"""
Classic trading strategies.
"""
from .ma_cross import MACrossStrategy
from .rsi_reversal import RSIReversalStrategy
from .bollinger_breakout import BollingerBreakoutStrategy

__all__ = [
    'MACrossStrategy',
    'RSIReversalStrategy',
    'BollingerBreakoutStrategy'
]
