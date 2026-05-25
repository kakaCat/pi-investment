"""
Prediction service for trained models.
"""
import os
import pickle
import numpy as np
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class Predictor:
    """
    Prediction service for loading and using trained models.
    """

    def __init__(self, model_path: str):
        """
        Args:
            model_path: Path to saved model file
        """
        self.model_path = model_path
        self.model = None
        self.feature_names = None

    def load_model(self) -> bool:
        """
        Load trained model from disk.

        Returns:
            True if successful, False otherwise
        """
        if not os.path.exists(self.model_path):
            logger.error(f"Model file not found: {self.model_path}")
            return False

        try:
            with open(self.model_path, 'rb') as f:
                self.model = pickle.load(f)

            logger.info(f"Model loaded from {self.model_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class labels.

        Args:
            X: Feature matrix

        Returns:
            Predicted labels
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load_model() first.")

        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class probabilities.

        Args:
            X: Feature matrix

        Returns:
            Predicted probabilities
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load_model() first.")

        if not hasattr(self.model, 'predict_proba'):
            raise ValueError("Model does not support probability prediction")

        return self.model.predict_proba(X)

    def predict_signal(
        self,
        signal: dict,
        feature_engineer: Any,
        threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Predict confidence for a single signal.

        Args:
            signal: Signal dictionary
            feature_engineer: FeatureEngineer instance
            threshold: Classification threshold

        Returns:
            Prediction result with confidence score
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load_model() first.")

        # Extract features
        features = feature_engineer.extract_features(signal)
        feature_array = feature_engineer.features_to_array(features)
        X = feature_array.reshape(1, -1)

        # Predict
        prediction = self.model.predict(X)[0]
        proba = self.model.predict_proba(X)[0]

        return {
            'prediction': int(prediction),
            'confidence': float(proba[1]),
            'is_confident': bool(proba[1] >= threshold),
            'probabilities': {
                'negative': float(proba[0]),
                'positive': float(proba[1])
            }
        }

    def predict_batch(
        self,
        signals: List[dict],
        feature_engineer: Any,
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Predict confidence for multiple signals.

        Args:
            signals: List of signal dictionaries
            feature_engineer: FeatureEngineer instance
            threshold: Classification threshold

        Returns:
            List of prediction results
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load_model() first.")

        results = []

        for signal in signals:
            try:
                result = self.predict_signal(signal, feature_engineer, threshold)
                result['symbol'] = signal.get('symbol')
                result['date'] = signal.get('date')
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to predict signal for {signal.get('symbol')}: {e}")
                results.append({
                    'symbol': signal.get('symbol'),
                    'date': signal.get('date'),
                    'error': str(e)
                })

        return results

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded model."""
        if self.model is None:
            return {'error': 'No model loaded'}

        info = {
            'model_type': type(self.model).__name__,
            'model_path': self.model_path
        }

        # Add model-specific info
        if hasattr(self.model, 'n_features_in_'):
            info['n_features'] = self.model.n_features_in_

        if hasattr(self.model, 'feature_importances_'):
            info['has_feature_importance'] = True

        if hasattr(self.model, 'get_params'):
            info['params'] = self.model.get_params()

        return info
