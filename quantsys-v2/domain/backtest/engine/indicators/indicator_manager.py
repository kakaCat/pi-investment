"""Unified indicator manager with auto-fallback (Custom → TA-Lib → pandas-ta)."""
from __future__ import annotations
import logging
from typing import Any

from domain.backtest.engine.indicators.custom_adapter import CustomIndicatorAdapter
from domain.backtest.engine.indicators.talib_adapter import TALibAdapter
from domain.backtest.engine.indicators.pandasta_adapter import PandasTAAdapter

logger = logging.getLogger(__name__)


class IndicatorManager:
    """Manages indicator calculation with automatic library fallback.

    Precedence: Custom → TA-Lib → pandas-ta → error

    Usage::

        manager = IndicatorManager()
        adx = manager.calculate(klines, 'ADX', length=14)
        batch = manager.calculate_batch(klines, {'SMA': {'length': 20}})
    """

    def __init__(self):
        self.adapters = []
        # Custom adapter (highest priority, always available)
        custom = CustomIndicatorAdapter()
        self.adapters.append(custom)
        logger.info("IndicatorManager: Custom adapter available")

        talib = TALibAdapter()
        if talib.is_available():
            self.adapters.append(talib)
            logger.info("IndicatorManager: TA-Lib available")
        pta = PandasTAAdapter()
        if pta.is_available():
            self.adapters.append(pta)
            logger.info("IndicatorManager: pandas-ta available")
        if len(self.adapters) == 1:  # Only custom adapter
            logger.warning(
                "IndicatorManager: no indicator library available. "
                "Install TA-Lib or pandas-ta."
            )

    def calculate(
        self, klines: list[dict], indicator: str, **params
    ) -> Any:
        if not self.adapters:
            raise RuntimeError(
                "No indicator library available. "
                "Install TA-Lib or pandas-ta."
            )
        for adapter in self.adapters:
            if not adapter.is_available():
                continue
            try:
                result = adapter.calculate(klines, indicator, **params)
                if result is not None:
                    return result
            except Exception as e:
                logger.debug(
                    "Adapter %s failed for %s: %s",
                    type(adapter).__name__, indicator, e,
                )
        logger.warning("All adapters failed for indicator '%s'", indicator)
        return None

    def calculate_batch(
        self,
        klines: list[dict],
        indicators: dict[str, dict],
    ) -> dict[str, Any]:
        results = {}
        for name, params in indicators.items():
            results[name] = self.calculate(klines, name, **params)
        return results
