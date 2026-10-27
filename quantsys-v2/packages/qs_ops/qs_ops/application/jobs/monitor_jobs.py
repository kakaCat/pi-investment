"""
监控类定时任务

包含：market_perception_daily_snapshot, v2_health_check
"""
import logging
from typing import Any, Dict

from qs_ops.application.jobs.job_protocol import Job, JobResult

logger = logging.getLogger(__name__)


class MarketPerceptionDailySnapshotJob(Job):
    """M1 市场感知每日快照"""

    @property
    def name(self) -> str:
        return "market_perception_daily_snapshot"

    @property
    def description(self) -> str:
        return "M1 市场感知每日快照（regime + sentiment + theme）"

    @property
    def timeout_seconds(self) -> int:
        return 1800  # 30分钟

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from application.services.market_perception_service import MarketPerceptionService
            service = MarketPerceptionService()
            trade_date = (params or {}).get("date")
            regime_result = service.run_daily_snapshot(trade_date=trade_date)
            return JobResult.ok(
                self.name,
                message=f"市场感知快照完成: {regime_result.get('regime')}",
                details=regime_result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class V2HealthCheckJob(Job):
    """V2 调度健康检查（本地 APScheduler 与 webhook 同一检查口径）"""

    @property
    def name(self) -> str:
        return "v2_health_check"

    @property
    def description(self) -> str:
        return "检查僵尸运行、漏执行、高失败率与任务域打标"

    @property
    def timeout_seconds(self) -> int:
        return 300

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from adapters.outbound.repositories.scheduler_repository import SchedulerRepository
            from qs_kernel.infrastructure.persistence.orm import get_session
            from qs_ops.application.jobs.health_monitor import check_job_health

            repo = SchedulerRepository(get_session())
            result = check_job_health(repo)
            healthy = bool(result.get("healthy"))
            return JobResult.ok(
                self.name,
                message="调度健康" if healthy else "调度健康降级",
                healthy=healthy,
                summary=result.get("summary") or {},
                issues=result.get("issues") or [],
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有监控类任务
MONITOR_JOBS = [
    MarketPerceptionDailySnapshotJob(),
    V2HealthCheckJob(),
]
