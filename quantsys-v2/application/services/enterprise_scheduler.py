"""
企业级调度服务
使用APScheduler + PostgreSQL实现持久化任务调度
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from infrastructure.persistence.database.engine import _resolve_db_dsn

logger = logging.getLogger(__name__)


class EnterpriseScheduler:
    """企业级调度服务"""
    
    def __init__(self):
        self.scheduler = None
        self._initialized = False
        
    def initialize(self):
        """初始化调度器"""
        if self._initialized:
            logger.warning("Scheduler already initialized")
            return
            
        try:
            # 配置JobStore - 使用PostgreSQL持久化
            dsn = _resolve_db_dsn()
            jobstores = {
                'default': SQLAlchemyJobStore(url=dsn, tablename='apscheduler_jobs')
            }
            
            # 配置执行器
            executors = {
                'default': ThreadPoolExecutor(20),  # 默认线程池
                'processpool': ProcessPoolExecutor(5)  # 进程池用于CPU密集任务
            }
            
            # 任务默认配置
            job_defaults = {
                'coalesce': True,  # 合并错过的任务
                'max_instances': 1,  # 每个任务最多同时运行1个实例
                'misfire_grace_time': 300  # 错过5分钟内的任务仍然执行
            }
            
            # 创建调度器
            self.scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone='Asia/Shanghai'
            )
            
            # 添加事件监听器
            self.scheduler.add_listener(
                self._job_executed_listener,
                EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
            )
            
            self._initialized = True
            logger.info("Enterprise scheduler initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            raise
    
    def start(self):
        """启动调度器"""
        if not self._initialized:
            self.initialize()
        
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Enterprise scheduler started")
        else:
            logger.warning("Scheduler already running")
    
    def shutdown(self, wait: bool = True):
        """关闭调度器"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("Enterprise scheduler shutdown")
    
    def add_job(
        self,
        job_id: str,
        func: callable,
        cron_expression: str,
        args: tuple = None,
        kwargs: dict = None,
        name: str = None,
        description: str = None,
        executor: str = 'default',
        replace_existing: bool = True
    ) -> str:
        """
        添加定时任务
        
        Args:
            job_id: 任务唯一ID
            func: 要执行的函数
            cron_expression: Cron表达式（如 "0 9 * * 1-5" 表示工作日9点）
            args: 函数位置参数
            kwargs: 函数关键字参数
            name: 任务名称
            description: 任务描述
            executor: 执行器类型
            replace_existing: 是否替换已存在的任务
            
        Returns:
            任务ID
        """
        try:
            # 解析cron表达式
            trigger = CronTrigger.from_crontab(cron_expression, timezone='Asia/Shanghai')
            
            # 添加任务
            job = self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                name=name or job_id,
                args=args or (),
                kwargs=kwargs or {},
                executor=executor,
                replace_existing=replace_existing
            )
            
            logger.info(f"Job added: {job_id} with cron: {cron_expression}")
            return job.id
            
        except Exception as e:
            logger.error(f"Failed to add job {job_id}: {e}")
            raise
    
    def remove_job(self, job_id: str):
        """删除任务"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Job removed: {job_id}")
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            raise
    
    def pause_job(self, job_id: str):
        """暂停任务"""
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"Job paused: {job_id}")
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            raise
    
    def resume_job(self, job_id: str):
        """恢复任务"""
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"Job resumed: {job_id}")
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            raise
    
    def trigger_job(self, job_id: str) -> bool:
        """手动触发任务执行"""
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.modify(next_run_time=datetime.now())
                logger.info(f"Job triggered: {job_id}")
                return True
            else:
                logger.warning(f"Job not found: {job_id}")
                return False
        except Exception as e:
            logger.error(f"Failed to trigger job {job_id}: {e}")
            raise
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """获取任务信息"""
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                return {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger),
                    'executor': job.executor,
                    'func': f"{job.func.__module__}.{job.func.__name__}"
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None
    
    def list_jobs(self) -> List[Dict]:
        """列出所有任务"""
        try:
            jobs = self.scheduler.get_jobs()
            return [
                {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger),
                    'executor': job.executor,
                    'func': f"{job.func.__module__}.{job.func.__name__}"
                }
                for job in jobs
            ]
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return []
    
    def get_status(self) -> Dict:
        """获取调度器状态"""
        return {
            'running': self.scheduler.running if self.scheduler else False,
            'jobs_count': len(self.scheduler.get_jobs()) if self.scheduler else 0,
            'state': self.scheduler.state if self.scheduler else 0
        }
    
    def _job_executed_listener(self, event):
        """任务执行监听器 - 记录执行日志"""
        from domain.ports import ISchedulerRepository
        from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory

        repo = EnhancedServiceFactory.resolve(ISchedulerRepository)
        try:
            if event.exception:
                # 任务执行失败
                repo.log_execution(
                    job_id=event.job_id,
                    status='error',
                    error=str(event.exception),
                    scheduled_time=event.scheduled_run_time,
                    start_time=None,
                    end_time=datetime.now()
                )
                logger.error(f"Job {event.job_id} failed: {event.exception}")
            else:
                # 任务执行成功
                repo.log_execution(
                    job_id=event.job_id,
                    status='success',
                    result=event.retval,
                    scheduled_time=event.scheduled_run_time,
                    start_time=None,
                    end_time=datetime.now()
                )
                logger.info(f"Job {event.job_id} executed successfully")
        except Exception as e:
            logger.error(f"Failed to log execution for {event.job_id}: {e}")


# 全局单例
_scheduler_instance = None


def get_scheduler() -> EnterpriseScheduler:
    """获取调度器单例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = EnterpriseScheduler()
    return _scheduler_instance
