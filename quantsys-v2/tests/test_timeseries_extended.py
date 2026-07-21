"""
Unit Tests for Extended Time Series Analysis Methods
====================================================

Tests the new time series methods (ARIMA, GARCH, VAR, cointegration).
"""

import pytest
import numpy as np
import pandas as pd

from domain.quantlib.timeseries import TimeSeriesAnalyzer
from domain.quantlib.core.exceptions import DataValidationError, InsufficientDataError, ModelFitError


class TestExtendedTimeSeriesMethods:
    """Test extended time series analysis methods."""

    def test_fit_arima_basic(self):
        """Test basic ARIMA model fitting."""
        np.random.seed(42)
        # Generate AR(1) process
        data = np.cumsum(np.random.randn(100)) + 100

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.fit_arima(data, order=(1, 1, 1))

        assert 'order' in result['value']
        assert result['value']['order'] == (1, 1, 1)
        assert 'aic' in result['value']
        assert 'bic' in result['value']
        assert 'parameters' in result['value']

    def test_fit_arima_seasonal(self):
        """Test ARIMA with seasonal component."""
        np.random.seed(42)
        # Generate data with trend and seasonality
        t = np.arange(100)
        seasonal = 10 * np.sin(2 * np.pi * t / 12)
        trend = 0.5 * t
        noise = np.random.randn(100)
        data = trend + seasonal + noise + 100

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.fit_arima(
            data,
            order=(1, 0, 1),
            seasonal_order=(1, 0, 1, 12)
        )

        assert result['value']['seasonal_order'] == (1, 0, 1, 12)
        assert 'residual_mean' in result['metadata']

    def test_fit_arima_insufficient_data(self):
        """Test that ARIMA rejects insufficient data."""
        data = np.random.randn(20)  # Too short
        analyzer = TimeSeriesAnalyzer()

        with pytest.raises(ValueError, match="Insufficient data"):
            analyzer.fit_arima(data)

    def test_predict_arima(self):
        """Test ARIMA forecasting."""
        np.random.seed(42)
        data = np.cumsum(np.random.randn(100)) + 100

        analyzer = TimeSeriesAnalyzer()

        # Fit model
        fit_result = analyzer.fit_arima(data, order=(1, 1, 1))

        # Make predictions
        pred_result = analyzer.predict_arima(fit_result, data, steps=10)

        assert 'forecast' in pred_result['value']
        assert len(pred_result['value']['forecast']) == 10
        assert 'lower_bound' in pred_result['value']
        assert 'upper_bound' in pred_result['value']
        assert len(pred_result['value']['lower_bound']) == 10

    def test_predict_arima_confidence_levels(self):
        """Test ARIMA predictions with different confidence levels."""
        np.random.seed(42)
        data = np.cumsum(np.random.randn(100)) + 100

        analyzer = TimeSeriesAnalyzer()
        fit_result = analyzer.fit_arima(data, order=(1, 1, 1))

        # 90% confidence
        pred_90 = analyzer.predict_arima(fit_result, data, steps=5, confidence_level=0.90)

        # 95% confidence
        pred_95 = analyzer.predict_arima(fit_result, data, steps=5, confidence_level=0.95)

        # 95% interval should be wider
        width_90 = pred_90['value']['upper_bound'][0] - pred_90['value']['lower_bound'][0]
        width_95 = pred_95['value']['upper_bound'][0] - pred_95['value']['lower_bound'][0]
        assert width_95 > width_90

    def test_fit_garch(self):
        """Test GARCH model fitting."""
        np.random.seed(42)
        # Generate returns with volatility clustering
        returns = np.random.randn(200) * 0.02

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.fit_garch(returns, p=1, q=1)

        assert 'parameters' in result['value']
        assert 'aic' in result['value']
        assert 'bic' in result['value']
        assert 'next_volatility' in result['value']
        assert 'mean_volatility' in result['metadata']

    def test_fit_garch_different_orders(self):
        """Test GARCH with different orders."""
        np.random.seed(42)
        returns = np.random.randn(200) * 0.02

        analyzer = TimeSeriesAnalyzer()

        # GARCH(1,1)
        result_11 = analyzer.fit_garch(returns, p=1, q=1)

        # GARCH(2,1)
        result_21 = analyzer.fit_garch(returns, p=2, q=1)

        assert result_11['parameters']['p'] == 1
        assert result_21['parameters']['p'] == 2

    def test_fit_garch_insufficient_data(self):
        """Test that GARCH rejects insufficient data."""
        returns = np.random.randn(30)  # Too short
        analyzer = TimeSeriesAnalyzer()

        with pytest.raises(ValueError, match="Insufficient data"):
            analyzer.fit_garch(returns)

    def test_fit_var(self):
        """Test VAR model fitting."""
        np.random.seed(42)
        # Generate two correlated time series
        n = 100
        series1 = np.cumsum(np.random.randn(n))
        series2 = 0.5 * series1 + np.cumsum(np.random.randn(n))

        data = pd.DataFrame({
            'series1': series1,
            'series2': series2
        })

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.fit_var(data, maxlags=5)

        assert 'selected_lag' in result['value']
        assert 'aic' in result['value']
        assert 'bic' in result['value']
        assert result['value']['n_series'] == 2

    def test_fit_var_multiple_series(self):
        """Test VAR with multiple time series."""
        np.random.seed(42)
        n = 100
        data = pd.DataFrame({
            'series1': np.cumsum(np.random.randn(n)),
            'series2': np.cumsum(np.random.randn(n)),
            'series3': np.cumsum(np.random.randn(n))
        })

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.fit_var(data, maxlags=3)

        assert result['value']['n_series'] == 3
        assert 'causality_tests' in result['metadata']

    def test_fit_var_insufficient_series(self):
        """Test that VAR requires at least 2 series."""
        data = pd.DataFrame({'series1': np.random.randn(100)})
        analyzer = TimeSeriesAnalyzer()

        with pytest.raises(DataValidationError, match="at least 2 time series"):
            analyzer.fit_var(data)

    def test_fit_var_insufficient_data(self):
        """Test that VAR rejects insufficient data."""
        data = pd.DataFrame({
            'series1': np.random.randn(20),
            'series2': np.random.randn(20)
        })
        analyzer = TimeSeriesAnalyzer()

        with pytest.raises(InsufficientDataError):
            analyzer.fit_var(data)

    def test_cointegration_test_cointegrated(self):
        """Test cointegration test with cointegrated series."""
        np.random.seed(42)
        # Generate cointegrated series
        n = 100
        common_trend = np.cumsum(np.random.randn(n))
        series1 = common_trend + np.random.randn(n) * 0.1
        series2 = 2 * common_trend + np.random.randn(n) * 0.1

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.cointegration_test(series1, series2)

        assert 'test_statistic' in result['value']
        assert 'p_value' in result['value']
        assert 'critical_values' in result['value']
        assert 'is_cointegrated' in result['metadata']

    def test_cointegration_test_not_cointegrated(self):
        """Test cointegration test with independent series."""
        np.random.seed(42)
        # Generate independent random walks
        series1 = np.cumsum(np.random.randn(100))
        series2 = np.cumsum(np.random.randn(100))

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.cointegration_test(series1, series2)

        # Independent series should not be cointegrated
        assert 'is_cointegrated' in result['metadata']
        assert 'conclusion' in result['metadata']

    def test_cointegration_test_unequal_length(self):
        """Test that cointegration test rejects unequal length series."""
        series1 = np.random.randn(100)
        series2 = np.random.randn(80)
        analyzer = TimeSeriesAnalyzer()

        with pytest.raises(DataValidationError, match="same length"):
            analyzer.cointegration_test(series1, series2)

    def test_timing_metadata_extended(self):
        """Test that timing decorator works for extended methods."""
        np.random.seed(42)
        data = np.cumsum(np.random.randn(100))
        analyzer = TimeSeriesAnalyzer()
        result = analyzer.fit_arima(data, order=(1, 1, 1))

        assert 'execution_time_ms' in result['metadata']
        assert result['metadata']['execution_time_ms'] > 0

    def test_result_format_extended(self):
        """Test standardized result format for extended methods."""
        np.random.seed(42)
        data = np.cumsum(np.random.randn(100))
        analyzer = TimeSeriesAnalyzer()
        result = analyzer.fit_arima(data, order=(1, 1, 1))

        # Check standard fields
        assert 'value' in result
        assert 'method' in result
        assert 'parameters' in result
        assert 'metadata' in result
        assert 'timestamp' in result
        assert 'calculator' in result

        assert result['calculator'] == 'TimeSeriesAnalyzer'
        assert result['method'] == 'fit_arima'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
