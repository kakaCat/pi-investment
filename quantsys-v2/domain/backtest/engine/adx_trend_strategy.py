"""ADX Trend Strength Strategy."""
from __future__ import annotations
from typing import Any

from domain.backtest.engine.enhanced_strategy_base import EnhancedStrategyBase


class ADXTrendStrategy(EnhancedStrategyBase):
    """ADX trend strength strategy.

    Uses ADX for trend strength + PLUS_DI/MINUS_DI for direction.
    ADX > threshold → strong trend → signal based on DI comparison.
    """

    DEFAULT_PARAMS = {
        'adx_threshold': 25,
        'adx_period': 14,
    }

    PARAM_SCHEMA = {
        'adx_threshold': {
            'type': 'number', 'min': 10, 'max': 60, 'default': 25,
            'description': 'ADX value above which trend is strong',
        },
        'adx_period': {
            'type': 'integer', 'min': 5, 'max': 50, 'default': 14,
            'description': 'Period for ADX calculation',
        },
    }

    def generate_signal(
        self, klines: list[dict], params: dict | None = None
    ) -> dict[str, Any]:
        p = {**self.DEFAULT_PARAMS, **(params or {})}
        adx_threshold: float = p['adx_threshold']
        adx_period: int = p['adx_period']

        min_required = adx_period * 2 + 1
        self._validate_klines(klines, min_length=min_required)

        indicators = self.calculate_batch_indicators(
            klines, ['ADX', 'PLUS_DI', 'MINUS_DI'],
        )

        adx = self._last_valid(indicators.get('ADX'))
        plus_di = self._last_valid(indicators.get('PLUS_DI'))
        minus_di = self._last_valid(indicators.get('MINUS_DI'))

        if adx is None:
            return {
                'action': 'hold', 'confidence': 0.0,
                'reason': 'ADX unavailable — insufficient data',
            }

        if adx < adx_threshold:
            return {
                'action': 'hold',
                'confidence': min(adx / 100, 0.3),
                'reason': f'Weak trend ADX={adx:.1f}<{adx_threshold}',
            }

        if plus_di is not None and minus_di is not None:
            if plus_di > minus_di:
                return {
                    'action': 'buy',
                    'confidence': min(adx / 50, 1.0),
                    'reason': (
                        f'Strong uptrend ADX={adx:.1f} '
                        f'+DI={plus_di:.1f}>-DI={minus_di:.1f}'
                    ),
                }
            else:
                return {
                    'action': 'sell',
                    'confidence': min(adx / 50, 1.0),
                    'reason': (
                        f'Strong downtrend ADX={adx:.1f} '
                        f'-DI={minus_di:.1f}>+DI={plus_di:.1f}'
                    ),
                }

        return {
            'action': 'hold', 'confidence': 0.0,
            'reason': f'ADX={adx:.1f} — unable to determine direction',
        }

    @staticmethod
    def _last_valid(values) -> float | None:
        if values is None:
            return None
        if hasattr(values, '__iter__') and not isinstance(values, str):
            for v in reversed(list(values)):
                if v is not None and v == v:  # not NaN
                    return float(v)
        return float(values) if values is not None else None
