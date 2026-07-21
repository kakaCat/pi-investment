"""Multi-factor strategy — layered scoring model."""
from __future__ import annotations
from typing import Any

from domain.quantlib.engine.enhanced_strategy_base import EnhancedStrategyBase


class MultiFactorStrategy(EnhancedStrategyBase):
    """Multi-factor strategy with layered scoring.

    Default factor groups:
    - trend (MA family): 33.3%
    - momentum (RSI, MACD): 33.3%
    - volatility (ATR, Bollinger): 33.4%
    """

    DEFAULT_PARAMS = {
        'factor_groups': {
            'trend': ['ma5', 'ma10', 'ma20'],
            'momentum': ['rsi14', 'macd', 'macd_signal'],
            'volatility': ['atr14', 'bollinger_upper', 'bollinger_lower'],
        },
        'group_weights': [0.33, 0.33, 0.34],
        'buy_threshold': 0.60,
        'sell_threshold': 0.40,
    }

    PARAM_SCHEMA = {
        'factor_groups': {
            'type': 'object',
            'description': 'Factor group definitions {group_name: [factor_names]}',
        },
        'group_weights': {
            'type': 'array',
            'description': 'Weight per group, should sum to 1.0',
        },
        'buy_threshold': {
            'type': 'number', 'min': 0, 'max': 1, 'default': 0.6,
            'description': 'Score above which to generate buy signal',
        },
        'sell_threshold': {
            'type': 'number', 'min': 0, 'max': 1, 'default': 0.4,
            'description': 'Score below which to generate sell signal',
        },
    }

    def generate_signal(
        self, klines: list[dict], params: dict | None = None
    ) -> dict[str, Any]:
        self._validate_klines(klines, min_length=30)
        p = {**self.DEFAULT_PARAMS, **(params or {})}
        factor_groups: dict = p['factor_groups']
        group_weights: list = p['group_weights']
        buy_threshold: float = p['buy_threshold']
        sell_threshold: float = p['sell_threshold']

        all_factors = []
        for names in factor_groups.values():
            all_factors.extend(names)

        factor_values = self.calculate_factors(klines, all_factors)

        group_scores = []
        group_names = list(factor_groups.keys())
        for grp_name in group_names:
            fac_names = factor_groups[grp_name]
            score = self._score_group(factor_values, fac_names, klines)
            group_scores.append(score)

        final_score = sum(
            s * w for s, w in zip(group_scores, group_weights)
        )
        final_score = max(0.0, min(1.0, final_score))

        if final_score >= buy_threshold:
            return {
                'action': 'buy',
                'confidence': round(final_score, 4),
                'reason': (
                    f'Multi-factor score {final_score:.2f}>={buy_threshold} '
                    f'({dict(zip(group_names, [f"{s:.2f}" for s in group_scores]))})'
                ),
            }
        elif final_score <= sell_threshold:
            return {
                'action': 'sell',
                'confidence': round(1 - final_score, 4),
                'reason': (
                    f'Multi-factor score {final_score:.2f}<={sell_threshold} '
                    f'({dict(zip(group_names, [f"{s:.2f}" for s in group_scores]))})'
                ),
            }

        return {
            'action': 'hold', 'confidence': 0.0,
            'reason': f'Multi-factor score {final_score:.2f} — neutral',
        }

    def _score_group(
        self,
        factor_values: dict,
        factor_names: list[str],
        klines: list[dict],
    ) -> float:
        scores = []
        current_price = float(klines[-1]['close'])

        for name in factor_names:
            val = factor_values.get(name)
            if val is None:
                scores.append(0.5)
                continue

            if 'ma' in name.lower():
                ratio = current_price / max(val, 0.0001)
                scores.append(min(1.0, max(0.0, (ratio - 0.95) / 0.15)))
            elif 'rsi' in name.lower():
                scores.append(min(1.0, max(0.0, (val - 30) / 40)))
            elif 'macd' in name.lower() and 'signal' not in name.lower():
                signal_val = factor_values.get('macd_signal', 0) or 0
                diff = val - signal_val
                scores.append(min(1.0, max(0.0, (diff + 1) / 2)))
            elif 'bollinger' in name.lower():
                if 'upper' in name.lower() and val > 0:
                    scores.append(min(1.0, max(0.0, current_price / max(val, 0.0001))))
                elif 'lower' in name.lower() and val > 0:
                    scores.append(min(1.0, max(0.0,
                        1 - val / max(current_price, 0.0001))))
                else:
                    scores.append(0.5)
            elif 'atr' in name.lower():
                close = current_price
                high = float(klines[-1].get('high', close))
                ratio = val / max(close, 0.0001)
                scores.append(0.5 if ratio > 1 else 0.7)
            else:
                scores.append(0.5)

        return sum(scores) / len(scores) if scores else 0.5
