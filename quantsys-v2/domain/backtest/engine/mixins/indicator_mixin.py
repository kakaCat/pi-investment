"""Mixin providing indicator calculation via IndicatorManager."""
from __future__ import annotations
from typing import Any

from domain.backtest.engine.indicators.indicator_manager import IndicatorManager


class IndicatorMixin:
    """Mixin that gives strategies access to technical indicators.

    Uses IndicatorManager for auto-fallback between TA-Lib and pandas-ta.
    """

    _indicator_manager: IndicatorManager | None = None

    @property
    def indicator_manager(self) -> IndicatorManager:
        if self._indicator_manager is None:
            self._indicator_manager = IndicatorManager()
        return self._indicator_manager

    def calculate_indicator(
        self, klines: list[dict], indicator: str, **params
    ) -> Any:
        return self.indicator_manager.calculate(klines, indicator, **params)

    def calculate_batch_indicators(
        self, klines: list[dict], indicator_names: list[str]
    ) -> dict[str, Any]:
        batch = {}
        for name in indicator_names:
            params = self._default_params_for(name)
            batch[name] = params
        return self.indicator_manager.calculate_batch(klines, batch)

    @staticmethod
    def _default_params_for(indicator: str) -> dict:
        defaults = {
            'SMA': {'length': 20}, 'EMA': {'length': 20},
            'RSI': {'length': 14}, 'ADX': {'length': 14},
            'CCI': {'length': 20}, 'ATR': {'length': 14},
            'MACD': {'fast': 12, 'slow': 26, 'signal': 9},
            'BBANDS': {'length': 20, 'std': 2},
        }
        return defaults.get(indicator, {'length': 14})
