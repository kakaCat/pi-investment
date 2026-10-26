"""
JobRegistry - 统一的任务注册表

所有定时任务通过 @register 装饰器注册到此表。
调度层通过 job_registry.get(name) 获取任务并执行。
"""
import logging
from typing import Any, Dict, Optional

from qs_ops.application.jobs.job_protocol import Job, JobResult

logger = logging.getLogger(__name__)


class JobRegistry:
    """任务注册表"""

    def __init__(self):
        self._jobs: Dict[str, Job] = {}

    def register(self, job: Job) -> None:
        """注册任务（幂等 + 冲突守卫）

        同一实例重复注册 → 静默跳过（register_all_jobs 重复调用安全）；
        同名不同实例 → 立即抛错（双源重复注册是结构缺陷，会静默覆盖正确实现，
        审计实证：pool_refresh_daily 曾被旧版 Job 覆盖正确实现导致空转 13 天）。
        """
        existing = self._jobs.get(job.name)
        if existing is not None:
            if existing is job:
                logger.debug(f"Job '{job.name}' already registered (same instance), skipping")
                return
            raise RuntimeError(
                f"Job '{job.name}' already registered by a different instance "
                f"({type(existing).__name__} vs {type(job).__name__}). "
                f"Duplicate registration hides one implementation — fix the registration source."
            )
        self._jobs[job.name] = job
        logger.info(f"Registered job: {job.name}")

    def get(self, name: str) -> Optional[Job]:
        """获取任务"""
        return self._jobs.get(name)

    def list_jobs(self) -> Dict[str, Job]:
        """列出所有任务"""
        return self._jobs.copy()

    async def execute(self, name: str, params: Dict[str, Any] = None) -> JobResult:
        """执行任务

        Args:
            name: 任务名
            params: 任务参数

        Returns:
            JobResult: 执行结果
        """
        job = self.get(name)
        if not job:
            return JobResult.fail(name, f"Unknown job: {name}")

        params = params or {}
        try:
            logger.info(f"Executing job: {name}")
            result = await job.execute(params)
            logger.info(f"Job {name} completed: success={result.success}")
            return result
        except Exception as e:
            logger.exception(f"Job {name} failed with exception")
            return JobResult.fail(name, str(e))
        finally:
            # 会话收尾（2026-10-21，看板事件 a6780ec3 / 3267a4ad）：
            # 本方法是**所有后台作业的统一出口**（job 在线程池里跑）。作业内部
            # 走仓储取数会开 scoped session 并起事务，若不归还：
            #   ① 连接长期 idle in transaction，挡住 autovacuum、持旧快照；
            #   ② 约 300s 后被 PG 强杀 → session_guard 判为 session_leak_detected
            #      （实测累计 1139 次，其中 22:07 一次来自 ThreadPoolExecutor-0_1）。
            # close_session() 按线程归还 scoped session，只影响本作业线程。
            try:
                from qs_kernel.infrastructure.persistence.orm import close_session
                close_session()
            except Exception:
                pass


# 全局单例
job_registry = JobRegistry()
