"""
qs_ops.application.jobs - 原目 application.jobs 于 2026-10-19 归并入 ops 调度任务独立包

所有定时任务必须在此包中实现，遵循统一的 Job 协议。
调度层（infrastructure.scheduler）只通过 JobRegistry 分发任务，
不包含任何业务逻辑。
"""

from qs_ops.application.jobs.job_protocol import Job, JobResult

__all__ = ["Job", "JobResult"]
