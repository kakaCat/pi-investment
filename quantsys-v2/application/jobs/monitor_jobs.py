"""
监控类定时任务

包含：daily_equity_snapshot, market_perception_daily_snapshot
"""
import logging
from typing import Any, Dict

from application.jobs.job_protocol import Job, JobResult

logger = logging.getLogger(__name__)


class DailyEquitySnapshotJob(Job):
    """每日权益快照"""

    @property
    def name(self) -> str:
        return "daily_equity_snapshot"

    @property
    def description(self) -> str:
        return "记录所有账户的每日权益快照"

    @property
    def timeout_seconds(self) -> int:
        return 1800  # 30分钟

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            # TODO: 实现权益快照逻辑
            return JobResult.ok(
                self.name,
                message="权益快照完成（待实现）",
                details={"snapshots": 0}
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


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
            regime_result = await service.regime_daily()
            return JobResult.ok(
                self.name,
                message=f"市场感知快照完成: {regime_result.get('regime')}",
                details=regime_result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有监控类任务
MONITOR_JOBS = [
    DailyEquitySnapshotJob(),
    MarketPerceptionDailySnapshotJob(),
]
