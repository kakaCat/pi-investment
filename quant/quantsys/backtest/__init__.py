"""
回测引擎模块

提供事件驱动的回测引擎，支持:
- 涨跌停限制
- 停牌处理
- 滑点模型
- 交易成本计算
- 权益曲线生成
- 回测基线验证
"""

from .engine import BacktestEngine, Order, Trade, Position, DailyEquity
from .broker import SimulatedBroker
from .slippage import SlippageModel
from .portfolio import Portfolio
from .validator import (
    BacktestValidator,
    ValidatorConfig,
    ValidationResult,
    ValidationIssue,
    MarketRegime,
    DataQualityCheck,
    IssueSeverity
)

__all__ = [
    'BacktestEngine',
    'SimulatedBroker',
    'SlippageModel',
    'Portfolio',
    'Order',
    'Trade',
    'Position',
    'DailyEquity',
    'BacktestValidator',
    'ValidatorConfig',
    'ValidationResult',
    'ValidationIssue',
    'MarketRegime',
    'DataQualityCheck',
    'IssueSeverity',
]
