"""
XGBoost model training for signal confidence prediction.
"""
import os
import json
import pickle
from datetime import datetime, timedelta
import numpy as np


def load_signals_from_dir(signals_dir: str, days: int = 30) -> list:
    """Load recent signals from JSON files."""
    signals = []
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    if not os.path.exists(signals_dir):
        return signals

    for filename in os.listdir(signals_dir):
        if not filename.endswith('.json'):
            continue

        date = filename.replace('.json', '')
        if date < cutoff_date:
            continue

        filepath = os.path.join(signals_dir, filename)
        try:
            with open(filepath, 'r') as f:
                daily_signals = json.load(f)
                signals.extend(daily_signals)
        except Exception as e:
            print(f"Error loading {filename}: {e}")

    return signals


def get_future_return(symbol: str, date: str, days: int = 5) -> float:
    """
    Calculate future return for a signal (placeholder).

    In production, this should query historical price data from the database.
    For now, returns a random value for testing.
    """
    # TODO: Implement actual price lookup from SQLite database
    # This is a placeholder that returns random values
    import random
    return random.uniform(-0.1, 0.15)


def train_model(days: int = 30, min_samples: int = 50) -> dict:
    """
    Train XGBoost model on historical signals.

    Args:
        days: Number of days of historical signals to use
        min_samples: Minimum number of samples required for training

    Returns:
        Training report with metrics
    """
    try:
        import xgboost as xgb
    except ImportError:
        return {
            "error": "xgboost not installed. Run: pip install xgboost"
        }

    from .feature_extractor import extract_features, features_to_array

    # Load historical signals
    signals = load_signals_from_dir('.pi-invest/quant/signals/', days)

    if len(signals) < min_samples:
        return {
            "error": f"Insufficient samples: {len(signals)} < {min_samples}",
            "samples": len(signals),
            "required": min_samples
        }

    # Label signals based on future returns
    labeled_data = []
    for signal in signals:
        future_return = get_future_return(signal['symbol'], signal['date'], days=5)
        label = 1 if future_return > 0.02 else 0  # >2% return = positive

        features = extract_features(signal)
        feature_array = features_to_array(features)
        labeled_data.append((feature_array, label))

    # Split features and labels
    X = np.array([item[0] for item in labeled_data])
    y = np.array([item[1] for item in labeled_data])

    # Train XGBoost
    model = xgb.XGBClassifier(
        max_depth=5,
        n_estimators=100,
        learning_rate=0.1,
        random_state=42
    )
    model.fit(X, y)

    # Save model
    os.makedirs('.pi-invest/quant/models', exist_ok=True)
    model_path = '.pi-invest/quant/models/signal_confidence.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)

    # Calculate metrics
    accuracy = model.score(X, y)
    feature_importance = model.feature_importances_.tolist()

    return {
        "success": True,
        "samples": len(labeled_data),
        "accuracy": float(accuracy),
        "feature_importance": feature_importance,
        "model_path": model_path,
        "positive_samples": int(y.sum()),
        "negative_samples": int(len(y) - y.sum())
    }
