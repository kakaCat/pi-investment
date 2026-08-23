"""TA-Lib indicator adapter (optional, requires C compilation)."""
from __future__ import annotations

import numpy as np

from domain.backtest.engine.indicators.base import IndicatorAdapter


class TALibAdapter(IndicatorAdapter):
    """Adapter for TA-Lib (150+ indicators, C-backed, fastest)."""

    _INDICATORS = [
        'SMA', 'EMA', 'RSI', 'ADX', 'CCI', 'MACD', 'BBANDS',
        'ATR', 'STOCH', 'WILLR', 'MFI', 'ROC', 'OBV',
        'PLUS_DI', 'MINUS_DI', 'AD', 'ADOSC', 'NATR',
        'SAR', 'ULTOSC', 'TRIX', 'DX', 'STOCHRSI',
    ]

    def is_available(self) -> bool:
        try:
            import talib  # noqa: F401
            return True
        except ImportError:
            return False

    def list_indicators(self) -> list[str]:
        return list(self._INDICATORS)

    def calculate(
        self, klines: list[dict], indicator: str, **params
    ) -> list[float] | None:
        if not self.is_available():
            return None

        import talib

        closes = np.array([float(k['close']) for k in klines])
        highs = np.array([float(k['high']) for k in klines])
        lows = np.array([float(k['low']) for k in klines])
        # 处理NULL volume：使用0填充
        volumes = np.array(
            [float(k.get('volume') or 0) for k in klines], dtype=np.float64
        )

        func_name = indicator.upper()
        func = getattr(talib, func_name, None)
        if func is None:
            return None

        timeperiod = params.get('timeperiod', params.get('length', 14))

        try:
            if func_name in ('SMA', 'EMA', 'RSI'):
                result = func(closes, timeperiod=timeperiod)
            elif func_name == 'MACD':
                result = func(
                    closes,
                    fastperiod=params.get('fast', 12),
                    slowperiod=params.get('slow', 26),
                    signalperiod=params.get('signal', 9),
                )
            elif func_name == 'BBANDS':
                upper, middle, lower = func(
                    closes, timeperiod=timeperiod,
                    nbdevup=params.get('std', 2),
                    nbdevdn=params.get('std', 2),
                )
                return {
                    'upper': upper.tolist(),
                    'middle': middle.tolist(),
                    'lower': lower.tolist(),
                }
            elif func_name in ('ADX', 'CCI', 'ATR', 'NATR', 'DX',
                               'PLUS_DI', 'MINUS_DI'):
                result = func(highs, lows, closes, timeperiod=timeperiod)
            elif func_name in ('MFI', 'WILLR', 'ROC'):
                result = func(highs, lows, closes, timeperiod=timeperiod)
            elif func_name == 'SAR':
                result = func(highs, lows)
            elif func_name == 'OBV':
                result = func(closes, volumes)
            else:
                result = func(closes, timeperiod=timeperiod)
        except Exception:
            return None

        if hasattr(result, 'tolist'):
            result = result.tolist()
        return result
