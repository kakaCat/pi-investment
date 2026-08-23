"""ML Prediction Strategy — XGBoost-based signal generation."""
from __future__ import annotations
from typing import Any

from domain.backtest.engine.enhanced_strategy_base import EnhancedStrategyBase
from domain.backtest.engine.mixins.ml_mixin import MLMixin


class MLPredictionStrategy(EnhancedStrategyBase, MLMixin):
    """Strategy using ML model predictions for signals.

    Supports precomputed (default) and real-time modes.
    """

    DEFAULT_PARAMS = {
        'use_precomputed': True,
        'confidence_threshold': 0.6,
        'model_type': 'xgboost',
        'model_version': 'latest',
    }

    PARAM_SCHEMA = {
        'use_precomputed': {
            'type': 'boolean', 'default': True,
            'description': 'Use precomputed ML results from params',
        },
        'confidence_threshold': {
            'type': 'number', 'min': 0.5, 'max': 0.95, 'default': 0.6,
            'description': 'Minimum confidence to generate buy signal',
        },
    }

    def generate_signal(
        self, klines: list[dict], params: dict | None = None
    ) -> dict[str, Any]:
        p = {**self.DEFAULT_PARAMS, **(params or {})}
        use_precomputed: bool = p['use_precomputed']
        confidence_threshold: float = p['confidence_threshold']

        self._validate_klines(klines, min_length=10)

        if use_precomputed:
            ml_result = p.get('ml_prediction')
        else:
            if not self.is_model_loaded():
                self.load_ml_model(
                    model_type=p.get('model_type', 'xgboost'),
                    version=p.get('model_version', 'latest'),
                )
            features = self._extract_features_from_klines(klines)
            ml_result = self.predict_ml(features, use_precomputed=False)

        if ml_result is None:
            return {
                'action': 'hold', 'confidence': 0.0,
                'reason': 'No ML prediction available',
            }

        signal = ml_result.get('signal', 'HOLD')
        confidence = ml_result.get('confidence', 0.0)

        if signal == 'BUY' and confidence >= confidence_threshold:
            return {
                'action': 'buy',
                'confidence': round(float(confidence), 4),
                'reason': (
                    f'ML预测买入 (confidence: {confidence:.2%}, '
                    f'threshold: {confidence_threshold:.0%})'
                ),
            }

        return {
            'action': 'hold', 'confidence': 0.0,
            'reason': (
                f'ML confidence {confidence:.2%} below '
                f'threshold {confidence_threshold:.0%}'
            ),
        }

    def _extract_features_from_klines(
        self, klines: list[dict]
    ) -> dict[str, float]:
        factors = self.calculate_factors(klines)
        return {
            k: float(v) if v is not None else 0.0
            for k, v in factors.items()
        }
