"""
JobRegistry - 统一的任务注册表

所有定时任务通过 @register 装饰器注册到此表。
调度层通过 job_registry.get(name) 获取任务并执行。
"""
import logging
from typing import Any, Dict, Optional

from application.jobs.job_protocol import Job, JobResult

logger = logging.getLogger(__name__)


class JobRegistry:
    """任务注册表"""

    def __init__(self):
        self._jobs: Dict[str, Job] = {}

    def register(self, job: Job) -> None:
        """注册任务"""
        if job.name in self._jobs:
            logger.warning(f"Job '{job.name}' already registered, overwriting")
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


# 全局单例
job_registry = JobRegistry()
