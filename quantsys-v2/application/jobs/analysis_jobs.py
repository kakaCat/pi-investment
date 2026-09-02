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
            # Fix④: 原实现为空壳（数 strategy_configs 行数即报 validated_count，从不真实验证，
            # 假成功记录持续污染 scheduler_runs.last_status）。
            # 现委托 StrategyValidationService.validate_from_recent_backtests —— 基于最近落库的
            # 真实批量回测证据（quant.backtest_results）做报告性验证，不依赖已删除的
            # /api/backtest/batch 路由；无证据策略显式跳过，绝不编造 0 分 invalid。
            from application.services.strategy_validation_service import StrategyValidationService
            from adapters.outbound.repositories.strategy_repository import StrategyORMRepository
            from adapters.outbound.repositories.stock_repository import StockORMRepository

            service = StrategyValidationService(
                strategy_repo=StrategyORMRepository(),
                stock_repo=StockORMRepository(),
            )
            result = service.validate_from_recent_backtests(
                lookback_days=int(params.get('lookback_days', 30)),
                threshold=float(params.get('threshold', 60.0)),
                dry_run=bool(params.get('dry_run', False)),
            )

            return JobResult.ok(
                self.name,
                message=(
                    f"策略验证完成: {result['passed']} valid / {result['failed']} invalid "
                    f"(evidence={result['with_evidence']}, no_evidence_skipped={result['no_evidence']})"
                ),
                details={
                    "validated_count": result['with_evidence'],
                    "valid_count": result['passed'],
                    "invalid_count": result['failed'],
                    "no_evidence_skipped": result['no_evidence'],
                    "reports_written": result['reports_written'],
                    "dry_run": result['dry_run'],
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
            from infrastructure.jobs.market_style_update_job import execute as _run
            result = _run(**params)
            if not result.get('success'):
                return JobResult.fail(
                    self.name,
                    result.get('error') or f"执行失败: {result}",
                )
            return JobResult.ok(
                self.name,
                message=(
                    f"市场风格检测完成: {result.get('style')} "
                    f"(confidence={result.get('confidence')}, trade_date={result.get('trade_date')})"
                ),
                **result,
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
]
