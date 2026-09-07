"""
ML Predictor Module

Handles model loading and batch prediction with confidence scores.
"""

from __future__ import annotations

import json
import logging
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MLPredictor:
    """
    ML predictor for stock signals.

    Loads trained models and performs batch predictions with confidence scores.
    """

    def __init__(
        self,
        model_type: str = "xgboost",
        model_dir: str = ".pi-invest/ml/models"
    ):
        """
        Initialize MLPredictor.

        Args:
            model_type: "xgboost" or "lightgbm"
            model_dir: Directory containing trained models
        """
        self.model_type = model_type
        self.model_dir = Path(model_dir)

        self.model = None
        self.feature_names: list[str] = []
        self.model_info: dict[str, Any] = {}

    def load_model(self, version: str = "latest") -> None:
        """
        Load trained model from disk.

        Args:
            version: Model version identifier

        Raises:
            FileNotFoundError: If model file not found
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
                self.model_info = json.load(f)
            self.feature_names = self.model_info.get("feature_names", [])
            logger.info(f"Model info loaded: {len(self.feature_names)} features")

    def predict(
        self,
        X: pd.DataFrame,
        return_proba: bool = True
    ) -> pd.DataFrame:
        """
        Make predictions on feature data.

        Args:
            X: Feature DataFrame (must have same features as training)
            return_proba: Whether to return probability scores

        Returns:
            DataFrame with columns: prediction, confidence (if return_proba=True)
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load_model() first.")

        # Validate features
        missing_features = set(self.feature_names) - set(X.columns)
        if missing_features:
            raise ValueError(f"Missing features: {missing_features}")

        # Ensure correct feature order
        X_ordered = X[self.feature_names]

        # Make predictions
        predictions = self.model.predict(X_ordered)

        result = pd.DataFrame({
            "prediction": predictions
        })

        if return_proba:
            probabilities = self.model.predict_proba(X_ordered)
            # Confidence is the probability of the predicted class
            confidence = np.max(probabilities, axis=1)
            result["confidence"] = confidence
            result["prob_down"] = probabilities[:, 0]
            result["prob_up"] = probabilities[:, 1]

        return result

    def predict_batch(
        self,
        metadata: pd.DataFrame,
        features: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Batch prediction with metadata.

        Args:
            metadata: DataFrame with symbol, date columns
            features: Feature DataFrame

        Returns:
            DataFrame with columns: symbol, date, prediction, confidence, prob_down, prob_up
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load_model() first.")

        logger.info(f"Predicting for {len(features)} samples")

        # Make predictions
        predictions = self.predict(features, return_proba=True)

        # Combine with metadata
        result = pd.concat([metadata.reset_index(drop=True), predictions], axis=1)

        # Add signal interpretation
        result["signal"] = result["prediction"].map({0: "HOLD", 1: "BUY"})

        logger.info(f"Predictions: {result['signal'].value_counts().to_dict()}")

        return result

    def predict_single(
        self,
        features: dict[str, float]
    ) -> dict[str, Any]:
        """
        Predict for a single sample.

        Args:
            features: Dict mapping feature name to value

        Returns:
            Dict with prediction, confidence, probabilities
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load_model() first.")

        # Convert to DataFrame
        X = pd.DataFrame([features])

        # Make prediction
        result = self.predict(X, return_proba=True)

        return {
            "prediction": int(result["prediction"].iloc[0]),
            "signal": "BUY" if result["prediction"].iloc[0] == 1 else "HOLD",
            "confidence": float(result["confidence"].iloc[0]),
            "prob_down": float(result["prob_down"].iloc[0]),
            "prob_up": float(result["prob_up"].iloc[0])
        }

    def get_model_info(self) -> dict[str, Any]:
        """
        Get loaded model information.

        Returns:
            Dict with model metadata
        """
        if self.model is None:
            return {"status": "not_loaded"}

        return {
            "status": "loaded",
            "model_type": self.model_type,
            "feature_count": len(self.feature_names),
            "feature_names": self.feature_names,
            **self.model_info
        }

    def validate_features(self, X: pd.DataFrame) -> dict[str, Any]:
        """
        Validate feature DataFrame against model requirements.

        Args:
            X: Feature DataFrame

        Returns:
            Dict with validation results
        """
        if self.model is None:
            return {"valid": False, "error": "Model not loaded"}

        missing_features = set(self.feature_names) - set(X.columns)
        extra_features = set(X.columns) - set(self.feature_names)

        valid = len(missing_features) == 0

        return {
            "valid": valid,
            "missing_features": list(missing_features),
            "extra_features": list(extra_features),
            "required_features": self.feature_names,
            "provided_features": list(X.columns)
        }
