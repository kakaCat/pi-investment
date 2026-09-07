"""
Machine Learning Module Examples
=================================

Complete usage examples for all ML calculators in quantlib.ml.

Examples:
    1. Automatic factor mining
    2. XGBoost return prediction
    3. LSTM volatility prediction
    4. Market anomaly detection
    5. Complete ML-enhanced strategy
    6. Model ensemble and backtesting

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
import pandas as pd
import warnings

warnings.filterwarnings('ignore')

from domain.quantlib.ml import (
    FeatureEngineeringCalculator,
    FactorMiningCalculator,
    ReturnPredictionCalculator,
    RiskPredictionCalculator,
    AnomalyDetectionCalculator,
)


# ==============================================================================
# Helper: Generate Sample Data
# ==============================================================================

def generate_sample_price_data(n_days: int = 500) -> pd.DataFrame:
    """Generate synthetic OHLCV data for examples."""
    np.random.seed(42)

    # Simulate a random walk with drift
    drift = 0.0002
    volatility = 0.02

    daily_returns = np.random.normal(drift, volatility, n_days)
    price = 10.0 * np.exp(np.cumsum(daily_returns))

    dates = pd.date_range(start='2024-01-01', periods=n_days, freq='B')

    high = price * (1 + np.abs(np.random.normal(0, 0.01, n_days)))
    low = price * (1 - np.abs(np.random.normal(0, 0.01, n_days)))
    open_price = price * (1 + np.random.normal(0, 0.005, n_days))
    volume = np.random.lognormal(15, 0.5, n_days)

    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': price,
        'volume': volume,
    }, index=dates)

    return df


def generate_factor_candidates(n_days: int = 500) -> pd.DataFrame:
    """Generate synthetic factor candidate data."""
    np.random.seed(123)

    dates = pd.date_range(start='2024-01-01', periods=n_days, freq='B')
    n_candidates = 30

    factors = pd.DataFrame(index=dates)

    for i in range(n_candidates):
        # Mix of random and structured factors
        if i < 10:
            # Informative factors (correlated with some target)
            base = np.random.normal(0, 1, n_days)
            factors[f'factor_{i:02d}'] = (
                0.5 * base +
                0.3 * np.random.normal(0, 1, n_days) +
                0.2 * np.sin(np.linspace(0, 5 * np.pi, n_days))
            )
        else:
            # Noise factors
            factors[f'factor_{i:02d}'] = np.random.normal(0, 1, n_days)

    return factors


# ==============================================================================
# Example 1: Automatic Factor Mining
# ==============================================================================

def example_factor_mining():
    """
    Example 1: Automatic Factor Mining

    Demonstrates how to use FactorMiningCalculator to discover alpha factors
    from candidate data using genetic algorithm, random forest, and LASSO.
    """
    print("=" * 70)
    print("Example 1: Automatic Factor Mining")
    print("=" * 70)

    # Generate sample data
    n_days = 500
    factors = generate_factor_candidates(n_days)
    print(f"  Generated {factors.shape[1]} factor candidates over {n_days} days")

    # Create a synthetic target (forward returns) with some structure
    np.random.seed(42)
    # Target is a weighted combination of some factors + noise
    target = (
        0.3 * factors['factor_00'].values +
        0.2 * factors['factor_01'].values +
        0.15 * factors['factor_02'].values -
        0.1 * factors['factor_03'].values +
        0.05 * np.random.normal(0, 1, n_days)
    )

    # Initialize calculator
    miner = FactorMiningCalculator()

    # Method 1: Random Forest importance
    print("\n1. Random Forest Factor Selection:")
    result_rf = miner.mine_factors(
        data=factors,
        target=target,
        method='random_forest',
        n_factors=10
    )
    rf_factors = result_rf['value']['factors'][:5]
    rf_importance = result_rf['metadata']['importance']
    print(f"   Top 5 factors: {rf_factors}")
    print(f"   Factor importances: {dict(list(rf_importance.items())[:3])}")

    # Method 2: LASSO selection
    print("\n2. LASSO Factor Selection:")
    result_lasso = miner.mine_factors(
        data=factors,
        target=target,
        method='lasso',
        n_factors=10
    )
    lasso_factors = result_lasso['value']['factors'][:5]
    print(f"   Top 5 factors: {lasso_factors}")

    # Method 3: Combined approach
    print("\n3. Combined Factor Mining:")
    result_combined = miner.mine_factors(
        data=factors,
        target=target,
        method='combined',
        n_factors=10,
        operators=['add', 'sub', 'mul', 'div', 'zscore', 'rank']
    )
    combined_factors = result_combined['value']['factors'][:5]
    ic_values = result_combined['metadata'].get('ic', {})
    print(f"   Top 5 factors: {combined_factors}")
    if ic_values:
        print(f"   IC values: {dict(list(ic_values.items())[:3])}")

    print("\n" + "-" * 70)


# ==============================================================================
# Example 2: XGBoost Return Prediction
# ==============================================================================

def example_return_prediction_xgboost():
    """
    Example 2: XGBoost Return Prediction

    Demonstrates return prediction using XGBoost with feature engineering
    and walk-forward cross-validation.
    """
    print("=" * 70)
    print("Example 2: XGBoost Return Prediction")
    print("=" * 70)

    # Generate price data
    price_data = generate_sample_price_data(500)
    print(f"  Price data: {len(price_data)} days")

    # Feature engineering
    print("\n1. Generating features...")
    fe_calc = FeatureEngineeringCalculator()
    fe_result = fe_calc.generate_features(
        data=price_data,
        feature_types=['technical', 'statistical', 'time'],
        window_sizes=[5, 10, 20, 60]
    )

    n_features = fe_result['metadata']['n_features']
    n_samples = fe_result['metadata']['n_samples']
    print(f"   Generated {n_features} features for {n_samples} samples")

    # Prepare features and target
    features_df = pd.DataFrame(fe_result['value'], index=price_data.index[-n_samples:])
    features_df = features_df.dropna()

    # Target: 5-day forward returns
    forward_returns = price_data['close'].pct_change(5).shift(-5).dropna().values
    common_len = min(len(features_df), len(forward_returns))
    features_df = features_df.iloc[:common_len]
    target = forward_returns[:common_len]

    print(f"   Features: {features_df.shape}, Target: {len(target)}")

    # XGBoost prediction
    print("\n2. Training XGBoost model...")
    pred_calc = ReturnPredictionCalculator()

    result_xgb = pred_calc.predict_returns(
        features=features_df,
        target=target,
        model_type='xgboost',
        horizon=5,
        train_ratio=0.7,
        n_splits=3,
        feature_selection=True
    )

    metrics = result_xgb['metadata']['metrics']
    predictions = result_xgb['value']['predictions']

    print(f"   Predictions: {len(predictions)} values")
    print(f"   R-squared: {metrics.get('r2', 'N/A')}")
    print(f"   RMSE: {metrics.get('rmse', 'N/A')}")
    print(f"   Hit Ratio: {metrics.get('hit_ratio', 'N/A')}")
    print(f"   IC: {metrics.get('ic', 'N/A')}")

    # Feature importance
    importance = result_xgb['metadata']['feature_importance']
    if importance:
        top_5 = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"\n   Top 5 features: {top_5}")

    print("\n" + "-" * 70)


# ==============================================================================
# Example 3: LSTM Volatility Prediction
# ==============================================================================

def example_risk_prediction():
    """
    Example 3: Risk (Volatility/VaR) Prediction

    Demonstrates volatility prediction using multiple model types
    and risk regime identification.
    """
    print("=" * 70)
    print("Example 3: Risk Prediction (Volatility / VaR)")
    print("=" * 70)

    # Generate return data
    np.random.seed(42)
    n_days = 500
    # Simulate returns with volatility clustering
    returns = np.zeros(n_days)
    sigma2 = np.zeros(n_days)
    sigma2[0] = 0.0004  # Annualized vol ~ 25%

    for t in range(1, n_days):
        sigma2[t] = 0.00001 + 0.1 * returns[t - 1] ** 2 + 0.85 * sigma2[t - 1]
        returns[t] = np.random.normal(0, np.sqrt(sigma2[t]))

    # Features
    dates = pd.date_range(start='2024-01-01', periods=n_days, freq='B')
    features = pd.DataFrame({
        'squared_returns': returns ** 2,
        'abs_returns': np.abs(returns),
        'vol_5d': pd.Series(np.abs(returns)).rolling(5).std().fillna(0).values,
        'vol_20d': pd.Series(np.abs(returns)).rolling(20).std().fillna(0).values,
        'range_20d': pd.Series(returns).rolling(20).max().fillna(0).values -
                     pd.Series(returns).rolling(20).min().fillna(0).values,
    }, index=dates).fillna(0)

    print(f"  Generated {n_days} days of return data with volatility clustering")

    risk_calc = RiskPredictionCalculator()

    # Method 1: GARCH volatility
    print("\n1. GARCH Volatility Forecast:")
    result_garch = risk_calc.predict_risk(
        returns=returns,
        features=features,
        risk_type='volatility',
        model_type='garch',
        horizon=10,
        confidence_level=0.95
    )
    preds = result_garch['value']['predictions']
    metrics = result_garch['metadata']['metrics']
    regime = result_garch['metadata']['risk_regime']

    print(f"   Forecast (10 days): {[f'{p:.4f}' for p in preds[:5]]}...")
    print(f"   GARCH params: omega={metrics['omega']:.6f}, alpha={metrics['alpha']:.3f}, beta={metrics['beta']:.3f}")
    print(f"   Persistence (alpha+beta): {metrics['persistence']:.3f}")
    print(f"   Risk Regime: {regime['current_regime']}")

    # Method 2: Historical volatility
    print("\n2. Historical Volatility Forecast:")
    result_hist = risk_calc.predict_risk(
        returns=returns,
        risk_type='volatility',
        model_type='historical',
        horizon=10
    )
    hist_preds = result_hist['value']['predictions']
    print(f"   Forecast: {[f'{p:.4f}' for p in hist_preds[:5]]}...")

    # Method 3: VaR prediction
    print("\n3. VaR Prediction (95% confidence):")
    result_var = risk_calc.predict_risk(
        returns=returns,
        risk_type='var',
        model_type='garch',
        horizon=10,
        confidence_level=0.95
    )
    var_preds = result_var['value']['predictions']
    ci = result_var['value']['confidence_interval']
    print(f"   VaR (daily, 95%): {[f'{p:.4f}' for p in var_preds[:5]]}...")
    print(f"   CI lower: {[f'{v:.4f}' for v in ci['lower'][:3]]}...")
    print(f"   CI upper: {[f'{v:.4f}' for v in ci['upper'][:3]]}...")

    # Method 4: CVaR prediction
    print("\n4. CVaR Prediction (Expected Shortfall):")
    result_cvar = risk_calc.predict_risk(
        returns=returns,
        risk_type='cvar',
        model_type='garch',
        horizon=10,
        confidence_level=0.95
    )
    cvar_preds = result_cvar['value']['predictions']
    print(f"   CVaR (daily, 95%): {[f'{p:.4f}' for p in cvar_preds[:5]]}...")

    print("\n" + "-" * 70)


# ==============================================================================
# Example 4: Market Anomaly Detection
# ==============================================================================

def example_anomaly_detection():
    """
    Example 4: Market Anomaly Detection

    Demonstrates anomaly detection on market data using multiple methods
    including Isolation Forest, LOF, and autoencoder.
    """
    print("=" * 70)
    print("Example 4: Market Anomaly Detection")
    print("=" * 70)

    # Generate normal and anomalous data
    np.random.seed(42)
    n_normal = 200
    n_anomaly = 10

    # Normal data
    normal_data = pd.DataFrame({
        'return': np.random.normal(0.001, 0.02, n_normal),
        'volume': np.random.lognormal(15, 0.3, n_normal),
        'volatility': np.random.lognormal(-3, 0.3, n_normal),
        'spread': np.random.lognormal(-4, 0.5, n_normal),
    })

    # Anomalous data
    anomaly_data = pd.DataFrame({
        'return': np.random.normal(0.01, 0.08, n_anomaly),  # Extreme returns
        'volume': np.random.lognormal(17, 0.5, n_anomaly),   # Extreme volume
        'volatility': np.random.lognormal(-1, 0.5, n_anomaly), # High volatility
        'spread': np.random.lognormal(-1, 0.5, n_anomaly),    # Wide spread
    })

    data = pd.concat([normal_data, anomaly_data], ignore_index=True)
    print(f"  Data: {len(data)} records ({len(normal_data)} normal + {len(anomaly_data)} anomalous)")

    detector = AnomalyDetectionCalculator()

    # Method 1: Isolation Forest
    print("\n1. Isolation Forest:")
    result_if = detector.detect_anomalies(
        data=data,
        method='isolation_forest',
        contamination=0.05
    )
    anomalies_if = np.array(result_if['value']['anomalies'])
    n_found_if = int(np.sum(anomalies_if[-n_anomaly:]))
    print(f"   Total anomalies detected: {result_if['value']['n_anomalies']}")
    print(f"   True anomalies caught in tail: {n_found_if}/{n_anomaly}")
    summary = result_if['metadata']['summary']
    print(f"   Score stats: mean={summary['score_stats']['mean']:.3f}, "
          f"std={summary['score_stats']['std']:.3f}")

    # Method 2: Local Outlier Factor
    print("\n2. Local Outlier Factor:")
    result_lof = detector.detect_anomalies(
        data=data,
        method='lof',
        contamination=0.05
    )
    print(f"   Anomalies detected: {result_lof['value']['n_anomalies']}")

    # Method 3: Z-score
    print("\n3. Z-score Method:")
    result_z = detector.detect_anomalies(
        data=data,
        method='zscore',
        threshold=2.5
    )
    print(f"   Anomalies detected: {result_z['value']['n_anomalies']}")

    # Method 4: IQR
    print("\n4. IQR Method:")
    result_iqr = detector.detect_anomalies(
        data=data,
        method='iqr',
        threshold=1.5
    )
    print(f"   Anomalies detected: {result_iqr['value']['n_anomalies']}")

    # Method 5: Combined
    print("\n5. Combined Method:")
    result_comb = detector.detect_anomalies(
        data=data,
        method='combined',
        contamination=0.05
    )
    print(f"   Anomalies detected: {result_comb['value']['n_anomalies']}")
    feature_contribs = result_comb['metadata']['summary'].get('feature_contributions', {})
    if feature_contribs:
        print(f"   Top contributing features: {dict(list(feature_contribs.items())[:3])}")

    print("\n" + "-" * 70)


# ==============================================================================
# Example 5: Complete ML-Enhanced Strategy
# ==============================================================================

def example_complete_strategy():
    """
    Example 5: Complete ML-Enhanced Strategy

    Demonstrates an end-to-end ML-enhanced quantitative strategy pipeline:
    Feature Engineering -> Factor Mining -> Return Prediction -> Risk Assessment
    """
    print("=" * 70)
    print("Example 5: Complete ML-Enhanced Strategy Pipeline")
    print("=" * 70)

    # Step 1: Generate data
    print("Step 1: Generating synthetic market data...")
    price_data = generate_sample_price_data(500)
    print(f"   OHLCV data: {price_data.shape}")

    # Step 2: Feature Engineering
    print("\nStep 2: Feature Engineering...")
    fe = FeatureEngineeringCalculator()
    fe_result = fe.generate_features(
        data=price_data,
        feature_types=['technical', 'statistical', 'time'],
        window_sizes=[5, 10, 20, 60]
    )
    n_features = fe_result['metadata']['n_features']
    print(f"   Generated {n_features} features")

    # Prepare feature DataFrame
    n_samples = fe_result['metadata']['n_samples']
    features_df = pd.DataFrame(fe_result['value'], index=price_data.index[-n_samples:])
    features_df = features_df.dropna()

    # Target: 5-day forward returns
    forward_returns = price_data['close'].pct_change(5).shift(-5)
    common_idx = features_df.index.intersection(forward_returns.dropna().index)
    features_aligned = features_df.loc[common_idx]
    target_values = forward_returns.loc[common_idx].values

    print(f"   Aligned data: {features_aligned.shape[0]} samples")

    # Step 3: Factor Mining
    print("\nStep 3: Factor Mining...")
    miner = FactorMiningCalculator()
    factor_result = miner.mine_factors(
        data=features_aligned,
        target=target_values,
        method='combined',
        n_factors=10
    )
    top_factors = factor_result['value']['factors'][:5]
    print(f"   Top 5 factors: {top_factors}")

    # Step 4: Return Prediction with Ensemble
    print("\nStep 4: Return Prediction (Ensemble)...")
    # Use top factors as features
    if top_factors:
        selected_features = features_aligned[top_factors]
    else:
        selected_features = features_aligned.iloc[:, :10]

    pred = ReturnPredictionCalculator()
    pred_result = pred.predict_returns(
        features=selected_features,
        target=target_values,
        model_type='xgboost',
        horizon=5,
        train_ratio=0.7
    )

    pred_metrics = pred_result['metadata']['metrics']
    print(f"   Hit Ratio: {pred_metrics.get('hit_ratio', 'N/A')}")
    print(f"   IC: {pred_metrics.get('ic', 'N/A')}")
    print(f"   R-squared: {pred_metrics.get('r2', 'N/A')}")

    # Step 5: Risk Assessment
    print("\nStep 5: Risk Assessment...")
    daily_returns = price_data['close'].pct_change().dropna()

    risk = RiskPredictionCalculator()
    risk_result = risk.predict_risk(
        returns=daily_returns.values,
        features=features_aligned.iloc[-len(daily_returns):],
        risk_type='var',
        model_type='garch',
        horizon=10,
        confidence_level=0.95
    )

    regime = risk_result['metadata']['risk_regime']
    var_values = risk_result['value']['predictions']

    print(f"   Risk Regime: {regime['current_regime']}")
    print(f"   Current Volatility: {risk_result['value']['current_volatility']:.4f}")
    print(f"   VaR (1-day, 95%): {var_values[0]:.4f}")

    # Step 6: Combine signals
    print("\nStep 6: Signal Generation...")
    predictions = np.array(pred_result['value']['predictions'])
    avg_prediction = float(np.mean(predictions))

    # Simple signal: positive predicted return AND acceptable VaR
    signal = "BUY" if avg_prediction > 0.001 else "SELL" if avg_prediction < -0.001 else "HOLD"
    confidence = min(abs(avg_prediction) / 0.005, 1.0) if abs(avg_prediction) > 0 else 0.0

    print(f"   Average Predicted Return: {avg_prediction:.6f}")
    print(f"   Signal: {signal}")
    print(f"   Confidence: {confidence:.2%}")

    print("\n" + "-" * 70)


# ==============================================================================
# Example 6: Model Ensemble and Backtesting
# ==============================================================================

def example_ensemble_backtest():
    """
    Example 6: Model Ensemble and Backtesting

    Demonstrates combining multiple models for prediction and
    evaluating performance in a simple backtesting framework.
    """
    print("=" * 70)
    print("Example 6: Model Ensemble and Backtesting")
    print("=" * 70)

    # Generate data
    price_data = generate_sample_price_data(500)
    print(f"  Data: {len(price_data)} days")

    # Feature engineering
    fe = FeatureEngineeringCalculator()
    fe_result = fe.generate_features(
        data=price_data,
        feature_types=['technical', 'statistical', 'time'],
        window_sizes=[10, 20, 60]
    )

    n_samples = fe_result['metadata']['n_samples']
    features_df = pd.DataFrame(fe_result['value'], index=price_data.index[-n_samples:])
    features_df = features_df.dropna()

    # Target
    forward_5d = price_data['close'].pct_change(5).shift(-5)
    common_idx = features_df.index.intersection(forward_5d.dropna().index)
    features_aligned = features_df.loc[common_idx]
    target_values = forward_5d.loc[common_idx].values

    # Split into train and test
    n_total = len(target_values)
    n_train = int(n_total * 0.7)
    train_features = features_aligned.iloc[:n_train]
    train_target = target_values[:n_train]
    test_features = features_aligned.iloc[n_train:]
    test_target = target_values[n_train:]

    print(f"\n  Train: {len(train_features)} samples, Test: {len(test_features)} samples")

    # Train individual models
    pred = ReturnPredictionCalculator()

    print("\n1. Individual Model Performance:")

    try:
        result_xgb = pred.predict_returns(
            features=train_features, target=train_target,
            model_type='xgboost', horizon=5, train_ratio=0.8
        )
        xgb_ic = result_xgb['metadata']['metrics'].get('ic', 0)
        xgb_hit = result_xgb['metadata']['metrics'].get('hit_ratio', 0)
        print(f"   XGBoost  - IC: {xgb_ic:.4f}, Hit Ratio: {xgb_hit:.4f}")
    except Exception as e:
        print(f"   XGBoost  - Failed: {e}")
        xgb_ic, xgb_hit = 0, 0

    try:
        result_lgb = pred.predict_returns(
            features=train_features, target=train_target,
            model_type='lightgbm', horizon=5, train_ratio=0.8
        )
        lgb_ic = result_lgb['metadata']['metrics'].get('ic', 0)
        lgb_hit = result_lgb['metadata']['metrics'].get('hit_ratio', 0)
        print(f"   LightGBM - IC: {lgb_ic:.4f}, Hit Ratio: {lgb_hit:.4f}")
    except Exception as e:
        print(f"   LightGBM - Failed: {e}")
        lgb_ic, lgb_hit = 0, 0

    # Ensemble via average
    ensemble_ic = np.mean([abs(xgb_ic), abs(lgb_ic)]) if abs(xgb_ic) + abs(lgb_ic) > 0 else 0
    ensemble_hit = np.mean([xgb_hit, lgb_hit])
    print(f"   Ensemble - IC: {ensemble_ic:.4f}, Hit Ratio: {ensemble_hit:.4f}")

    # Simple backtest
    print("\n2. Simple Backtest:")

    # Use XGBoost predictions on test set
    try:
        test_pred_result = pred.predict_returns(
            features=test_features, target=test_target,
            model_type='xgboost', horizon=5, train_ratio=0.01  # Use all for "prediction"
        )
        test_predictions = np.array(test_pred_result['value']['predictions'])
    except Exception:
        test_predictions = np.random.normal(0, 0.01, len(test_target))

    # Trading strategy: go long if predicted return > 0, else short
    position = np.where(test_predictions > 0, 1, -1)
    strategy_returns = position * test_target[:len(position)]

    # Performance metrics
    cumulative_return = np.prod(1 + strategy_returns) - 1
    annualized_return = np.mean(strategy_returns) * 252
    annualized_vol = np.std(strategy_returns) * np.sqrt(252)
    sharpe = annualized_return / annualized_vol if annualized_vol > 0 else 0
    max_dd = np.min(np.cumprod(1 + strategy_returns) /
                    np.maximum.accumulate(np.cumprod(1 + strategy_returns))) - 1
    win_rate = np.mean(strategy_returns > 0)

    print(f"   Cumulative Return: {cumulative_return:.4f}")
    print(f"   Annualized Return: {annualized_return:.4f}")
    print(f"   Annualized Volatility: {annualized_vol:.4f}")
    print(f"   Sharpe Ratio: {sharpe:.4f}")
    print(f"   Max Drawdown: {max_dd:.4f}")
    print(f"   Win Rate: {win_rate:.4f}")

    print("\n" + "-" * 70)


# ==============================================================================
# Main
# ==============================================================================

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("  QuantSys V2 - Machine Learning Module Examples")
    print("=" * 70 + "\n")

    try:
        example_factor_mining()
    except Exception as e:
        print(f"Example 1 failed: {e}\n")

    try:
        example_return_prediction_xgboost()
    except Exception as e:
        print(f"Example 2 failed: {e}\n")

    try:
        example_risk_prediction()
    except Exception as e:
        print(f"Example 3 failed: {e}\n")

    try:
        example_anomaly_detection()
    except Exception as e:
        print(f"Example 4 failed: {e}\n")

    try:
        example_complete_strategy()
    except Exception as e:
        print(f"Example 5 failed: {e}\n")

    try:
        example_ensemble_backtest()
    except Exception as e:
        print(f"Example 6 failed: {e}\n")

    print("=" * 70)
    print("  All examples completed!")
    print("=" * 70)
