"""
ORM Repository模块

包含所有ORM Repository的统一导出

完全迁移状态：✅ 已完成
"""

# 批次1（核心）✅
from .stock_repository import StockORMRepository
from .kline_repository import KlineORMRepository
from .signal_repository import SignalORMRepository
from .simulation_repository import SimulationORMRepository

# 批次2（关键业务）✅
from .portfolio_repository import PortfolioORMRepository
from .factor_repository import FactorORMRepository
from .backtest_repository import BacktestORMRepository

# 批次3（新增 - 完全迁移）✅
from .signal_execution_repository import SignalExecutionORMRepository
from .risk_repository import RiskORMRepository
from .strategy_repository import StrategyORMRepository
from .financial_repository import FinancialORMRepository
from .stock_pool_repository import StockPoolRepository, StockPoolORMRepository
from .position_repository import PositionORMRepository
from .risk_config_repository import RiskConfigORMRepository
from .strategy_performance_repository import StrategyPerformanceRepository, StrategyPerformanceORMRepository
from .fund_flow_repository import FundFlowORMRepository
FundFlowRepository = FundFlowORMRepository  # 旧名兼容（enhanced_risk_assessor/pool_health_tracker 在用）
from .market_style_repository import MarketStyleORMRepository
from .data_quality_repository import DataQualityORMRepository
from .ml_model_repository import MlModelORMRepository
from .strategy_circuit_breaker_repository import StrategyCircuitBreakerORMRepository
from .strategy_weight_repository import StrategyWeightORMRepository
from .traceability_repository import TraceabilityORMRepository
from .agent_intelligence_repository import AgentIntelligenceORMRepository, AgentDecisionRepository
from .pool_change_log_repository import PoolChangeLogRepository
from .signal_execution_log_repository import SignalExecutionLogORMRepository
from .async_factor_repository import AsyncFactorORMRepository

# 批次4（调度器和监控）✅
from .scheduler_config_repository import SchedulerConfigORMRepository
from .condition_rule_repository import ConditionRuleORMRepository, ConditionResultORMRepository

__all__ = [
    # 批次1（核心）
    'StockORMRepository',
    'KlineORMRepository',
    'SignalORMRepository',
    'SimulationORMRepository',

    # 批次2（关键业务）
    'PortfolioORMRepository',
    'FactorORMRepository',
    'BacktestORMRepository',

    # 批次3（新增 - 完全迁移）
    'SignalExecutionORMRepository',
    'RiskORMRepository',
    'StrategyORMRepository',
    'FinancialORMRepository',
    'StockPoolRepository',
    'StockPoolORMRepository',
    'PositionORMRepository',
    'RiskConfigORMRepository',
    'StrategyPerformanceRepository',
    'StrategyPerformanceORMRepository',
    'FundFlowORMRepository',
    'FundFlowRepository',
    'MarketStyleORMRepository',
    'DataQualityORMRepository',
    'MlModelORMRepository',
    'StrategyCircuitBreakerORMRepository',
    'StrategyWeightORMRepository',
    'TraceabilityORMRepository',
    'AgentIntelligenceORMRepository',
    'AgentDecisionRepository',
    'PoolChangeLogRepository',
    'SignalExecutionLogORMRepository',
    'AsyncFactorORMRepository',

    # 批次4（调度器和监控）
    'SchedulerConfigORMRepository',
    'ConditionRuleORMRepository',
    'ConditionResultORMRepository',
]
