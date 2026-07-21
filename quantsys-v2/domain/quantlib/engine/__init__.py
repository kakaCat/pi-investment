"""
Strategy Engine

策略引擎模块，提供策略抽象基类、内置策略实现、
策略组合器、策略运行器。

可用策略:
基础策略:
- MACrossStrategy: 均线交叉策略
- RSIReversalStrategy: RSI反转策略
- BollingerBreakoutStrategy: 布林带突破策略

高级策略:
- TurtleStrategy: 海龟交易策略（趋势跟踪）
- DonchianChannelStrategy: 唐奇安通道策略（趋势跟踪）
- MomentumStrategy: ROC动量策略（动量策略）
- BreakoutStrategy: 突破策略（价格+成交量确认）
- MeanReversionStrategy: 均值回归策略（震荡市）
- VolatilityBreakoutStrategy: ATR波动率突破策略
- PairsCorrelationStrategy: 配对交易策略（统计套利）

因子系统:
    from domain.quantlib.adapters import get_factor_adapter
    adapter = get_factor_adapter()
    value = adapter.calculate("ma5", klines)

使用方式:
    runner = StrategyRunner()
    signals = runner.run(symbol="000001.SZ", klines=klines)
"""

from domain.quantlib.engine.strategy_base import StrategyBase
from domain.quantlib.engine.ma_cross import MACrossStrategy
from domain.quantlib.engine.rsi_reversal import RSIReversalStrategy
from domain.quantlib.engine.bollinger_breakout import BollingerBreakoutStrategy
from domain.quantlib.engine.turtle_strategy import TurtleStrategy
from domain.quantlib.engine.donchian_channel_strategy import DonchianChannelStrategy
from domain.quantlib.engine.momentum_strategy import MomentumStrategy
from domain.quantlib.engine.breakout_strategy import BreakoutStrategy
from domain.quantlib.engine.mean_reversion_strategy import MeanReversionStrategy
from domain.quantlib.engine.volatility_breakout_strategy import VolatilityBreakoutStrategy
from domain.quantlib.engine.pairs_correlation_strategy import PairsCorrelationStrategy
from domain.quantlib.engine.strategy_combiner import StrategyCombiner
from domain.quantlib.engine.strategy_runner import StrategyRunner

# Risk rule engine
from domain.quantlib.engine.risk_rules import (
    check_position_size,
    check_portfolio_concentration,
    check_stop_loss,
    check_daily_drawdown,
    check_max_positions,
    check_blacklist,
    check_liquidity,
)

# Backtest engine components
from domain.quantlib.engine.slippage import (
    SlippageModel,
    FixedSlippage,
    ProportionalSlippage,
    MarketImpactSlippage,
    NoSlippage,
    create_slippage_model,
)
from domain.quantlib.engine.commission import (
    CommissionModel,
    AShareCommission,
    HKStockCommission,
    FixedCommission,
    ZeroCommission,
    TieredCommission,
    create_commission_model,
)
from domain.quantlib.engine.position_sizing import (
    PositionSizer,
    FixedPositionSizer,
    FixedPercentSizer,
    KellyPositionSizer,
    RiskParitySizer,
    VolatilityTargetSizer,
    create_position_sizer,
)
from domain.quantlib.engine.backtest_report import (
    BacktestReportGenerator,
    PerformanceMetrics,
)

# New imports — Strategy Extension Phase 2
from domain.quantlib.engine.enhanced_strategy_base import EnhancedStrategyBase
from domain.quantlib.engine.multi_factor_strategy import MultiFactorStrategy
from domain.quantlib.engine.ml_prediction_strategy import MLPredictionStrategy
from domain.quantlib.engine.adx_trend_strategy import ADXTrendStrategy
from domain.quantlib.engine.cci_reversal_strategy import CCIReversalStrategy
from domain.quantlib.engine.grid_trading_strategy import GridTradingStrategy
from domain.quantlib.engine.strategy_factory import StrategyFactory
# from domain.quantlib.engine.ensemble_vote_strategy import EnsembleVoteStrategy  # TODO: File not yet implemented
from domain.quantlib.engine.pe_momentum_ma60_strategy import PEMomentumMA60Strategy
from domain.quantlib.engine.indicators.indicator_manager import IndicatorManager
from domain.quantlib.engine.mixins.indicator_mixin import IndicatorMixin
from domain.quantlib.engine.mixins.factor_mixin import FactorMixin
from domain.quantlib.engine.mixins.ml_mixin import MLMixin

__all__ = [
    'StrategyBase',
    # Basic strategies
    'MACrossStrategy',
    'RSIReversalStrategy',
    'BollingerBreakoutStrategy',
    # Advanced strategies
    'TurtleStrategy',
    'DonchianChannelStrategy',
    'MomentumStrategy',
    'BreakoutStrategy',
    'MeanReversionStrategy',
    'VolatilityBreakoutStrategy',
    'PairsCorrelationStrategy',
    # Strategy tools
    'StrategyCombiner',
    'StrategyRunner',
    # Risk rules
    'check_position_size',
    'check_portfolio_concentration',
    'check_stop_loss',
    'check_daily_drawdown',
    'check_max_positions',
    'check_blacklist',
    'check_liquidity',
    # Backtest engine - Slippage
    'SlippageModel',
    'FixedSlippage',
    'ProportionalSlippage',
    'MarketImpactSlippage',
    'NoSlippage',
    'create_slippage_model',
    # Backtest engine - Commission
    'CommissionModel',
    'AShareCommission',
    'HKStockCommission',
    'FixedCommission',
    'ZeroCommission',
    'TieredCommission',
    'create_commission_model',
    # Backtest engine - Position sizing
    'PositionSizer',
    'FixedPositionSizer',
    'FixedPercentSizer',
    'KellyPositionSizer',
    'RiskParitySizer',
    'VolatilityTargetSizer',
    'create_position_sizer',
    # Backtest engine - Reporting
    'BacktestReportGenerator',
    'PerformanceMetrics',
    # Strategy extension
    'EnhancedStrategyBase',
    'MultiFactorStrategy',
    'MLPredictionStrategy',
    'ADXTrendStrategy',
    'CCIReversalStrategy',
    'GridTradingStrategy',
    'StrategyFactory',
    'EnsembleVoteStrategy',
    'PEMomentumMA60Strategy',
    'IndicatorManager',
    'IndicatorMixin',
    'FactorMixin',
    'MLMixin',
]
