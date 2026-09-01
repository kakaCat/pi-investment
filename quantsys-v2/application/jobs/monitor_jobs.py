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


class RiskCheckJob(Job):
    """每周风险检查（旧 handle_risk_check，ADR-002 Phase 1 补齐）"""

    @property
    def name(self) -> str:
        return "risk_check"

    @property
    def description(self) -> str:
        return "组合/持仓/市场三维风险检查"

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        import asyncio

        def _run() -> Dict[str, Any]:
            from application.services.risk_check_service import RiskCheckService
            service = RiskCheckService()
            return service.run_comprehensive_risk_check(
                check_portfolio=params.get('check_portfolio', True),
                check_positions=params.get('check_positions', True),
                check_market=params.get('check_market', True),
            )

        try:
            report = await asyncio.to_thread(_run)
            return JobResult.ok(
                self.name,
                message=f"风险检查完成: {report.get('overall_risk_level', 'unknown')}",
                details=report,
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有监控类任务
MONITOR_JOBS = [
    DailyEquitySnapshotJob(),
    MarketPerceptionDailySnapshotJob(),
    RiskCheckJob(),
]
