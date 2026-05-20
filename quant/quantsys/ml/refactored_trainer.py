"""
Refactored signal trainer with proper ML practices.

FIXES:
1. ✅ Time series cross-validation (no more train=test)
2. ✅ 50+ engineered features
3. ✅ Hyperparameter tuning with Optuna
4. ✅ Model ensemble (XGBoost + LightGBM + RandomForest)
5. ✅ Proper train/test split
"""
import os
import json
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

from .features.feature_engineering import FeatureEngineer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_signals_from_dir(signals_dir: str, days: int = 60) -> list:
    """Load recent signals from JSON files."""
    signals = []
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    if not os.path.exists(signals_dir):
        logger.warning(f"Signals directory not found: {signals_dir}")
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
            logger.error(f"Error loading {filename}: {e}")

    logger.info(f"Loaded {len(signals)} signals from {signals_dir}")
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
        logger.debug(f"Failed to get future return for {symbol} on {date}: {e}")
        return 0.0


def prepare_training_data(
    signals: List[dict],
    return_threshold: float = 0.02,
    return_days: int = 5
) -> tuple:
    """
    Prepare training data with labels.

    Args:
        signals: List of signal dictionaries
        return_threshold: Threshold for positive label (default 2%)
        return_days: Days to calculate future return

    Returns:
        (X, y, feature_names, labeled_signals)
    """
    logger.info("Preparing training data with feature engineering...")

    feature_engineer = FeatureEngineer()
    labeled_data = []

    for signal in signals:
        # Calculate future return
        future_return = get_future_return(signal['symbol'], signal['date'], days=return_days)

        # Label: 1 if return > threshold, 0 otherwise
        label = 1 if future_return > return_threshold else 0

        # Extract features
        features = feature_engineer.extract_features(signal)
        feature_array = feature_engineer.features_to_array(features)

        labeled_data.append({
            'features': feature_array,
            'label': label,
            'future_return': future_return,
            'signal': signal
        })

    # Convert to numpy arrays
    X = np.array([item['features'] for item in labeled_data])
    y = np.array([item['label'] for item in labeled_data])
    feature_names = feature_engineer.get_feature_names()

    logger.info(f"Prepared {len(X)} samples with {len(feature_names)} features")
    logger.info(f"Label distribution: Positive={y.sum()}, Negative={len(y)-y.sum()}")
    logger.info(f"Class balance: {y.sum()/len(y)*100:.1f}% positive")

    return X, y, feature_names, labeled_data


def train_model(
    days: int = 60,
    min_samples: int = 100,
    model_type: str = 'xgboost',
    tune_hyperparams: bool = False,
    n_trials: int = 50,
    return_threshold: float = 0.02
) -> Dict[str, Any]:
    """
    Train ML model with proper validation.

    Args:
        days: Number of days of historical signals to use
        min_samples: Minimum number of samples required for training
        model_type: 'xgboost', 'lightgbm', or 'ensemble'
        tune_hyperparams: Whether to tune hyperparameters
        n_trials: Number of tuning trials
        return_threshold: Threshold for positive label

    Returns:
        Training report with metrics
    """
    logger.info("="*60)

    from .training.trainer import ModelTrainer

    logger.info("STARTING ML MODEL TRAINING")
    logger.info("="*60)

    # Check dependencies
    try:
        import xgboost as xgb
    except ImportError:
        return {
            "error": "xgboost not installed. Run: pip install xgboost"
        }

    try:
        from sklearn.model_selection import TimeSeriesSplit
    except ImportError:
        return {
            "error": "scikit-learn not installed. Run: pip install scikit-learn"
        }

    # Load historical signals
    signals = load_signals_from_dir('.pi-invest/quant/signals/', days)

    if len(signals) < min_samples:
        return {
            "error": f"Insufficient samples: {len(signals)} < {min_samples}",
            "samples": len(signals),
            "required": min_samples,
            "suggestion": f"Increase 'days' parameter or wait for more signals to accumulate"
        }

    # Prepare training data
    X, y, feature_names, labeled_data = prepare_training_data(
        signals,
        return_threshold=return_threshold
    )

    # Check class balance
    positive_ratio = y.sum() / len(y)
    if positive_ratio < 0.1 or positive_ratio > 0.9:
        logger.warning(
            f"Severe class imbalance: {positive_ratio*100:.1f}% positive. "
            f"Consider adjusting return_threshold (current: {return_threshold})"
        )

    # Train model with proper validation
    trainer = ModelTrainer(
        model_type=model_type,
        tune_hyperparams=tune_hyperparams,
        n_trials=n_trials,
        cv_splits=5
    )

    training_report = trainer.train(X, y)

    # Save model
    os.makedirs('.pi-invest/quant/models', exist_ok=True)
    model_path = '.pi-invest/quant/models/signal_confidence.pkl'
    trainer.save_model(model_path)

    training_report['model_path'] = model_path
    training_report['feature_names'] = feature_names
    training_report['return_threshold'] = return_threshold

    # Save training report
    report_path = '.pi-invest/quant/models/training_report.json'
    with open(report_path, 'w') as f:
        json.dump(training_report, f, indent=2)

    logger.info(f"Training report saved to {report_path}")

    # Print summary
    logger.info("\n" + "="*60)
    logger.info("TRAINING COMPLETE")
    logger.info("="*60)
    logger.info(f"Model type: {model_type}")
    logger.info(f"Total samples: {training_report['data']['total_samples']}")
    logger.info(f"Features: {training_report['data']['n_features']}")
    logger.info(f"CV Accuracy: {training_report['cv_results']['mean_scores']['accuracy']:.4f} ± {training_report['cv_results']['std_scores']['accuracy']:.4f}")
    logger.info(f"Test Accuracy: {training_report['test_metrics']['accuracy']:.4f}")
    logger.info(f"Test AUC: {training_report['test_metrics'].get('auc', 0):.4f}")
    logger.info(f"Model saved: {model_path}")
    logger.info("="*60 + "\n")

    return training_report


# Backward compatibility with old API
def train_model_legacy(days: int = 30, min_samples: int = 50) -> dict:
    """
    Legacy API for backward compatibility.

    ⚠️ DEPRECATED: Use train_model() instead for proper validation.
    """
    logger.warning(
        "Using legacy train_model API. "
        "This function is deprecated and will be removed in future versions. "
        "Use train_model() instead."
    )

    return train_model(
        days=days,
        min_samples=min_samples,
        model_type='xgboost',
        tune_hyperparams=False
    )
