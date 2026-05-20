"""
策略模块

提供各种量化策略实现
"""

from .base import BaseStrategy
from .classic.ma_cross import MACrossStrategy

__all__ = [
    'BaseStrategy',
    'MACrossStrategy',
]
