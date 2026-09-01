"""
分析类定时任务

包含：factor_compute, strategy_validate_daily, strategy_discover_weekly,
      chan_scan, chan_knowledge_distill, market_style_update,
      market_scan_preopen, financial_statement_update
"""
import logging
from typing import Any, Dict

from application.jobs.job_protocol import Job, JobResult

logger = logging.getLogger(__name__)


class FactorComputeJob(Job):
    """因子计算任务"""

    @property
    def name(self) -> str:
        return "factor_compute"

    @property
    def description(self) -> str:
        return "计算技术因子和量化因子"

    @property
    def timeout_seconds(self) -> int:
        return 7200  # 2小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.scheduler.scheduler import SchedulerService
            scheduler = SchedulerService()
            result = scheduler._handle_factor_compute(params)
            return JobResult.ok(
                self.name,
                message="因子计算完成",
                details=result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class StrategyValidateDailyJob(Job):
    """每日策略验证"""

    @property
    def name(self) -> str:
        return "strategy_validate_daily"

    @property
    def description(self) -> str:
        return "验证策略性能和参数"

    @property
    def timeout_seconds(self) -> int:
        return 3600  # 1小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from adapters.outbound.repositories.strategy_repository import StrategyORMRepository

            strategies = StrategyORMRepository().list_strategies()
            validated_count = 0
            failed_validations = []

            for strategy in strategies:
                try:
                    # TODO: 实现实际验证逻辑
                    validated_count += 1
                except Exception as e:
                    logger.warning(f"Validation failed for strategy {strategy.get('id')}: {e}")
                    failed_validations.append(strategy.get('strategy_name'))

            return JobResult.ok(
                self.name,
                message=f"策略验证完成: {validated_count} validated",
                details={
                    "validated_count": validated_count,
                    "failed_validations": failed_validations
                }
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class StrategyDiscoverWeeklyJob(Job):
    """每周策略发现"""

    @property
    def name(self) -> str:
        return "strategy_discover_weekly"

    @property
    def description(self) -> str:
        return "发现新的交易策略或模式"

    @property
    def timeout_seconds(self) -> int:
        return 7200  # 2小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from adapters.outbound.repositories.stock_repository import StockORMRepository
            stocks = StockORMRepository().list_all_active(market="A")
            return JobResult.ok(
                self.name,
                message=f"策略发现完成: {len(stocks)} stocks analyzed",
                details={"stocks_analyzed": len(stocks)}
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class ChanScanJob(Job):
    """缠论技术分析扫描"""

    @property
    def name(self) -> str:
        return "chan_scan"

    @property
    def description(self) -> str:
        return "缠论技术分析扫描"

    @property
    def timeout_seconds(self) -> int:
        return 3600  # 1小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            # TODO: 实现缠论扫描逻辑
            return JobResult.ok(
                self.name,
                message="缠论扫描完成（待实现）",
                details={"scanned": 0}
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class ChanKnowledgeDistillJob(Job):
    """每周缠论知识蒸馏"""

    @property
    def name(self) -> str:
        return "chan_knowledge_distill"

    @property
    def description(self) -> str:
        return "缠论知识蒸馏"

    @property
    def timeout_seconds(self) -> int:
        return 7200  # 2小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            # TODO: 实现知识蒸馏逻辑
            return JobResult.ok(
                self.name,
                message="缠论知识蒸馏完成（待实现）",
                details={"distilled": 0}
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class MarketStyleUpdateJob(Job):
    """市场风格检测"""

    @property
    def name(self) -> str:
        return "market_style_update"

    @property
    def description(self) -> str:
        return "检测市场风格并保存到数据库"

    @property
    def timeout_seconds(self) -> int:
        return 1800  # 30分钟

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            # TODO: 实现市场风格检测逻辑
            return JobResult.ok(
                self.name,
                message="市场风格检测完成（待实现）",
                details={"style": "unknown"}
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class MarketScanPreopenJob(Job):
    """盘前扫描"""

    @property
    def name(self) -> str:
        return "market_scan_preopen"

    @property
    def description(self) -> str:
        return "盘前扫描交易机会"

    @property
    def timeout_seconds(self) -> int:
        return 1800  # 30分钟

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from adapters.outbound.repositories.stock_repository import StockORMRepository
            stocks = StockORMRepository().list_all_active(market="A")
            return JobResult.ok(
                self.name,
                message=f"盘前扫描完成: {len(stocks)} stocks",
                details={"stocks_scanned": len(stocks)}
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class FinancialStatementUpdateJob(Job):
    """季度财报三大报表落库"""

    @property
    def name(self) -> str:
        return "financial_statement_update"

    @property
    def description(self) -> str:
        return "季度财报三大报表落库"

    @property
    def timeout_seconds(self) -> int:
        return 7200  # 2小时

    @property
    def misfire_grace_time_seconds(self) -> int:
        return 43200  # 12小时

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        try:
            from infrastructure.jobs.financial_statement_update_job import execute
            result = execute(**params)
            return JobResult.ok(
                self.name,
                message="财报更新完成",
                details=result
            )
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class DecisionScoreDailyJob(Job):
    """决策打分每日任务（旧 handle_decision_score_daily，ADR-002 Phase 1 补齐）"""

    @property
    def name(self) -> str:
        return "decision_score_daily"

    @property
    def description(self) -> str:
        return "满20交易日的买卖决策打分回写（文本参数进化 P0a）"

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        import asyncio

        def _run() -> Dict[str, Any]:
            from application.services.evolution.decision_score_service import DecisionScoreService
            return DecisionScoreService().score_mature_decisions()

        try:
            result = await asyncio.to_thread(_run)
            return JobResult.ok(self.name, message="决策打分完成", details=result)
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class EvolutionFitnessDailyJob(Job):
    """双侧捕获适应度每日计算（旧 handle_evolution_fitness_daily，ADR-002 Phase 1 补齐）"""

    @property
    def name(self) -> str:
        return "evolution_fitness_daily"

    @property
    def description(self) -> str:
        return "收盘后全账户滚动窗口适应度计算（行为进化 Phase 1）"

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        import asyncio

        def _run() -> Dict[str, Any]:
            from application.services.evolution.evolution_fitness_service import EvolutionFitnessService
            return EvolutionFitnessService().compute_all_accounts(
                window_days=params.get('window_days', 20))

        try:
            result = await asyncio.to_thread(_run)
            return JobResult.ok(self.name, message="适应度计算完成", details=result)
        except Exception as e:
            return JobResult.fail(self.name, str(e))


class MissedOpportunityDailyJob(Job):
    """踏空捕获每日任务（旧 handle_missed_opportunity_daily，ADR-002 Phase 1 补齐）"""

    @property
    def name(self) -> str:
        return "missed_opportunity_daily"

    @property
    def description(self) -> str:
        return "未行动买入信号补登为 missed_opportunity 决策（文本参数进化 P0b）"

    async def execute(self, params: Dict[str, Any]) -> JobResult:
        import asyncio

        def _run() -> Dict[str, Any]:
            from application.services.evolution.missed_opportunity_service import MissedOpportunityService
            return MissedOpportunityService().capture()

        try:
            result = await asyncio.to_thread(_run)
            return JobResult.ok(self.name, message="踏空捕获完成", details=result)
        except Exception as e:
            return JobResult.fail(self.name, str(e))


# 导出所有分析类任务
ANALYSIS_JOBS = [
    FactorComputeJob(),
    StrategyValidateDailyJob(),
    StrategyDiscoverWeeklyJob(),
    ChanScanJob(),
    ChanKnowledgeDistillJob(),
    MarketStyleUpdateJob(),
    MarketScanPreopenJob(),
    FinancialStatementUpdateJob(),
    DecisionScoreDailyJob(),
    EvolutionFitnessDailyJob(),
    MissedOpportunityDailyJob(),
]
