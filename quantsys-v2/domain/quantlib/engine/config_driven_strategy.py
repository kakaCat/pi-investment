"""Config-Driven Strategy — database-defined, no code file needed."""
from __future__ import annotations
from typing import Any

from domain.quantlib.engine.enhanced_strategy_base import EnhancedStrategyBase


class ConfigDrivenStrategy(EnhancedStrategyBase):
    """Strategy defined entirely by database configuration — no code file required.

    Configure via ``quant.strategy_configs.parameters``:

    .. code-block:: json

        {
          "indicators": {
            "sma20": {"name": "SMA", "length": 20},
            "rsi14":  {"name": "RSI", "length": 14}
          },
          "rules": [
            {
              "condition": "close > sma20 AND rsi14 < 30",
              "action": "buy",
              "confidence": 0.8
            },
            {
              "condition": "close < sma20 AND rsi14 > 70",
              "action": "sell",
              "confidence": 0.8
            }
          ]
        }

    Supported operators in conditions: ``>``, ``>=``, ``<``, ``<=``, ``==``,
    ``!=``, ``AND``, ``OR``.

    Available variables in conditions: ``close``, ``high``, ``low``, ``open``,
    ``volume``, plus any indicator alias defined in the ``indicators`` section.
    """

    DEFAULT_PARAMS = {
        'indicators': {},
        'rules': [],
    }

    PARAM_SCHEMA = {
        'indicators': {
            'type': 'object',
            'description': 'Indicators to calculate: {alias: {name, ...params}}',
        },
        'rules': {
            'type': 'array',
            'description': 'Ordered rule list: [{condition, action, confidence}]',
        },
    }

    # ------------------------------------------------------------------
    # generate_signal
    # ------------------------------------------------------------------

    def generate_signal(
        self, klines: list[dict], params: dict | None = None
    ) -> dict[str, Any]:
        self._validate_klines(klines, min_length=10)
        p = {**self.DEFAULT_PARAMS, **(params or {})}
        indicators: dict = p.get('indicators', {})
        rules: list = p.get('rules', [])

        # 1. Calculate all configured indicators
        values: dict[str, float] = {}
        for alias, ind_config in indicators.items():
            name = ind_config['name']
            ind_params = {k: v for k, v in ind_config.items() if k != 'name'}
            result = self.calculate_indicator(klines, name, **ind_params)
            last = self._extract_last(result)
            if last is not None:
                values[alias] = last

        # 2. Add OHLCV values
        latest = klines[-1]
        values['close'] = float(latest.get('close', 0))
        values['high'] = float(latest.get('high', values['close']))
        values['low'] = float(latest.get('low', values['close']))
        values['open'] = float(latest.get('open', values['close']))
        values['volume'] = float(latest.get('volume', 0))

        # 3. Evaluate rules in priority order
        for rule in rules:
            condition = rule.get('condition', '')
            try:
                if self._eval_condition(condition, values):
                    return {
                        'action': rule['action'],
                        'confidence': float(rule.get('confidence', 0.5)),
                        'reason': f"Rule matched: {condition} (values: {self._format_matches(condition, values)})",
                    }
            except Exception:
                continue

        return {
            'action': 'hold',
            'confidence': 0.0,
            'reason': 'No rule matched',
        }

    # ------------------------------------------------------------------
    # Condition evaluator (safe, no eval)
    # ------------------------------------------------------------------

    _OPS = {'>', '>=', '<', '<=', '==', '!='}

    def _eval_condition(self, condition: str, values: dict[str, float]) -> bool:
        """Evaluate a condition string safely — no exec/eval."""
        condition = condition.strip()

        # Handle OR
        if ' OR ' in condition:
            left, right = condition.split(' OR ', 1)
            return self._eval_condition(left, values) or self._eval_condition(right, values)

        # Handle AND
        if ' AND ' in condition:
            left, right = condition.split(' AND ', 1)
            return self._eval_condition(left, values) and self._eval_condition(right, values)

        # Handle single comparison: "left OP right"
        for op in ('>=', '<=', '!=', '==', '>', '<'):
            if f' {op} ' in condition:
                left_str, right_str = condition.split(f' {op} ', 1)
                left = self._resolve_value(left_str.strip(), values)
                right = self._resolve_value(right_str.strip(), values)
                if left is None or right is None:
                    return False
                if op == '>':
                    return left > right
                elif op == '>=':
                    return left >= right
                elif op == '<':
                    return left < right
                elif op == '<=':
                    return left <= right
                elif op == '==':
                    return left == right
                elif op == '!=':
                    return left != right

        # Single token — truthiness check
        val = self._resolve_value(condition, values)
        return bool(val) if val is not None else False

    def _resolve_value(self, token: str, values: dict[str, float]) -> float | None:
        """Resolve a token: indicator alias, OHLCV field, or numeric literal."""
        token = token.strip()
        # Numeric literal
        try:
            return float(token)
        except (ValueError, TypeError):
            pass
        # Dictionary lookup
        return values.get(token)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_last(result) -> float | None:
        if result is None:
            return None
        if hasattr(result, '__iter__') and not isinstance(result, str):
            for v in reversed(list(result)):
                if v is not None and v == v:  # not NaN
                    return float(v)
            return None
        try:
            return float(result)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _format_matches(condition: str, values: dict[str, float]) -> str:
        """Format the matched condition with actual values for traceability."""
        parts = []
        for token in condition.replace('(', '').replace(')', '').split():
            if token in ('AND', 'OR', '>', '>=', '<', '<=', '==', '!='):
                parts.append(token)
            elif token in values:
                parts.append(f"{token}={values[token]:.2f}")
            else:
                parts.append(token)
        return ' '.join(parts)
