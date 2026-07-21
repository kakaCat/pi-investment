"""CCI Reversal Strategy — overbought/oversold mean reversion."""
from __future__ import annotations
from typing import Any

from domain.quantlib.engine.enhanced_strategy_base import EnhancedStrategyBase


class CCIReversalStrategy(EnhancedStrategyBase):
    """CCI (Commodity Channel Index) reversal strategy.

    CCI > +100 → overbought → sell.
    CCI < -100 → oversold → buy.
    """

    DEFAULT_PARAMS = {
        'cci_period': 20,
        'overbought': 100,
        'oversold': -100,
    }

    PARAM_SCHEMA = {
        'cci_period': {
            'type': 'integer', 'min': 5, 'max': 50, 'default': 20,
            'description': 'Period for CCI calculation',
        },
        'overbought': {
            'type': 'number', 'min': 50, 'max': 300, 'default': 100,
            'description': 'CCI value above which is overbought',
        },
        'oversold': {
            'type': 'number', 'min': -300, 'max': -50, 'default': -100,
            'description': 'CCI value below which is oversold',
        },
    }

    def generate_signal(
        self, klines: list[dict], params: dict | None = None
    ) -> dict[str, Any]:
        p = {**self.DEFAULT_PARAMS, **(params or {})}
        cci_period: int = p['cci_period']
        overbought: float = p['overbought']
        oversold: float = p['oversold']

        self._validate_klines(klines, min_length=cci_period * 2 + 1)

        cci_values = self.calculate_indicator(
            klines, 'CCI', length=cci_period,
        )

        current_cci = self._last_valid(cci_values)
        if current_cci is None:
            return {
                'action': 'hold', 'confidence': 0.0,
                'reason': 'CCI unavailable',
            }

        if current_cci < oversold:
            confidence = min(abs(current_cci) / 200, 1.0)
            return {
                'action': 'buy',
                'confidence': round(confidence, 4),
                'reason': f'CCI oversold {current_cci:.1f}<{oversold}',
            }
        elif current_cci > overbought:
            confidence = min(current_cci / 200, 1.0)
            return {
                'action': 'sell',
                'confidence': round(confidence, 4),
                'reason': f'CCI overbought {current_cci:.1f}>{overbought}',
            }

        return {
            'action': 'hold', 'confidence': 0.0,
            'reason': f'CCI neutral {current_cci:.1f} in [{oversold},{overbought}]',
        }

    @staticmethod
    def _last_valid(values) -> float | None:
        if values is None:
            return None
        if hasattr(values, '__iter__') and not isinstance(values, str):
            for v in reversed(list(values)):
                if v is not None and v == v:
                    return float(v)
        return float(values) if values is not None else None
