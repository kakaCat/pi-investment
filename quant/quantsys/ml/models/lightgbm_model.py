"""
LightGBM model wrapper.
"""
import numpy as np
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class LightGBMModel:
    """
    LightGBM classifier wrapper with best practices.
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        Args:
            params: LightGBM parameters
        """
        try:
            import lightgbm as lgb
            self.lgb = lgb
        except ImportError:
            raise ImportError("lightgbm not installed. Run: pip install lightgbm")

        self.params = params or self._get_default_params()
        self.model = None

    def _get_default_params(self) -> Dict[str, Any]:
        """Get default LightGBM parameters."""
        return {
            'num_leaves': 31,
            'n_estimators': 100,
            'learning_rate': 0.1,
            'min_child_samples': 20,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'reg_alpha': 0.1,
            'reg_lambda': 1.0,
            'random_state': 42,
            'n_jobs': -1,
            'verbose': -1
        }

    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict[str, Any]:
        """
        Train LightGBM model.

        Args:
            X_train: Training features
            y_train: Training labels

        Returns:
            Training report
        """
        logger.info(f"Training LightGBM with params: {self.params}")

        self.model = self.lgb.LGBMClassifier(**self.params)
        self.model.fit(X_train, y_train)

        return {
            'success': True,
            'model_type': 'lightgbm',
            'n_features': X_train.shape[1],
            'n_samples': len(X_train)
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class labels."""
        if self.model is None:
            raise ValueError("Model not trained")

        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities."""
        if self.model is None:
            raise ValueError("Model not trained")

        return self.model.predict_proba(X)

    def get_feature_importance(self) -> np.ndarray:
        """Get feature importance scores."""
        if self.model is None:
            raise ValueError("Model not trained")

        return self.model.feature_importances_

    def get_params(self) -> Dict[str, Any]:
        """Get model parameters."""
        return self.params

    def set_params(self, params: Dict[str, Any]):
        """Set model parameters."""
        self.params.update(params)
        if self.model is not None:
            self.model.set_params(**self.params)
