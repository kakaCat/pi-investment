"""
监控类定时任务

包含：market_perception_daily_snapshot
"""
import logging
from typing import Any, Dict

from application.jobs.job_protocol import Job, JobResult

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


# 导出所有监控类任务
MONITOR_JOBS = [
    MarketPerceptionDailySnapshotJob(),
]
