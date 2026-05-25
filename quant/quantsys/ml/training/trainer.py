"""
Unified training framework for ML models with proper validation.
"""
import os
import json
import pickle
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

from .cross_validation import TimeSeriesCV, print_cv_results
from .hyperparameter_tuning import HyperparameterTuner

logger = logging.getLogger(__name__)


class ModelTrainer:
    """
    Training framework with time series CV, hyperparameter tuning, and proper validation.
    """

    def __init__(
        self,
        model_type: str = 'xgboost',
        tune_hyperparams: bool = False,
        n_trials: int = 50,
        cv_splits: int = 5
    ):
        """
        Args:
            model_type: 'xgboost', 'lightgbm', or 'ensemble'
            tune_hyperparams: Whether to tune hyperparameters
            n_trials: Number of tuning trials
            cv_splits: Number of CV splits
        """
        self.model_type = model_type
        self.tune_hyperparams = tune_hyperparams
        self.n_trials = n_trials
        self.cv_splits = cv_splits
        self.model = None
        self.best_params = None
        self.cv_results = None

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        model_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Train model with proper time series validation.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target labels (n_samples,)
            model_params: Optional model parameters (if not tuning)

        Returns:
            Training report with metrics
        """
        logger.info(f"Training {self.model_type} model on {len(X)} samples...")
        logger.info(f"Feature shape: {X.shape}, Label distribution: {np.bincount(y)}")

        # Step 1: Split data (time-aware)
        tscv = TimeSeriesCV(n_splits=self.cv_splits)
        X_train, X_test, y_train, y_test = tscv.get_train_test_split(X, y, test_ratio=0.2)

        # Step 2: Hyperparameter tuning (optional)
        if self.tune_hyperparams:
            logger.info("Starting hyperparameter tuning...")
            tuner = HyperparameterTuner(n_trials=self.n_trials, n_jobs=1)

            if self.model_type == 'xgboost':
                tuning_result = tuner.tune_xgboost(X_train, y_train, cv_splits=self.cv_splits)
            elif self.model_type == 'lightgbm':
                tuning_result = tuner.tune_lightgbm(X_train, y_train, cv_splits=self.cv_splits)
            else:
                logger.warning(f"Hyperparameter tuning not supported for {self.model_type}")
                tuning_result = None

            if tuning_result and 'best_params' in tuning_result:
                self.best_params = tuning_result['best_params']
                logger.info(f"Best params: {self.best_params}")
            else:
                self.best_params = model_params or self._get_default_params()
        else:
            self.best_params = model_params or self._get_default_params()

        # Step 3: Train model with best params
        self.model = self._create_model(self.best_params)
        self.model.fit(X_train, y_train)

        # Step 4: Cross-validation on training set
        logger.info("Performing time series cross-validation...")
        tscv_full = TimeSeriesCV(n_splits=self.cv_splits)
        self.cv_results = tscv_full.validate_model(
            self._create_model(self.best_params),
            X_train,
            y_train,
            metrics=['accuracy', 'precision', 'recall', 'f1', 'auc']
        )

        print_cv_results(self.cv_results)

        # Step 5: Final evaluation on held-out test set
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score,
            f1_score, roc_auc_score, confusion_matrix, classification_report
        )

        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1] if hasattr(self.model, 'predict_proba') else None

        test_metrics = {
            'accuracy': float(accuracy_score(y_test, y_pred)),
            'precision': float(precision_score(y_test, y_pred, zero_division=0)),
            'recall': float(recall_score(y_test, y_pred, zero_division=0)),
            'f1': float(f1_score(y_test, y_pred, zero_division=0)),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist()
        }

        if y_pred_proba is not None:
            try:
                test_metrics['auc'] = float(roc_auc_score(y_test, y_pred_proba))
            except ValueError:
                test_metrics['auc'] = 0.0

        logger.info("\n" + "="*60)
        logger.info("HELD-OUT TEST SET RESULTS")
        logger.info("="*60)
        logger.info(f"Test samples: {len(X_test)}")
        for metric, value in test_metrics.items():
            if metric != 'confusion_matrix':
                logger.info(f"{metric}: {value:.4f}")
        logger.info("="*60 + "\n")

        # Step 6: Feature importance
        feature_importance = self._get_feature_importance()

        # Compile training report
        training_report = {
            'success': True,
            'model_type': self.model_type,
            'timestamp': datetime.now().isoformat(),
            'data': {
                'total_samples': len(X),
                'train_samples': len(X_train),
                'test_samples': len(X_test),
                'n_features': X.shape[1],
                'positive_samples': int(y.sum()),
                'negative_samples': int(len(y) - y.sum()),
                'class_balance': float(y.sum() / len(y))
            },
            'hyperparameters': self.best_params,
            'cv_results': {
                'mean_scores': self.cv_results['mean_scores'],
                'std_scores': self.cv_results['std_scores']
            },
            'test_metrics': test_metrics,
            'feature_importance': feature_importance
        }

        return training_report

    def save_model(self, model_path: str) -> str:
        """Save trained model to disk."""
        if self.model is None:
            raise ValueError("No model to save. Train a model first.")

        os.makedirs(os.path.dirname(model_path), exist_ok=True)

        with open(model_path, 'wb') as f:
            pickle.dump(self.model, f)

        logger.info(f"Model saved to {model_path}")
        return model_path

    def load_model(self, model_path: str):
        """Load trained model from disk."""
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

        logger.info(f"Model loaded from {model_path}")

    def _create_model(self, params: Dict[str, Any]):
        """Create model instance based on type."""
        if self.model_type == 'xgboost':
            import xgboost as xgb
            return xgb.XGBClassifier(**params)
        elif self.model_type == 'lightgbm':
            import lightgbm as lgb
            return lgb.LGBMClassifier(**params)
        elif self.model_type == 'randomforest':
            from sklearn.ensemble import RandomForestClassifier
            return RandomForestClassifier(**params)
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")

    def _get_default_params(self) -> Dict[str, Any]:
        """Get default parameters for model type."""
        if self.model_type == 'xgboost':
            return {
                'max_depth': 5,
                'n_estimators': 100,
                'learning_rate': 0.1,
                'min_child_weight': 3,
                'gamma': 0.1,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'reg_lambda': 1.0,
                'random_state': 42
            }
        elif self.model_type == 'lightgbm':
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
                'verbose': -1
            }
        elif self.model_type == 'randomforest':
            return {
                'n_estimators': 100,
                'max_depth': 10,
                'min_samples_split': 5,
                'min_samples_leaf': 2,
                'max_features': 'sqrt',
                'random_state': 42,
                'n_jobs': -1
            }
        else:
            return {}

    def _get_feature_importance(self) -> Optional[List[float]]:
        """Get feature importance from trained model."""
        if self.model is None:
            return None

        if hasattr(self.model, 'feature_importances_'):
            return self.model.feature_importances_.tolist()

        return None
