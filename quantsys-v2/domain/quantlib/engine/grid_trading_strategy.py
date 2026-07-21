"""Grid Trading Strategy — range-bound market strategy."""
from __future__ import annotations
from typing import Any

from domain.quantlib.engine.enhanced_strategy_base import EnhancedStrategyBase


class GridTradingStrategy(EnhancedStrategyBase):
    """Grid trading for range-bound markets.

    Divides a price range into grid levels. Buys near lower grid lines,
    sells near upper grid lines.
    """

    DEFAULT_PARAMS = {
        'grid_count': 10,
        'price_range': 'auto',
        'atr_multiplier': 2.0,
        'atr_period': 14,
        'trigger_zone': 0.2,
    }

    PARAM_SCHEMA = {
        'grid_count': {
            'type': 'integer', 'min': 3, 'max': 100, 'default': 10,
            'description': 'Number of grid levels',
        },
        'price_range': {
            'type': 'string_or_array',
            'description': "'auto' for ATR-based, or [lower, upper] fixed",
        },
        'atr_multiplier': {
            'type': 'number', 'min': 0.5, 'max': 5.0, 'default': 2.0,
            'description': 'ATR multiplier for auto range',
        },
    }

    def generate_signal(
        self, klines: list[dict], params: dict | None = None
    ) -> dict[str, Any]:
        p = {**self.DEFAULT_PARAMS, **(params or {})}
        grid_count: int = p['grid_count']
        price_range = p['price_range']
        atr_multiplier: float = p['atr_multiplier']
        atr_period: int = p['atr_period']
        trigger_zone: float = p['trigger_zone']

        self._validate_klines(klines, min_length=atr_period + 1)
        current_price = float(klines[-1]['close'])

        if price_range == 'auto':
            atr_vals = self.calculate_indicator(
                klines, 'ATR', length=atr_period,
            )
            atr = self._last_valid(atr_vals)
            if atr is None:
                return {
                    'action': 'hold', 'confidence': 0.0,
                    'reason': 'ATR unavailable for grid',
                }
            lower_bound = current_price - atr * atr_multiplier
            upper_bound = current_price + atr * atr_multiplier
        else:
            lower_bound, upper_bound = float(price_range[0]), float(price_range[1])

        if lower_bound >= upper_bound:
            return {
                'action': 'hold', 'confidence': 0.0,
                'reason': 'Invalid price range',
            }

        grid_size = (upper_bound - lower_bound) / grid_count
        current_grid = max(0, min(
            grid_count - 1,
            int((current_price - lower_bound) / grid_size),
        ))

        grid_low = lower_bound + current_grid * grid_size
        grid_high = grid_low + grid_size
        pos_in_grid = (
            (current_price - grid_low) / grid_size if grid_size > 0 else 0.5
        )

        if pos_in_grid <= trigger_zone:
            return {
                'action': 'buy', 'confidence': 0.7,
                'reason': (
                    f'Grid #{current_grid+1}/{grid_count}: '
                    f'{current_price:.2f} near lower {grid_low:.2f} ({pos_in_grid:.0%})'
                ),
            }
        elif pos_in_grid >= (1 - trigger_zone):
            return {
                'action': 'sell', 'confidence': 0.7,
                'reason': (
                    f'Grid #{current_grid+1}/{grid_count}: '
                    f'{current_price:.2f} near upper {grid_high:.2f} ({pos_in_grid:.0%})'
                ),
            }

        return {
            'action': 'hold', 'confidence': 0.0,
            'reason': (
                f'Grid #{current_grid+1}/{grid_count}: mid-range {pos_in_grid:.0%}, '
                f'[{grid_low:.2f},{grid_high:.2f}]'
            ),
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
