"""
ML Pipeline Demo Script

Demonstrates training and prediction workflow.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from application.services.ml_pipeline.feature_engineering import FeatureEngineer
from application.services.ml_pipeline.trainer import MLTrainer
from application.services.ml_pipeline.predictor import MLPredictor

# Import factor modules to register factors
from domain.quantlib.engine import technical_factors, fundamental_factors


def generate_sample_data(n_symbols=10, n_days=200):
    """Generate sample kline data for demonstration."""
    print(f"Generating sample data for {n_symbols} symbols, {n_days} days...")

    klines_dict = {}
    dates = pd.date_range(end=datetime.now(), periods=n_days, freq='D')

    for i in range(n_symbols):
        symbol = f"00000{i}.SZ"
        klines = []

        price = 100.0 + np.random.randn() * 20

        for date in dates:
            # Random walk with trend
            change = np.random.randn() * 2 + 0.05  # Slight upward bias
            price = max(price + change, 10.0)

            kline = {
                'date': date.strftime('%Y-%m-%d'),
                'trade_date': date.strftime('%Y-%m-%d'),
                'open': price + np.random.randn() * 0.5,
                'high': price + abs(np.random.randn() * 1.5),
                'low': price - abs(np.random.randn() * 1.5),
                'close': price,
                'volume': np.random.randint(1000000, 10000000),
                'amount': price * np.random.randint(1000000, 10000000)
            }
            klines.append(kline)

        klines_dict[symbol] = klines

    print(f"Generated data for {len(klines_dict)} symbols")
    return klines_dict


def demo_feature_engineering(klines_dict):
    """Demonstrate feature engineering."""
    print("\n" + "="*60)
    print("STEP 1: Feature Engineering")
    print("="*60)

    engineer = FeatureEngineer(scaler_type='standard')

    # Extract features (use subset for demo)
    factor_names = [
        'ma5', 'ma10', 'ma20',
        'rsi14', 'macd', 'macd_signal',
        'bollinger_upper', 'bollinger_lower',
        'volume_ratio', 'atr14'
    ]

    print(f"\nExtracting {len(factor_names)} features...")
    features_df = engineer.extract_features(klines_dict, factor_names=factor_names)

    print(f"Features shape: {features_df.shape}")
    print(f"Feature names: {engineer.feature_names}")
    print(f"\nSample features:")
    print(features_df.head())

    # Create synthetic target (next day return > 0)
    # In production, calculate actual forward returns
    print("\nCreating target variable...")
    target = (features_df['rsi14'].fillna(50) > 50).astype(int)
    print(f"Target distribution: {target.value_counts().to_dict()}")

    # Prepare features
    print("\nPreparing features (scaling, handling missing values)...")
    metadata, scaled_features = engineer.prepare_features(
        features_df,
        handle_missing='drop',
        fit_scaler=True
    )

    print(f"Prepared features shape: {scaled_features.shape}")
    print(f"Metadata shape: {metadata.shape}")

    # Align target
    target = target[scaled_features.index]

    return metadata, scaled_features, target, engineer


def demo_training(X, y):
    """Demonstrate model training."""
    print("\n" + "="*60)
    print("STEP 2: Model Training")
    print("="*60)

    trainer = MLTrainer(model_type='xgboost')

    print(f"\nTraining XGBoost model...")
    print(f"Training data: X={X.shape}, y={y.shape}")

    results = trainer.train(
        X, y,
        test_size=0.2,
        params={
            'max_depth': 5,
            'learning_rate': 0.1,
            'n_estimators': 50
        }
    )

    print(f"\n--- Training Results ---")
    print(f"Train Accuracy: {results['train_accuracy']:.4f}")
    print(f"Test Accuracy:  {results['test_accuracy']:.4f}")
    print(f"Test Precision: {results['test_precision']:.4f}")
    print(f"Test Recall:    {results['test_recall']:.4f}")
    print(f"Test F1:        {results['test_f1']:.4f}")

    if 'test_roc_auc' in results:
        print(f"Test ROC AUC:   {results['test_roc_auc']:.4f}")

    # Feature importance
    print(f"\n--- Top 5 Important Features ---")
    importance = trainer.get_feature_importance(top_n=5)
    for i, (feature, score) in enumerate(importance.items(), 1):
        print(f"{i}. {feature}: {score:.4f}")

    # Save model
    print(f"\nSaving model...")
    model_path = trainer.save_model(version='demo')
    print(f"Model saved to: {model_path}")

    return trainer


def demo_prediction(metadata, X, trainer):
    """Demonstrate prediction."""
    print("\n" + "="*60)
    print("STEP 3: Prediction")
    print("="*60)

    # Create predictor
    predictor = MLPredictor(model_type='xgboost')
    predictor.load_model(version='demo')

    print(f"\nModel loaded successfully")
    print(f"Model features: {len(predictor.feature_names)}")

    # Make predictions
    print(f"\nMaking predictions for {len(X)} samples...")
    predictions = predictor.predict_batch(metadata, X)

    print(f"\n--- Prediction Results ---")
    print(f"Total predictions: {len(predictions)}")
    print(f"Signal distribution: {predictions['signal'].value_counts().to_dict()}")

    print(f"\n--- Sample Predictions ---")
    print(predictions[['symbol', 'date', 'signal', 'confidence', 'prob_up']].head(10))

    # Single prediction demo
    print(f"\n--- Single Prediction Demo ---")
    sample_features = X.iloc[0].to_dict()
    result = predictor.predict_single(sample_features)
    print(f"Symbol: {metadata.iloc[0]['symbol']}")
    print(f"Signal: {result['signal']}")
    print(f"Confidence: {result['confidence']:.4f}")
    print(f"Prob Up: {result['prob_up']:.4f}")
    print(f"Prob Down: {result['prob_down']:.4f}")

    return predictions


def demo_model_info():
    """Demonstrate model info retrieval."""
    print("\n" + "="*60)
    print("STEP 4: Model Information")
    print("="*60)

    predictor = MLPredictor(model_type='xgboost')
    predictor.load_model(version='demo')

    info = predictor.get_model_info()

    print(f"\nModel Status: {info['status']}")
    print(f"Model Type: {info['model_type']}")
    print(f"Feature Count: {info['feature_count']}")
    print(f"Training Date: {info.get('train_date', 'N/A')}")
    print(f"Train Size: {info.get('train_size', 'N/A')}")
    print(f"Test Size: {info.get('test_size', 'N/A')}")


def main():
    """Run complete ML pipeline demo."""
    print("="*60)
    print("ML Pipeline Demo")
    print("="*60)

    # Generate sample data
    klines_dict = generate_sample_data(n_symbols=20, n_days=200)

    # Feature engineering
    metadata, X, y, engineer = demo_feature_engineering(klines_dict)

    # Training
    trainer = demo_training(X, y)

    # Prediction
    predictions = demo_prediction(metadata, X, trainer)

    # Model info
    demo_model_info()

    print("\n" + "="*60)
    print("Demo completed successfully!")
    print("="*60)


if __name__ == '__main__':
    main()
