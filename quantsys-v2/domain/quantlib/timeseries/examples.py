"""
Time Series Modeling Examples
==============================

Comprehensive usage examples for all time series modeling modules.

Author: QuantSys V2 Team
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from domain.quantlib.timeseries import (
    ARIMACalculator,
    GARCHCalculator,
    CointegrationCalculator,
    GrangerCausalityCalculator,
    KalmanFilterCalculator
)


# ============================================================================
# Example 1: ARIMA Modeling and Forecasting
# ============================================================================

def example_arima():
    """
    Example: Fit ARIMA model and generate forecasts.
    """
    print("=" * 80)
    print("Example 1: ARIMA Modeling and Forecasting")
    print("=" * 80)

    # Generate sample data (AR(1) process)
    np.random.seed(42)
    n = 200
    data = np.zeros(n)
    data[0] = np.random.randn()
    for t in range(1, n):
        data[t] = 0.7 * data[t-1] + np.random.randn()

    # Initialize calculator
    calc = ARIMACalculator()

    # Automatic order selection
    print("\n1. Automatic Order Selection")
    auto_result = calc.auto_select_order(data, max_p=5, max_d=2, max_q=5)
    optimal_order = auto_result['value']['optimal_order']
    print(f"   Optimal order: {optimal_order}")
    print(f"   AIC: {auto_result['value']['aic']:.2f}")

    # Fit ARIMA model
    print("\n2. Fit ARIMA Model")
    fit_result = calc.fit(data, order=optimal_order)
    print(f"   AIC: {fit_result['value']['aic']:.2f}")
    print(f"   BIC: {fit_result['value']['bic']:.2f}")
    print(f"   Converged: {fit_result['metadata']['converged']}")

    # Diagnose residuals
    print("\n3. Residual Diagnostics")
    diag_result = calc.diagnose_residuals(fit_result)
    print(f"   Ljung-Box p-value: {diag_result['value'].get('ljung_box_pvalue', 'N/A')}")
    print(f"   Residuals normal: {diag_result['value'].get('residuals_normal', 'N/A')}")

    # Forecast
    print("\n4. Generate Forecast")
    forecast_result = calc.forecast(fit_result, data, steps=10, confidence_level=0.95)
    print(f"   10-step forecast: {forecast_result['value']['forecast'][:3]}...")
    print(f"   Forecast mean: {forecast_result['metadata']['forecast_mean']:.4f}")

    return fit_result, forecast_result


# ============================================================================
# Example 2: GARCH Volatility Modeling
# ============================================================================

def example_garch():
    """
    Example: Model volatility with GARCH and calculate VaR.
    """
    print("\n" + "=" * 80)
    print("Example 2: GARCH Volatility Modeling")
    print("=" * 80)

    # Generate sample returns with volatility clustering
    np.random.seed(42)
    n = 500
    returns = np.random.randn(n) * 0.01

    # Add volatility clustering
    for t in range(1, n):
        if abs(returns[t-1]) > 0.02:
            returns[t] *= 2

    # Initialize calculator
    calc = GARCHCalculator()

    # Detect volatility clustering
    print("\n1. Detect Volatility Clustering")
    cluster_result = calc.detect_volatility_clustering(returns, window=20)
    print(f"   Clustering score: {cluster_result['value']['clustering_score']:.4f}")
    print(f"   Has clustering: {cluster_result['metadata']['has_clustering']}")

    # Fit GARCH model
    print("\n2. Fit GARCH(1,1) Model")
    fit_result = calc.fit(returns, p=1, q=1, vol_model='GARCH')
    print(f"   AIC: {fit_result['value']['aic']:.2f}")
    print(f"   Persistence: {fit_result['metadata']['persistence']:.4f}")
    print(f"   Mean volatility: {fit_result['metadata']['volatility_stats']['mean_volatility']:.4f}")

    # Compare models
    print("\n3. Compare GARCH Models")
    compare_result = calc.compare_models(returns)
    print(f"   Best model: {compare_result['value']['best_model']}")
    print(f"   Best AIC: {compare_result['value']['best_aic']:.2f}")

    # Forecast volatility
    print("\n4. Forecast Volatility")
    forecast_result = calc.forecast_volatility(fit_result, returns, steps=10)
    print(f"   10-day volatility forecast: {forecast_result['value']['volatility_forecast'][:3]}...")

    # Calculate VaR
    print("\n5. Calculate Value at Risk (VaR)")
    var_result = calc.calculate_var(fit_result, returns, confidence_level=0.95, horizon=1)
    print(f"   95% VaR (1-day): {var_result['metadata']['var_1day']:.4f}")
    print(f"   95% CVaR (1-day): {var_result['metadata']['cvar_1day']:.4f}")

    return fit_result, var_result


# ============================================================================
# Example 3: Cointegration and Pairs Trading
# ============================================================================

def example_cointegration():
    """
    Example: Test cointegration and generate pairs trading signals.
    """
    print("\n" + "=" * 80)
    print("Example 3: Cointegration and Pairs Trading")
    print("=" * 80)

    # Generate cointegrated series
    np.random.seed(42)
    n = 200
    series1 = np.cumsum(np.random.randn(n))
    series2 = 2.0 * series1 + np.random.randn(n) * 0.5  # Cointegrated with series1

    # Initialize calculator
    calc = CointegrationCalculator()

    # Engle-Granger test
    print("\n1. Engle-Granger Cointegration Test")
    eg_result = calc.engle_granger_test(series1, series2)
    print(f"   Test statistic: {eg_result['value']['test_statistic']:.4f}")
    print(f"   P-value: {eg_result['value']['p_value']:.4f}")
    print(f"   Is cointegrated: {eg_result['value']['is_cointegrated']}")
    print(f"   Hedge ratio: {eg_result['metadata']['hedge_ratio']:.4f}")

    # Error Correction Model
    print("\n2. Error Correction Model (ECM)")
    ecm_result = calc.estimate_ecm(series1, series2)
    print(f"   Adjustment speed: {ecm_result['value']['adjustment_speed']:.4f}")
    print(f"   Half-life: {ecm_result['value']['half_life']:.2f} periods")
    print(f"   Converges: {ecm_result['metadata']['converges']}")

    # Calculate spread
    print("\n3. Calculate Cointegration Spread")
    spread_result = calc.calculate_spread(series1, series2)
    print(f"   Hedge ratio: {spread_result['value']['hedge_ratio']:.4f}")
    print(f"   Current z-score: {spread_result['metadata']['spread_stats']['current_z_score']:.4f}")

    # Generate trading signals
    print("\n4. Generate Pairs Trading Signals")
    signal_result = calc.generate_trading_signals(spread_result, entry_threshold=2.0, exit_threshold=0.5)
    print(f"   Long positions: {signal_result['metadata']['n_long']}")
    print(f"   Short positions: {signal_result['metadata']['n_short']}")
    print(f"   % in market: {signal_result['metadata']['pct_in_market']:.2f}%")

    return eg_result, signal_result


# ============================================================================
# Example 4: Granger Causality Testing
# ============================================================================

def example_granger_causality():
    """
    Example: Test Granger causality between time series.
    """
    print("\n" + "=" * 80)
    print("Example 4: Granger Causality Testing")
    print("=" * 80)

    # Generate series with causal relationship
    np.random.seed(42)
    n = 200

    # X causes Y (with lag)
    x = np.random.randn(n)
    y = np.zeros(n)
    y[0] = np.random.randn()
    for t in range(1, n):
        y[t] = 0.5 * x[t-1] + 0.3 * y[t-1] + np.random.randn() * 0.5

    # Initialize calculator
    calc = GrangerCausalityCalculator()

    # Test X -> Y
    print("\n1. Test if X Granger-causes Y")
    test_result = calc.test(y, x, maxlag=5)
    print(f"   X Granger-causes Y: {test_result['value']['x_granger_causes_y']}")
    print(f"   Optimal lag: {test_result['value']['optimal_lag']}")
    print(f"   Min p-value: {test_result['value']['min_pvalue']:.6f}")

    # Bidirectional test
    print("\n2. Bidirectional Causality Test")
    bidir_result = calc.bidirectional_test(x, y, maxlag=5)
    print(f"   Relationship: {bidir_result['value']['relationship']}")
    print(f"   X -> Y: {bidir_result['value']['series1_causes_series2']}")
    print(f"   Y -> X: {bidir_result['value']['series2_causes_series1']}")

    # Optimal lag selection
    print("\n3. Select Optimal Lag")
    lag_result = calc.select_optimal_lag(y, x, maxlag=10, ic='aic')
    print(f"   Optimal lag (AIC): {lag_result['value']['optimal_lag']}")

    # Instantaneous causality
    print("\n4. Instantaneous Causality")
    instant_result = calc.instantaneous_causality(x, y, maxlag=3)
    print(f"   Residual correlation: {instant_result['value']['residual_correlation']:.4f}")
    print(f"   Has instantaneous causality: {instant_result['value']['has_instantaneous_causality']}")

    return test_result, bidir_result


# ============================================================================
# Example 5: Kalman Filtering
# ============================================================================

def example_kalman_filter():
    """
    Example: Apply Kalman filter for state estimation and smoothing.
    """
    print("\n" + "=" * 80)
    print("Example 5: Kalman Filtering")
    print("=" * 80)

    # Generate noisy observations of a random walk
    np.random.seed(42)
    n = 100
    true_state = np.cumsum(np.random.randn(n) * 0.1)
    observations = true_state + np.random.randn(n) * 0.5

    # Initialize calculator
    calc = KalmanFilterCalculator()

    # Method 1: Use local level model (simplified)
    print("\n1. Local Level Model (Random Walk + Noise)")
    ll_result = calc.fit_local_level(observations)
    print(f"   Level variance: {ll_result['value']['level_variance']:.6f}")
    print(f"   Observation variance: {ll_result['value']['obs_variance']:.6f}")
    print(f"   Signal-to-noise ratio: {ll_result['metadata']['signal_to_noise_ratio']:.4f}")

    # Method 2: Manual Kalman filter setup
    print("\n2. Manual Kalman Filter Setup")

    # State space matrices
    F = np.array([[1.0]])  # Random walk
    H = np.array([[1.0]])  # Direct observation
    Q = np.array([[0.01]])  # Process noise
    R = np.array([[0.25]])  # Observation noise

    # Filter
    filter_result = calc.filter(observations, F, H, Q, R)
    print(f"   Log-likelihood: {filter_result['value']['log_likelihood']:.2f}")

    # Smooth
    print("\n3. Apply RTS Smoother")
    smooth_result = calc.smooth(filter_result)
    filtered_states = np.array(filter_result['value']['filtered_states']).flatten()
    smoothed_states = np.array(smooth_result['value']['smoothed_states']).flatten()
    print(f"   Filtered state (last): {filtered_states[-1]:.4f}")
    print(f"   Smoothed state (last): {smoothed_states[-1]:.4f}")
    print(f"   True state (last): {true_state[-1]:.4f}")

    # Predict
    print("\n4. Predict Future States")
    predict_result = calc.predict(filter_result, steps=10)
    predictions = np.array(predict_result['value']['predicted_states']).flatten()
    print(f"   10-step predictions: {predictions[:3]}...")

    return ll_result, smooth_result


# ============================================================================
# Example 6: Complete Trading Strategy Pipeline
# ============================================================================

def example_trading_strategy():
    """
    Example: Complete pipeline for pairs trading strategy.
    """
    print("\n" + "=" * 80)
    print("Example 6: Complete Pairs Trading Strategy Pipeline")
    print("=" * 80)

    # Generate two stock price series
    np.random.seed(42)
    n = 250  # 1 year of daily data

    # Stock A: base random walk
    stock_a = 100 + np.cumsum(np.random.randn(n) * 0.5)

    # Stock B: cointegrated with A
    stock_b = 50 + 0.5 * stock_a + np.cumsum(np.random.randn(n) * 0.3)

    print(f"\nAnalyzing {n} days of price data for Stock A and Stock B")

    # Step 1: Test for cointegration
    print("\n1. Test Cointegration")
    coint_calc = CointegrationCalculator()
    coint_result = coint_calc.engle_granger_test(stock_a, stock_b)

    if coint_result['value']['is_cointegrated']:
        print(f"   ✓ Stocks are cointegrated (p={coint_result['value']['p_value']:.4f})")
        hedge_ratio = coint_result['metadata']['hedge_ratio']
        print(f"   Hedge ratio: {hedge_ratio:.4f}")
    else:
        print(f"   ✗ Stocks are NOT cointegrated")
        return None

    # Step 2: Test causality
    print("\n2. Test Granger Causality")
    causality_calc = GrangerCausalityCalculator()
    causality_result = causality_calc.bidirectional_test(stock_a, stock_b, maxlag=5)
    print(f"   Relationship: {causality_result['value']['relationship']}")

    # Step 3: Calculate spread and z-score
    print("\n3. Calculate Trading Spread")
    spread_result = coint_calc.calculate_spread(stock_a, stock_b, hedge_ratio=hedge_ratio)
    current_z = spread_result['metadata']['spread_stats']['current_z_score']
    print(f"   Current z-score: {current_z:.4f}")

    # Step 4: Generate trading signals
    print("\n4. Generate Trading Signals")
    signal_result = coint_calc.generate_trading_signals(
        spread_result,
        entry_threshold=2.0,
        exit_threshold=0.5
    )
    print(f"   Long signals: {signal_result['metadata']['n_long']}")
    print(f"   Short signals: {signal_result['metadata']['n_short']}")
    print(f"   Time in market: {signal_result['metadata']['pct_in_market']:.2f}%")

    # Step 5: Risk management with GARCH
    print("\n5. Risk Management (GARCH Volatility)")
    returns_a = np.diff(stock_a) / stock_a[:-1]
    garch_calc = GARCHCalculator()
    garch_result = garch_calc.fit(returns_a, p=1, q=1)
    var_result = garch_calc.calculate_var(garch_result, returns_a, confidence_level=0.95)
    print(f"   95% VaR: {var_result['metadata']['var_1day']:.4f}")

    print("\n" + "=" * 80)
    print("Strategy Summary:")
    print(f"  - Cointegrated pair with hedge ratio {hedge_ratio:.4f}")
    print(f"  - Current position: {'LONG' if current_z < -2 else 'SHORT' if current_z > 2 else 'FLAT'}")
    print(f"  - Risk (95% VaR): {abs(var_result['metadata']['var_1day']):.4f}")
    print("=" * 80)

    return {
        'cointegration': coint_result,
        'causality': causality_result,
        'signals': signal_result,
        'risk': var_result
    }


# ============================================================================
# Main Execution
# ============================================================================

def main():
    """
    Run all examples.
    """
    print("\n" + "=" * 80)
    print("TIME SERIES MODELING EXAMPLES")
    print("QuantSys V2 - Migrated from FinceptTerminal")
    print("=" * 80)

    # Run examples
    example_arima()
    example_garch()
    example_cointegration()
    example_granger_causality()
    example_kalman_filter()
    example_trading_strategy()

    print("\n" + "=" * 80)
    print("All examples completed successfully!")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()
