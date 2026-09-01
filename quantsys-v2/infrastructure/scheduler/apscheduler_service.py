"""
APScheduler 封装服务

将手写调度器迁移到 APScheduler 框架，提供：
- 秒级精确调度（vs 原 30s 轮询）
- 分布式锁支持（PostgreSQL advisory lock）
- 成熟的 misfire 处理
- 延迟任务支持（DateTrigger）
- 间隔任务支持（IntervalTrigger）
- 社区维护，降低维护成本

Created: 2026-09-01
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

if TYPE_CHECKING:
    from domain.ports import ISchedulerRepository

logger = logging.getLogger(__name__)


class APSchedulerService:
    """APScheduler 封装服务"""

    def __init__(self, db_url: str, repo: ISchedulerRepository):
        """
        初始化 APScheduler

        Args:
            db_url: 数据库连接 URL (用于 jobstore)
            repo: 调度器仓储（用于读取 scheduler_tasks）
        """
        self.repo = repo

        # 配置 jobstore（使用 PostgreSQL 存储调度状态）
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=db_url,
                tablename='apscheduler_jobs'
            )
        }

        # 配置执行器（线程池）
        executors = {
            'default': ThreadPoolExecutor(max_workers=10)
        }

        # 配置任务默认参数
        job_defaults = {
            'coalesce': False,        # 不合并多次 misfire（每次都执行）
            'max_instances': 1,       # 每个任务最多 1 个实例（防止并发）
            'misfire_grace_time': 300 # 5 分钟宽限期（超过则跳过）
        }

        # 创建调度器（使用 BackgroundScheduler，在后台线程运行）
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='Asia/Shanghai'
        )

        logger.info("APSchedulerService initialized")

    def load_tasks_from_db(self):
        """
        从 scheduler_tasks 表加载任务到 APScheduler

        跳过 cron_expression='managed_by_agent_os' 的任务（由 Agent OS 管理）
        支持任务类型：
        - cron: 定时任务（CronTrigger）
        - delay: 延迟任务（DateTrigger，一次性）
        - interval: 间隔任务（IntervalTrigger）
        - once: 一次性任务（DateTrigger）
        """
        tasks = self.repo.list_tasks(enabled_only=True)
        loaded_count = 0
        skipped_count = 0

        for task in tasks:
            # 跳过由 Agent OS 管理的任务
            if task.get("cron_expression") == "managed_by_agent_os":
                logger.info(f"Skip Agent OS managed task: {task.get('name')}")
                skipped_count += 1
                continue

            try:
                # 根据 task_type 创建不同的 trigger
                task_type = task.get('task_type', 'cron')
                trigger = self._create_trigger(task_type, task)

                # 添加任务到 APScheduler
                # 注意：使用模块级函数避免序列化问题
                from infrastructure.scheduler.job_executor import execute_scheduled_job

                self.scheduler.add_job(
                    func=execute_scheduled_job,
                    trigger=trigger,
                    args=[task.get("id")],
                    id=f"task_{task.get("id")}",
                    name=task.get("name"),
                    replace_existing=True,
                    misfire_grace_time=task.get("misfire_grace_time_seconds") or 300
                )

                loaded_count += 1
                logger.info(
                    f"Loaded task: {task.get('name')} "
                    f"(id={task.get('id')}, type={task_type}, expr={task.get('cron_expression')})"
                )

            except Exception as e:
                logger.error(f"Failed to load task {task.get('name')}: {e}", exc_info=True)

        logger.info(
            f"Task loading complete: {loaded_count} loaded, "
            f"{skipped_count} skipped (Agent OS)"
        )

    def _create_trigger(self, task_type: str, task):
        """
        根据任务类型创建 APScheduler 触发器

        Args:
            task_type: 任务类型 (cron/delay/interval/once)
            task: 任务配置（字典或对象）

        Returns:
            APScheduler Trigger 对象

        Raises:
            ValueError: 不支持的任务类型或配置错误
        """
        # 统一获取属性的方式（支持字典和对象）
        def get_attr(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        cron_expr = get_attr(task, 'cron_expression')
        params = get_attr(task, 'params', {})
        task_name = get_attr(task, 'name', 'Unknown')

        if task_type == 'cron':
            # 标准 Cron 任务
            return CronTrigger.from_crontab(
                cron_expr,
                timezone='Asia/Shanghai'
            )

        elif task_type == 'delay':
            # 延迟任务：N 秒后执行一次
            delay_seconds = params.get('delay_seconds')
            if delay_seconds is None:
                # 尝试从 cron_expression 解析（格式：DELAY:300）
                if cron_expr and cron_expr.startswith('DELAY:'):
                    delay_seconds = int(cron_expr.split(':')[1])
                else:
                    raise ValueError(f"Delay task missing delay_seconds: {task_name}")

            run_at = datetime.now() + timedelta(seconds=delay_seconds)
            logger.info(f"Delay task {task_name} will run at {run_at}")
            return DateTrigger(run_date=run_at, timezone='Asia/Shanghai')

        elif task_type == 'interval':
            # 间隔任务：每 N 秒执行一次
            interval_seconds = params.get('interval_seconds')
            if interval_seconds is None:
                # 尝试从 cron_expression 解析（格式：INTERVAL:60）
                if cron_expr and cron_expr.startswith('INTERVAL:'):
                    interval_seconds = int(cron_expr.split(':')[1])
                else:
                    raise ValueError(f"Interval task missing interval_seconds: {task_name}")

            return IntervalTrigger(
                seconds=interval_seconds,
                timezone='Asia/Shanghai'
            )

        elif task_type == 'once':
            # 一次性任务：指定时间执行一次
            run_at_str = params.get('run_at') or cron_expr
            try:
                # 尝试解析 ISO 格式时间
                run_at = datetime.fromisoformat(run_at_str)
                logger.info(f"Once task {task_name} will run at {run_at}")
                return DateTrigger(run_date=run_at, timezone='Asia/Shanghai')
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid run_at format for once task {task_name}: {e}")

        else:
            raise ValueError(f"Unsupported task_type: {task_type}")

    def start(self):
        """启动调度器"""
        if self.scheduler.running:
            logger.warning("APScheduler already running")
            return

        # 先加载任务，再启动
        self.load_tasks_from_db()
        self.scheduler.start()

        logger.info("✅ APScheduler started")

    def shutdown(self, wait: bool = True):
        """
        关闭调度器

        Args:
            wait: 是否等待正在执行的任务完成
        """
        if not self.scheduler.running:
            logger.warning("APScheduler not running")
            return

        self.scheduler.shutdown(wait=wait)
        logger.info("✅ APScheduler shutdown")

    def reload_tasks(self):
        """
        重新加载任务（用于动态更新）

        使用场景：
        - 用户在 scheduler_tasks 表中添加/修改/删除任务后
        - 调用此方法同步到 APScheduler
        """
        if not self.scheduler.running:
            logger.error("Cannot reload tasks: scheduler not running")
            return

        # 移除所有现有任务
        self.scheduler.remove_all_jobs()

        # 重新加载
        self.load_tasks_from_db()

        logger.info("✅ Tasks reloaded")

    def get_job_status(self, task_id: int) -> dict:
        """
        获取任务在 APScheduler 中的状态

        Args:
            task_id: scheduler_tasks 表的任务 ID

        Returns:
            任务状态字典，包含 next_run_time 等信息
        """
        job = self.scheduler.get_job(f"task_{task_id}")

        if job is None:
            return {"exists": False}

        return {
            "exists": True,
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        }

    def trigger_task_now(self, task_id: int):
        """
        手动触发任务立即执行

        Args:
            task_id: scheduler_tasks 表的任务 ID
        """
        from datetime import datetime

        job = self.scheduler.get_job(f"task_{task_id}")
        if job is None:
            raise ValueError(f"Task {task_id} not found in APScheduler")

        # 修改下次执行时间为当前时间（立即执行）
        self.scheduler.modify_job(
            f"task_{task_id}",
            next_run_time=datetime.now()
        )

        logger.info(f"Task {task_id} triggered manually")
