"""
Backtrader Integration Module
==============================

Professional backtesting framework integration for quantsys-v2.

Provides:
- Data adapters (DataFrame → Backtrader)
- Strategy adapters (existing strategies → Backtrader)
- Backtest engine with parallel support
- Enhanced order matching and slippage models

Components:
- data_feed: PandasDataFeed for DataFrame integration
- strategy_adapter: Adapters for indicator and signal strategies
- backtrader_engine: Main backtest engine with parallel support
"""

from domain.quantlib.engine.backtrader.data_feed import PandasDataFeed
from domain.quantlib.engine.backtrader.strategy_adapter import (
    IndicatorStrategyAdapter,
    SignalStrategyAdapter
)
from domain.quantlib.engine.backtrader.backtrader_engine import BacktraderEngine

__all__ = [
    'PandasDataFeed',
    'IndicatorStrategyAdapter',
    'SignalStrategyAdapter',
    'BacktraderEngine'
]
