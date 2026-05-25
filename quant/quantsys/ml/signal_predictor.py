"""
Signal confidence prediction using trained XGBoost model.
"""
import os
import pickle
import numpy as np
from .features.feature_engineering import FeatureEngineer


def predict_confidence(signal: dict) -> dict:
    """
    Predict signal confidence using XGBoost model.

    Args:
        signal: Signal dictionary with indicators

    Returns:
        Dictionary with confidence score and model info
    """
    model_path = '.pi-invest/quant/models/signal_confidence.pkl'

    # Model not exists - graceful degradation
    if not os.path.exists(model_path):
        return {
            "confidence": None,
            "model": "none",
            "message": "Model not trained yet"
        }

    try:
        # Load model
        with open(model_path, 'rb') as f:
            model = pickle.load(f)

        # Extract features using FeatureEngineer
        feature_engineer = FeatureEngineer()
        feature_dict = feature_engineer.extract_features(signal)
        X = feature_engineer.features_to_array(feature_dict).reshape(1, -1)

        # Predict probability
        proba = model.predict_proba(X)[0][1]  # Positive class probability

        return {
            "confidence": float(proba),
            "model": "xgboost"
        }

    except Exception as e:
        return {
            "confidence": None,
            "model": "none",
            "error": str(e)
        }
