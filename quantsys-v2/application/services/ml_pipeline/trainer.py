"""
ML Trainer Module

Handles model training, evaluation, and persistence.
Supports XGBoost and LightGBM models.
"""

from __future__ import annotations

import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix
)
from sklearn.model_selection import train_test_split

# 注意：xgboost 不在模块级导入（2026-08-20 segfault 修复）。
# xgboost/lightgbm 均依赖 Homebrew libomp，若与进程内其他 OpenMP 拷贝
# （torch/lib/libomp.dylib、sklearn/.dylibs/libomp.dylib）混载，
# OpenMP worker 线程会段错误（crash 堆栈: __kmp_suspend_initialize_thread）。
# 两个后端都改为在各自 _train_* 方法内延迟导入，训练进程只加载所需后端。

logger = logging.getLogger(__name__)


class MLTrainer:
    """
    ML model trainer for stock prediction.

    Supports XGBoost and LightGBM with comprehensive evaluation metrics.
    """

    def __init__(
        self,
        model_type: str = "xgboost",
        model_dir: str = ".pi-invest/ml/models"
    ):
        """
        Initialize MLTrainer.

        Args:
            model_type: "xgboost" or "lightgbm"
            model_dir: Directory to save trained models
        """
        self.model_type = model_type
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.model = None
        self.feature_names: list[str] = []
        self.feature_importance: dict[str, float] = {}
        self.training_history: dict[str, Any] = {}

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = 0.2,
        random_state: int = 42,
        params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Train the model.

        Args:
            X: Feature DataFrame
            y: Target series (binary: 0=down/neutral, 1=up)
            test_size: Proportion of data for testing
            random_state: Random seed
            params: Model hyperparameters

        Returns:
            Dict with training results and metrics
        """
        logger.info(f"Training {self.model_type} model")
        logger.info(f"Training data shape: X={X.shape}, y={y.shape}")

        # Store feature names
        self.feature_names = list(X.columns)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )

        logger.info(f"Train set: {X_train.shape}, Test set: {X_test.shape}")
        logger.info(f"Train target distribution: {y_train.value_counts().to_dict()}")
        logger.info(f"Test target distribution: {y_test.value_counts().to_dict()}")

        # Train model
        if self.model_type == "xgboost":
            results = self._train_xgboost(X_train, y_train, X_test, y_test, params)
        elif self.model_type == "lightgbm":
            results = self._train_lightgbm(X_train, y_train, X_test, y_test, params)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        # Store training history
        self.training_history = {
            "model_type": self.model_type,
            "train_date": datetime.now().isoformat(),
            "train_size": len(X_train),
            "test_size": len(X_test),
            "feature_count": len(self.feature_names),
            "feature_names": self.feature_names,
            "params": params or {},
            **results
        }

        logger.info(f"Training completed. Test accuracy: {results['test_accuracy']:.4f}")

        return self.training_history

    def _train_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        params: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Train XGBoost model."""
        try:
            import xgboost as xgb
        except ImportError:
            raise ImportError("xgboost not installed. Install with: pip install xgboost")

        # Default parameters
        default_params = {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "max_depth": 6,
            "learning_rate": 0.1,
            "n_estimators": 100,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "n_jobs": -1
        }

        if params:
            default_params.update(params)

        # Train model
        self.model = xgb.XGBClassifier(**default_params)
        self.model.fit(
            X_train,
            y_train,
            eval_set=[(X_train, y_train), (X_test, y_test)],
            verbose=False
        )

        # Get feature importance (convert to native Python float)
        importance_scores = self.model.feature_importances_
        self.feature_importance = {
            name: float(score)
            for name, score in zip(self.feature_names, importance_scores)
        }

        # Evaluate
        train_metrics = self._evaluate(X_train, y_train, prefix="train")
        test_metrics = self._evaluate(X_test, y_test, prefix="test")

        return {
            **train_metrics,
            **test_metrics,
            "feature_importance": self.feature_importance,
            "params": default_params
        }

    def _train_lightgbm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        params: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Train LightGBM model."""
        try:
            import lightgbm as lgb
        except ImportError:
            raise ImportError("lightgbm not installed. Install with: pip install lightgbm")

        # Default parameters
        default_params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "max_depth": 6,
            "learning_rate": 0.1,
            "n_estimators": 100,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "n_jobs": -1,
            "verbose": -1
        }

        if params:
            default_params.update(params)

        # Train model
        self.model = lgb.LGBMClassifier(**default_params)
        self.model.fit(
            X_train,
            y_train,
            eval_set=[(X_train, y_train), (X_test, y_test)],
            eval_metric="logloss"
        )

        # Get feature importance (convert to native Python float)
        importance_scores = self.model.feature_importances_
        self.feature_importance = {
            name: float(score)
            for name, score in zip(self.feature_names, importance_scores)
        }

        # Evaluate
        train_metrics = self._evaluate(X_train, y_train, prefix="train")
        test_metrics = self._evaluate(X_test, y_test, prefix="test")

        return {
            **train_metrics,
            **test_metrics,
            "feature_importance": self.feature_importance,
            "params": default_params
        }

    def _evaluate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        prefix: str = "test"
    ) -> dict[str, float]:
        """
        Evaluate model performance.

        Args:
            X: Feature DataFrame
            y: True labels
            prefix: Metric name prefix (e.g., "train" or "test")

        Returns:
            Dict with evaluation metrics
        """
        # Predictions
        y_pred = self.model.predict(X)
        y_pred_proba = self.model.predict_proba(X)[:, 1]

        # Calculate metrics
        metrics = {
            f"{prefix}_accuracy": accuracy_score(y, y_pred),
            f"{prefix}_precision": precision_score(y, y_pred, zero_division=0),
            f"{prefix}_recall": recall_score(y, y_pred, zero_division=0),
            f"{prefix}_f1": f1_score(y, y_pred, zero_division=0),
        }

        # ROC AUC (only if both classes present)
        if len(np.unique(y)) > 1:
            metrics[f"{prefix}_roc_auc"] = roc_auc_score(y, y_pred_proba)

        # Confusion matrix
        cm = confusion_matrix(y, y_pred)
        metrics[f"{prefix}_confusion_matrix"] = cm.tolist()

        return metrics

    def save_model(self, version: str = "latest") -> Path:
        """
        Save trained model to disk.

        Args:
            version: Model version identifier

        Returns:
            Path to saved model file
        """
        if self.model is None:
            raise ValueError("No model to save. Train a model first.")

        # Save model
        model_path = self.model_dir / f"{self.model_type}_{version}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(self.model, f)

        logger.info(f"Model saved to {model_path}")

        # Save training report
        report_path = self.model_dir / f"training_report_{version}.json"
        with open(report_path, "w") as f:
            json.dump(self.training_history, f, indent=2)

        logger.info(f"Training report saved to {report_path}")

        return model_path

    def load_model(self, version: str = "latest") -> None:
        """
        Load trained model from disk.

        Args:
            version: Model version identifier
        """
        model_path = self.model_dir / f"{self.model_type}_{version}.pkl"

        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        with open(model_path, "rb") as f:
            self.model = pickle.load(f)

        logger.info(f"Model loaded from {model_path}")

        # Load training report if available
        report_path = self.model_dir / f"training_report_{version}.json"
        if report_path.exists():
            with open(report_path, "r") as f:
                self.training_history = json.load(f)
            self.feature_names = self.training_history.get("feature_names", [])
            self.feature_importance = self.training_history.get("feature_importance", {})

    def get_feature_importance(self, top_n: int | None = None) -> dict[str, float]:
        """
        Get feature importance scores.

        Args:
            top_n: Return only top N features. If None, return all.

        Returns:
            Dict mapping feature name to importance score
        """
        if not self.feature_importance:
            return {}

        sorted_importance = sorted(
            self.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )

        if top_n is not None:
            sorted_importance = sorted_importance[:top_n]

        return dict(sorted_importance)

    def get_model_info(self) -> dict[str, Any]:
        """
        Get model information.

        Returns:
            Dict with model metadata
        """
        if self.model is None:
            return {"status": "not_trained"}

        return {
            "status": "trained",
            "model_type": self.model_type,
            "feature_count": len(self.feature_names),
            "training_history": self.training_history
        }
