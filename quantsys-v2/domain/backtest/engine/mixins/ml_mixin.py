"""Mixin providing ML prediction integration.

DDD Architecture:
- Depends on IMLPredictor interface (optional)
- Application layer injects concrete implementation if needed

Updated 2026-06-26: 添加依赖注入支持
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MLMixin:
    """Mixin that gives strategies access to ML predictions.

    Supports two modes:
    - Precomputed: ``params['ml_prediction']`` already contains results.
    - Real-time: uses injected predictor or loads MLPredictor directly.
    """

    _predictor: Any = None

    def is_model_loaded(self) -> bool:
        return self._predictor is not None

    def load_ml_model(
        self,
        model_type: str = 'xgboost',
        version: str = 'latest',
        predictor: Optional[Any] = None
    ) -> None:
        """
        Load ML model for predictions.

        Args:
            model_type: Model type (for logging only)
            version: Model version (for logging only)
            predictor: ML predictor interface (must be injected by Application layer)

        Raises:
            ValueError: If predictor is not provided
        """
        if predictor is None:
            raise ValueError(
                "ML predictor must be injected by Application layer. "
                "Domain layer cannot create application services directly."
            )

        self._predictor = predictor
        logger.info("ML predictor loaded: %s/%s", model_type, version)

    def predict_ml(
        self,
        features: dict[str, float],
        use_precomputed: bool = False,
    ) -> dict[str, Any] | None:
        if use_precomputed:
            precomputed = features.get('ml_prediction')
            if precomputed is None:
                logger.debug("No precomputed ML prediction in params")
                return None
            return precomputed

        if self._predictor is None:
            raise ValueError(
                "Model not loaded. Call load_ml_model() first, "
                "or use precomputed mode."
            )
        return self._predictor.predict_single(features)
