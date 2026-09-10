"""
任务注册 - 在应用启动时调用此模块注册所有任务
"""
import structlog
from application.jobs.job_registry import job_registry
from application.jobs.data_jobs import DATA_JOBS
from application.jobs.signal_jobs import SIGNAL_JOBS
from application.jobs.trading_jobs import TRADING_JOBS
from application.jobs.analysis_jobs import ANALYSIS_JOBS
from application.jobs.report_jobs import REPORT_JOBS
from application.jobs.monitor_jobs import MONITOR_JOBS
from application.jobs.model_jobs import MODEL_JOBS

logger = structlog.get_logger(__name__)


def register_all_jobs() -> None:
    """注册所有任务到 JobRegistry"""
    all_jobs = (
        DATA_JOBS +
        SIGNAL_JOBS +
        TRADING_JOBS +
        ANALYSIS_JOBS +
        REPORT_JOBS +
        MONITOR_JOBS +
        MODEL_JOBS
    )

    for job in all_jobs:
        job_registry.register(job)

    logger.info("registered_jobs", count=len(all_jobs))
