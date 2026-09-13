"""
智能调度服务 - ORM版本
基于 APScheduler 的增强调度器，支持动态任务管理和优先级调度

完全使用ORM，不再直接执行SQL
"""
import structlog
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED

from domain.ports import ISchedulerConfigRepository

logger = structlog.get_logger(__name__)


class SmartSchedulerService:
    """智能调度服务（ORM版本）

    功能：
    1. 定时任务调度（Cron）
    2. 任务优先级管理
    3. 失败重试机制
    4. 任务执行历史记录
    5. 动态任务注册/注销

    迁移状态：✅ 已完成ORM迁移
    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(self, config_repo: Optional[ISchedulerConfigRepository] = None):
        """初始化服务

        Args:
            config_repo: 调度器配置仓库（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.scheduler = BackgroundScheduler(
            timezone='Asia/Shanghai',
            job_defaults={
                'coalesce': True,  # 合并错过的执行
                'max_instances': 1,  # 同一任务最多1个实例
                'misfire_grace_time': 300  # 错过5分钟内仍执行
            }
        )
        self.task_registry: Dict[str, Dict[str, Any]] = {}
        self.config_repo = config_repo
        self._setup_listeners()
        logger.info("SmartSchedulerService initialized with ORM")

    def _setup_listeners(self):
        """设置任务执行监听器"""
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR
        )
        self.scheduler.add_listener(
            self._on_job_missed,
            EVENT_JOB_MISSED
        )

    def _on_job_executed(self, event):
        """任务执行成功回调"""
        job_id = event.job_id
        logger.info(f"Job executed successfully: {job_id}")

        # 记录执行历史（简化版本，不依赖数据库）
        # 可以后续添加执行历史的ORM Repository

    def _on_job_error(self, event):
        """任务执行失败回调"""
        job_id = event.job_id
        logger.error(f"Job failed: {job_id}, error: {event.exception}")

        # 记录执行历史（简化版本）

        # TODO: 实现重试逻辑

    def _on_job_missed(self, event):
        """任务错过执行回调"""
        job_id = event.job_id
        logger.warning(f"Job missed: {job_id}")

    def _update_run_status(
        self,
        job_id: str,
        status: str,
        execution_time_ms: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """更新任务执行状态。

        2026-09-13（w-32314d00，REQ-24e15d t3）：原先在此手写两条裸 SQL（SELECT run_id / UPDATE runs），
        现上收到 AutomationRunRepository —— 服务层不再直连 SQL；同时避免该路径再受
        「ORM 列名映射错（run_metadata vs metadata）」类问题影响（该问题本次已修）。
        """
        from datetime import datetime

        try:
            from adapters.outbound.repositories.automation_repository import AutomationRunRepository

            repo = AutomationRunRepository()
            run_id = repo.find_running_run_id_by_job_id(job_id)
            if run_id:
                repo.update_run(run_id, {
                    'status': status,
                    'completed_at': datetime.now(),
                    'execution_time_ms': execution_time_ms,
                    'error_message': error_message,
                })
        except Exception as e:
            logger.error(f"Failed to update run status: {e}")

    def register_task(
        self,
        task_id: int,
        task_name: str,
        task_func: Callable,
        schedule: str,
        params: Dict = None,
        priority: int = 5
    ) -> str:
        """注册定时任务

        Args:
            task_id: 任务ID（数据库ID）
            task_name: 任务名称
            task_func: 任务执行函数
            schedule: Cron 表达式
            params: 任务参数
            priority: 优先级 1-10

        Returns:
            job_id: APScheduler 任务ID
        """
        try:
            # 创建触发器
            trigger = CronTrigger.from_crontab(schedule, timezone='Asia/Shanghai')

            # 包装任务函数
            def wrapped_task():
                return self._execute_task(task_id, task_name, task_func, params or {})

            # 添加到调度器
            job = self.scheduler.add_job(
                wrapped_task,
                trigger=trigger,
                id=f"task_{task_id}",
                name=task_name,
                max_instances=1,
                coalesce=True,
                replace_existing=True
            )

            # 注册到本地缓存
            self.task_registry[task_name] = {
                'task_id': task_id,
                'job_id': job.id,
                'job': job,
                'priority': priority,
                'params': params,
                'schedule': schedule
            }

            logger.info(f"Registered task: {task_name} (id={task_id}, schedule={schedule})")
            return job.id

        except Exception as e:
            logger.error(f"Failed to register task {task_name}: {e}")
            raise

    def _execute_task(
        self,
        task_id: int,
        task_name: str,
        task_func: Callable,
        params: Dict
    ) -> Any:
        """执行任务并记录历史

        Args:
            task_id: 任务ID
            task_name: 任务名称
            task_func: 任务函数
            params: 任务参数

        Returns:
            任务执行结果
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()

        # 记录开始执行
        # （2026-09-13，w-32314d00，REQ-24e15d t3：裸 INSERT 上收到仓储；
        #   同时删掉上收后残留的 `conn = get_db_connection()` —— 它已无人使用，
        #   留着等于白开一条连接，正是本 REQ 要消灭的那类占用。）
        from adapters.outbound.repositories.automation_repository import AutomationRunRepository

        AutomationRunRepository().create_run({
            'task_id': task_id,
            'run_id': run_id,
            'trigger_type': 'scheduled',
            'trigger_by': 'system',
            'started_at': start_time,
            'status': 'running',
            'run_metadata': {'job_id': f'task_{task_id}'},
        })

        # 执行任务
        try:
            logger.info(f"Executing task: {task_name} (run_id={run_id})")
            result = task_func(**params)

            # 记录成功
            end_time = datetime.now()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # 2026-09-13（w-32314d00，REQ-24e15d t3）：成功路径两条裸 UPDATE 上收到仓储。
            # 取数前已核对：ORM 模型 AutomationTask 含 last_run_at（与真实库列一致），
            # 故 update_task 的 setattr 不会静默跳过（这类"属性未映射→静默不改"是必须防的坑）。
            from adapters.outbound.repositories.automation_repository import (
                AutomationRunRepository,
                AutomationTaskRepository,
            )

            AutomationRunRepository().update_run(run_id, {
                'status': 'success',
                'completed_at': end_time,
                'execution_time_ms': execution_time_ms,
                'result': result,
            })

            # 更新任务最后执行时间（按任务名更新，服务侧本来就以 task_name 为键）
            AutomationTaskRepository().update_task(task_name, {'last_run_at': start_time})

            logger.info(f"Task completed: {task_name} (run_id={run_id}, time={execution_time_ms}ms)")
            return result

        except Exception as e:
            # 记录失败
            end_time = datetime.now()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            logger.error(f"Task failed: {task_name} (run_id={run_id}), error: {e}")

            # 2026-09-13（w-32314d00，REQ-24e15d t3）：失败路径的裸 UPDATE 上收到仓储。
            from adapters.outbound.repositories.automation_repository import AutomationRunRepository

            AutomationRunRepository().update_run(run_id, {
                'status': 'failed',
                'completed_at': end_time,
                'execution_time_ms': execution_time_ms,
                'error_message': str(e),
            })

            raise

    def trigger_task(self, task_name: str, params: Dict = None) -> str:
        """手动触发任务

        Args:
            task_name: 任务名称
            params: 覆盖的参数

        Returns:
            run_id: 执行ID
        """
        if task_name not in self.task_registry:
            raise ValueError(f"Task not found: {task_name}")

        task_info = self.task_registry[task_name]
        task_id = task_info['task_id']

        # 合并参数
        merged_params = {**task_info['params'], **(params or {})}

        # 从数据库获取任务函数
        # TODO: 这里需要一个任务函数注册表
        # 暂时使用 job.func 直接执行

        run_id = f"run_{uuid.uuid4().hex[:12]}"

        # 记录手动触发（2026-09-13，w-32314d00，REQ-24e15d t3：裸 INSERT 上收到仓储 —— 本文件最后一处）
        from adapters.outbound.repositories.automation_repository import AutomationRunRepository

        AutomationRunRepository().create_run({
            'task_id': task_id,
            'run_id': run_id,
            'trigger_type': 'manual',
            'trigger_by': 'user',
            'started_at': datetime.now(),
            'status': 'pending',
        })

        # 异步执行
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)

        def execute():
            # 这里需要实际的任务函数
            pass

        future = executor.submit(execute)

        logger.info(f"Manually triggered task: {task_name} (run_id={run_id})")
        return run_id

    def unregister_task(self, task_name: str):
        """注销任务"""
        if task_name not in self.task_registry:
            logger.warning(f"Task not found: {task_name}")
            return

        task_info = self.task_registry[task_name]
        job_id = task_info['job_id']

        # 从调度器移除
        self.scheduler.remove_job(job_id)

        # 从缓存移除
        del self.task_registry[task_name]

        logger.info(f"Unregistered task: {task_name}")

    def get_task_status(self, task_name: str) -> Optional[Dict]:
        """获取任务状态"""
        if task_name not in self.task_registry:
            return None

        task_info = self.task_registry[task_name]
        job = task_info['job']

        return {
            'task_name': task_name,
            'job_id': job.id,
            'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
            'schedule': task_info['schedule'],
            'priority': task_info['priority']
        }

    def list_tasks(self) -> List[Dict]:
        """列出所有任务"""
        return [
            self.get_task_status(task_name)
            for task_name in self.task_registry
        ]

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("SmartScheduler started")

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("SmartScheduler stopped")

    def pause_task(self, task_name: str):
        """暂停任务"""
        if task_name in self.task_registry:
            job_id = self.task_registry[task_name]['job_id']
            self.scheduler.pause_job(job_id)
            logger.info(f"Paused task: {task_name}")

    def resume_task(self, task_name: str):
        """恢复任务"""
        if task_name in self.task_registry:
            job_id = self.task_registry[task_name]['job_id']
            self.scheduler.resume_job(job_id)
            logger.info(f"Resumed task: {task_name}")


# 全局单例
_scheduler_instance: Optional[SmartSchedulerService] = None


def get_scheduler() -> SmartSchedulerService:
    """获取调度器单例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SmartSchedulerService()
    return _scheduler_instance
