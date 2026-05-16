"""
Signal confidence prediction using trained XGBoost model.
"""
import os
import pickle
import numpy as np
from .feature_extractor import extract_features, features_to_array


def predict_confidence(features: dict) -> dict:
    """
    Predict signal confidence using XGBoost model.

    Args:
        features: Feature dictionary from extract_features()

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

        # Convert features to array
        X = np.array([features_to_array(features)])

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
