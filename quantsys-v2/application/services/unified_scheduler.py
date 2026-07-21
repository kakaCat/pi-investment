"""
统一调度器服务 - 基于APScheduler
替代自研调度器，统一管理所有定时任务

Author: System Migration
Date: 2026-06-27
"""
import structlog
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from pathlib import Path

# 确保环境变量已加载
from dotenv import load_dotenv
_env_file = Path(__file__).parent.parent.parent / '.env'
if _env_file.exists():
    load_dotenv(_env_file)

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import (
    EVENT_JOB_EXECUTED,
    EVENT_JOB_ERROR,
    EVENT_JOB_MISSED,
    EVENT_JOB_ADDED,
    EVENT_JOB_REMOVED
)

from infrastructure.persistence.database.base_repository import _resolve_db_dsn

logger = structlog.get_logger(__name__)


class UnifiedSchedulerService:
    """统一调度器服务

    功能：
    1. 统一管理所有定时任务（替代自研scheduler）
    2. 基于APScheduler实现秒级精确调度
    3. 支持任务持久化到PostgreSQL
    4. 支持动态添加/删除/暂停/恢复任务
    5. 完整的任务执行监控和日志

    架构改进：
    - 从30秒轮询 → 事件驱动调度
    - 从1463行自研代码 → APScheduler标准实现
    - 统一4个独立调度器到一个服务
    """

    def __init__(self):
        """初始化统一调度器"""

        # 配置JobStore（持久化到PostgreSQL）
        db_url = _resolve_db_dsn()

        # 确保URL格式正确（postgresql+psycopg2://...）
        if db_url and not db_url.startswith('postgresql+'):
            db_url = db_url.replace('postgresql://', 'postgresql+psycopg2://')

        jobstores = {
            'default': SQLAlchemyJobStore(
                url=db_url,
                tablename='apscheduler_jobs'  # 新表，不影响旧的scheduler_tasks
            )
        }

        # 配置执行器
        executors = {
            'default': ThreadPoolExecutor(20),  # IO密集任务（数据获取、API调用）
            'processpool': ProcessPoolExecutor(5)  # CPU密集任务（回测、因子计算）
        }

        # 任务默认配置
        job_defaults = {
            'coalesce': True,  # 合并错过的多次执行为一次
            'max_instances': 1,  # 同一任务最多1个实例运行
            'misfire_grace_time': 300  # 错过5分钟内仍执行
        }

        # 创建调度器
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Shanghai'
        )

        # 任务注册表（用于监控和管理）
        self.task_registry: Dict[str, Dict[str, Any]] = {}

        # 设置事件监听器
        self._setup_listeners()

        logger.info("UnifiedSchedulerService initialized")

    def _setup_listeners(self):
        """设置任务执行监听器"""
        self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
        self.scheduler.add_listener(self._on_job_missed, EVENT_JOB_MISSED)
        self.scheduler.add_listener(self._on_job_added, EVENT_JOB_ADDED)
        self.scheduler.add_listener(self._on_job_removed, EVENT_JOB_REMOVED)

    def _on_job_executed(self, event):
        """任务执行成功回调"""
        job_id = event.job_id
        logger.info(f"✓ Job executed successfully: {job_id}")

        # 记录到自定义监控表（如需要）
        self._record_execution(
            job_id=job_id,
            status='success',
            scheduled_time=event.scheduled_run_time,
            retval=event.retval
        )

    def _on_job_error(self, event):
        """任务执行失败回调"""
        job_id = event.job_id
        exception = event.exception
        logger.error(f"✗ Job failed: {job_id}, error: {exception}")

        # 记录失败信息
        self._record_execution(
            job_id=job_id,
            status='failed',
            scheduled_time=event.scheduled_run_time,
            error_message=str(exception)
        )

        # TODO: 实现重试逻辑或告警通知

    def _on_job_missed(self, event):
        """任务错过执行回调"""
        job_id = event.job_id
        logger.warning(f"⚠ Job missed: {job_id}")

    def _on_job_added(self, event):
        """任务添加回调"""
        job_id = event.job_id
        logger.info(f"+ Job added: {job_id}")

    def _on_job_removed(self, event):
        """任务删除回调"""
        job_id = event.job_id
        logger.info(f"- Job removed: {job_id}")

    def _record_execution(
        self,
        job_id: str,
        status: str,
        scheduled_time: datetime,
        retval: Any = None,
        error_message: str = None
    ):
        """记录任务执行历史到数据库

        可选：如果需要保持与旧scheduler_runs表的兼容性

        注意：此方法已废弃，不再使用旧数据库连接
        """
        try:
            # 已迁移到APScheduler内置的job store
            # 不再需要手动记录执行历史
            logger.debug(f"Job {job_id} execution recorded by APScheduler")
        except Exception as e:
            logger.warning(f"Failed to record execution history: {e}")

    # ============================================================
    # 任务管理API
    # ============================================================

    def add_cron_job(
        self,
        func: Callable,
        cron_expr: str = None,
        job_id: str = None,
        name: str = None,
        args: tuple = None,
        kwargs: dict = None,
        executor: str = 'default',
        **cron_kwargs
    ) -> str:
        """添加Cron定时任务

        Args:
            func: 任务函数
            cron_expr: Cron表达式字符串 "30 16 * * 1-5" 或使用cron_kwargs
            job_id: 任务ID（唯一标识）
            name: 任务名称（显示用）
            args: 位置参数
            kwargs: 关键字参数
            executor: 执行器 'default' | 'processpool'
            **cron_kwargs: minute, hour, day, month, day_of_week等

        Returns:
            job_id: 任务ID

        Example:
            # 方式1: 使用cron表达式
            scheduler.add_cron_job(
                func=daily_data_update,
                cron_expr="30 16 * * 1-5",
                job_id="daily_data_update",
                name="每日数据更新"
            )

            # 方式2: 使用参数
            scheduler.add_cron_job(
                func=daily_data_update,
                job_id="daily_data_update",
                hour=16, minute=30, day_of_week='mon-fri'
            )
        """
        # 解析cron表达式
        if cron_expr:
            parts = cron_expr.split()
            if len(parts) == 5:
                cron_kwargs = {
                    'minute': parts[0],
                    'hour': parts[1],
                    'day': parts[2],
                    'month': parts[3],
                    'day_of_week': parts[4]
                }

        trigger = CronTrigger(**cron_kwargs, timezone='Asia/Shanghai')

        job = self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            name=name or job_id,
            args=args or (),
            kwargs=kwargs or {},
            executor=executor,
            replace_existing=True
        )

        # 记录到注册表
        self.task_registry[job.id] = {
            'id': job.id,
            'name': job.name,
            'func': func.__name__,
            'trigger': str(trigger),
            'executor': executor,
            'next_run': job.next_run_time
        }

        logger.info(f"Added cron job: {job.id}, next run: {job.next_run_time}")
        return job.id

    def add_interval_job(
        self,
        func: Callable,
        seconds: int = None,
        minutes: int = None,
        hours: int = None,
        job_id: str = None,
        name: str = None,
        args: tuple = None,
        kwargs: dict = None,
        executor: str = 'default'
    ) -> str:
        """添加间隔执行任务

        Example:
            # 每5分钟执行一次
            scheduler.add_interval_job(
                func=monitor_market,
                minutes=5,
                job_id="market_monitor_5min"
            )
        """
        from apscheduler.triggers.interval import IntervalTrigger

        # 确保至少有一个时间参数
        if seconds is None and minutes is None and hours is None:
            raise ValueError("Must specify at least one of: seconds, minutes, hours")

        trigger = IntervalTrigger(
            seconds=seconds or 0,
            minutes=minutes or 0,
            hours=hours or 0,
            timezone='Asia/Shanghai'
        )

        job = self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            name=name or job_id,
            args=args or (),
            kwargs=kwargs or {},
            executor=executor,
            replace_existing=True
        )

        logger.info(f"Added interval job: {job.id}, interval: {trigger}")
        return job.id

    def remove_job(self, job_id: str):
        """删除任务"""
        self.scheduler.remove_job(job_id)
        self.task_registry.pop(job_id, None)
        logger.info(f"Removed job: {job_id}")

    def pause_job(self, job_id: str):
        """暂停任务"""
        self.scheduler.pause_job(job_id)
        logger.info(f"Paused job: {job_id}")

    def resume_job(self, job_id: str):
        """恢复任务"""
        self.scheduler.resume_job(job_id)
        logger.info(f"Resumed job: {job_id}")

    def modify_job(self, job_id: str, **changes):
        """修改任务配置

        Example:
            # 修改执行时间
            scheduler.modify_job(
                'daily_data_update',
                trigger='cron',
                hour=17, minute=0
            )
        """
        self.scheduler.modify_job(job_id, **changes)
        logger.info(f"Modified job: {job_id}")

    def get_job(self, job_id: str):
        """获取任务信息"""
        return self.scheduler.get_job(job_id)

    def get_all_jobs(self) -> List:
        """获取所有任务"""
        return self.scheduler.get_jobs()

    def print_jobs(self):
        """打印所有任务信息"""
        jobs = self.get_all_jobs()
        if not jobs:
            logger.info("No scheduled jobs")
            return

        logger.info(f"Total {len(jobs)} scheduled jobs:")
        for job in jobs:
            logger.info(f"  - {job.id}: {job.name}")
            logger.info(f"    Next run: {job.next_run_time}")
            logger.info(f"    Trigger: {job.trigger}")

    # ============================================================
    # 生命周期管理
    # ============================================================

    def start(self):
        """启动调度器（非阻塞）"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("✓ UnifiedScheduler started (non-blocking)")
        else:
            logger.warning("Scheduler already running")

    def shutdown(self, wait: bool = True):
        """优雅关闭调度器

        Args:
            wait: 是否等待运行中的任务完成
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)
            logger.info("✓ UnifiedScheduler shutdown")

    def is_running(self) -> bool:
        """检查调度器是否运行"""
        return self.scheduler.running

    # ============================================================
    # 任务注册 - 从旧scheduler迁移
    # ============================================================

    def register_from_database(self):
        """从数据库配置表动态注册任务

        读取 quant.scheduler_task_configs 表中的任务配置
        支持完全的数据库驱动配置
        """
        try:
            from application.services.scheduler_config_service import SchedulerConfigService

            config_service = SchedulerConfigService()

            # 获取所有启用的任务配置
            configs = config_service.list_configs(enabled_only=True)

            logger.info(f"Found {len(configs)} enabled task configs in database")

            for config in configs:
                try:
                    self._register_config(config)
                except Exception as e:
                    logger.error(f"Failed to register task {config['task_name']}: {e}")

            logger.info(f"✓ Registered {len(configs)} tasks from database")

        except Exception as e:
            logger.error(f"Failed to load task configs from database: {e}")

    def _register_config(self, config: Dict):
        """注册单个数据库配置的任务

        Args:
            config: 任务配置字典，包含：
                - task_name: 任务名称
                - cron_expression: Cron表达式
                - command: 命令
                - params: 参数（JSON）
                - executor: 执行器
                - max_instances: 最大实例数
                - misfire_grace_time: 错过执行宽限时间
                - coalesce: 是否合并错过的执行
        """
        from application.services.scheduler_tasks import get_task_handler

        task_name = config['task_name']
        cron_expr = config['cron_expression']
        command = config['command']
        params = config.get('params', {})

        try:
            handler = get_task_handler(command)

            # 创建包装函数，传递params
            def wrapped_handler():
                return handler(params)

            # 注册到APScheduler
            job_defaults = {
                'max_instances': config.get('max_instances', 1),
                'misfire_grace_time': config.get('misfire_grace_time', 300),
                'coalesce': config.get('coalesce', True)
            }

            self.add_cron_job(
                func=wrapped_handler,
                cron_expr=cron_expr,
                job_id=f"db_{task_name}",
                name=task_name,
                executor=config.get('executor', 'default')
            )

            logger.info(f"✓ Registered database task: {task_name}")

        except Exception as e:
            logger.error(f"Failed to get handler for command '{command}': {e}")
            raise

    def reload_from_database(self):
        """重新从数据库加载任务配置

        热重载功能：
        1. 移除所有 db_ 前缀的任务
        2. 重新从数据库加载
        3. 不影响其他任务

        用途：更新任务配置后无需重启系统
        """
        try:
            # 获取所有以 db_ 开头的任务
            all_jobs = self.get_all_jobs()
            db_jobs = [job for job in all_jobs if job.id.startswith('db_')]

            # 移除旧的数据库任务
            for job in db_jobs:
                self.remove_job(job.id)
                logger.info(f"Removed old database task: {job.id}")

            # 重新加载
            self.register_from_database()

            logger.info("✓ Database tasks reloaded successfully")

        except Exception as e:
            logger.error(f"Failed to reload database tasks: {e}")
            raise

    def register_legacy_tasks(self):
        """注册从旧调度器迁移的任务

        读取 quant.scheduler_tasks 表中的任务定义
        """
        try:
            # 使用ORM加载任务配置
            from adapters.outbound.repositories import SchedulerConfigORMRepository

            repo = SchedulerConfigORMRepository()
            tasks = repo.get_enabled_tasks()

            logger.info(f"Found {len(tasks)} enabled tasks from SchedulerConfigORMRepository")

            for task in tasks:
                try:
                    self._register_legacy_task(task.to_dict())
                except Exception as e:
                    logger.error(f"Failed to register task {task.task_name}: {e}")

            logger.info(f"✓ Registered {len(tasks)} legacy tasks")

        except Exception as e:
            logger.error(f"Failed to load legacy tasks: {e}")

    def _register_legacy_task(self, task: Dict):
        """注册单个旧任务

        Args:
            task: 包含 name, schedule_expr, command, params
        """
        job_id = f"legacy_{task['task_id']}_{task['name']}"
        cron_expr = task['schedule_expr']
        command = task['command']
        params = task.get('params', {})

        # 导入command handlers
        from application.services.scheduler_tasks import get_task_handler

        try:
            handler = get_task_handler(command)

            self.add_cron_job(
                func=handler,
                cron_expr=cron_expr,
                job_id=job_id,
                name=task['name'],
                kwargs=params
            )

            logger.info(f"✓ Registered legacy task: {task['name']}")
        except Exception as e:
            logger.error(f"Failed to get handler for command '{command}': {e}")


# ============================================================
# 全局单例
# ============================================================

_unified_scheduler: Optional[UnifiedSchedulerService] = None


def get_unified_scheduler() -> UnifiedSchedulerService:
    """获取全局统一调度器实例（单例模式）"""
    global _unified_scheduler
    if _unified_scheduler is None:
        _unified_scheduler = UnifiedSchedulerService()
    return _unified_scheduler
