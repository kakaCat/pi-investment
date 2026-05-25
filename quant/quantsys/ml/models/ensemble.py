"""
Model ensemble using stacking.
"""
import numpy as np
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class EnsembleModel:
    """
    Ensemble model using stacking with multiple base models.

    Combines XGBoost, LightGBM, and RandomForest with a meta-model.
    """

    def __init__(
        self,
        base_models: Optional[List[Any]] = None,
        meta_model: Optional[Any] = None
    ):
        """
        Args:
            base_models: List of base models (if None, uses default ensemble)
            meta_model: Meta-model for stacking (if None, uses LogisticRegression)
        """
        self.base_models = base_models
        self.meta_model = meta_model
        self.trained = False

    def _create_default_base_models(self) -> List[Any]:
        """Create default base models."""
        import xgboost as xgb
        from sklearn.ensemble import RandomForestClassifier

        models = [
            xgb.XGBClassifier(
                max_depth=5,
                n_estimators=100,
                learning_rate=0.1,
                random_state=42
            ),
            RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
        ]

        # Try to add LightGBM if available
        try:
            import lightgbm as lgb
            models.append(
                lgb.LGBMClassifier(
                    num_leaves=31,
                    n_estimators=100,
                    learning_rate=0.1,
                    random_state=42,
                    verbose=-1
                )
            )
        except ImportError:
            logger.warning("LightGBM not available, using XGBoost and RandomForest only")

        return models

    def _create_default_meta_model(self) -> Any:
        """Create default meta-model."""
        from sklearn.linear_model import LogisticRegression

        return LogisticRegression(random_state=42, max_iter=1000)

    def train(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict[str, Any]:
        """
        Train ensemble model using stacking.

        Args:
            X_train: Training features
            y_train: Training labels

        Returns:
            Training report
        """
        from sklearn.model_selection import cross_val_predict, TimeSeriesSplit

        logger.info("Training ensemble model with stacking...")

        # Initialize models if not provided
        if self.base_models is None:
            self.base_models = self._create_default_base_models()

        if self.meta_model is None:
            self.meta_model = self._create_default_meta_model()

        # Step 1: Train base models and generate meta-features
        logger.info(f"Training {len(self.base_models)} base models...")

        meta_features = np.zeros((len(X_train), len(self.base_models)))
        tscv = TimeSeriesSplit(n_splits=5)

        for i, model in enumerate(self.base_models):
            logger.info(f"Training base model {i+1}/{len(self.base_models)}: {type(model).__name__}")

            # Generate out-of-fold predictions for meta-features
            meta_features[:, i] = cross_val_predict(
                model, X_train, y_train,
                cv=tscv,
                method='predict_proba',
                n_jobs=1
            )[:, 1]

            # Train on full training set
            model.fit(X_train, y_train)

        # Step 2: Train meta-model on meta-features
        logger.info("Training meta-model...")
        self.meta_model.fit(meta_features, y_train)

        self.trained = True

        return {
            'success': True,
            'model_type': 'ensemble',
            'n_base_models': len(self.base_models),
            'base_model_types': [type(m).__name__ for m in self.base_models],
            'meta_model_type': type(self.meta_model).__name__,
            'n_features': X_train.shape[1],
            'n_samples': len(X_train)
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class labels."""
        if not self.trained:
            raise ValueError("Model not trained")

        # Generate meta-features from base models
        meta_features = self._generate_meta_features(X)

        # Predict using meta-model
        return self.meta_model.predict(meta_features)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities."""
        if not self.trained:
            raise ValueError("Model not trained")

        # Generate meta-features from base models
        meta_features = self._generate_meta_features(X)

        # Predict using meta-model
        return self.meta_model.predict_proba(meta_features)

    def _generate_meta_features(self, X: np.ndarray) -> np.ndarray:
        """Generate meta-features from base model predictions."""
        meta_features = np.zeros((len(X), len(self.base_models)))

        for i, model in enumerate(self.base_models):
            meta_features[:, i] = model.predict_proba(X)[:, 1]

        return meta_features

    def get_base_model_predictions(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """Get predictions from each base model."""
        if not self.trained:
            raise ValueError("Model not trained")

        predictions = {}

        for i, model in enumerate(self.base_models):
            model_name = f"{type(model).__name__}_{i}"
            predictions[model_name] = model.predict_proba(X)[:, 1]

        return predictions
