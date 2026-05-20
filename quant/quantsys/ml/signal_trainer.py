"""
XGBoost model training for signal confidence prediction.

⚠️  DEPRECATED: This module has been refactored to fix critical issues.

CRITICAL ISSUES IN THIS FILE:
1. ❌ Training set = Test set (line 132: model.score(X, y))
2. ❌ Only 8 basic features
3. ❌ No cross-validation
4. ❌ No hyperparameter tuning

USE NEW MODULE INSTEAD:
    from ml.refactored_trainer import train_model

    result = train_model(
        days=60,
        min_samples=100,
        model_type='xgboost',
        tune_hyperparams=False
    )

See python/ml/README.md for details.
"""
import os
import json
import pickle
from datetime import datetime, timedelta
import numpy as np
import warnings

warnings.warn(
    "ml.signal_trainer is deprecated and has critical validation issues. "
    "Use ml.refactored_trainer instead. See python/ml/README.md",
    DeprecationWarning,
    stacklevel=2
)


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
    Calculate future return for a signal using actual price data.
    """
    from datetime import datetime as dt, timedelta
    from quantsys.data.db import Database

    try:
        future_date = (dt.strptime(date, '%Y-%m-%d') + timedelta(days=days)).strftime('%Y-%m-%d')
        database = Database()
        try:
            future_close = database.get_close_for_label(symbol, future_date, direction="forward")
            current_close = database.get_close_for_label(symbol, date, direction="backward")
        finally:
            database.close()

        if future_close is not None and current_close and current_close > 0:
            return (future_close - current_close) / current_close

        return 0.0
    except Exception as e:
        print(f"[get_future_return] Failed for {symbol} on {date}: {e}")
        return 0.0


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

    from .features.feature_engineering import FeatureEngineer

    # Load historical signals
    signals = load_signals_from_dir('.pi-invest/quant/signals/', days)

    if len(signals) < min_samples:
        return {
            "error": f"Insufficient samples: {len(signals)} < {min_samples}",
            "samples": len(signals),
            "required": min_samples
        }

    # Label signals based on future returns
    feature_engineer = FeatureEngineer()
    labeled_data = []
    for signal in signals:
        future_return = get_future_return(signal['symbol'], signal['date'], days=5)
        label = 1 if future_return > 0.02 else 0  # >2% return = positive

        feature_dict = feature_engineer.extract_features(signal)
        feature_array = feature_engineer.features_to_array(feature_dict)
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
