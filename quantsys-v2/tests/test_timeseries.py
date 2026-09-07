"""
Unit Tests for Time Series Analysis Module
===========================================

Tests the TimeSeriesAnalyzer functionality.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from domain.quantlib.timeseries import TimeSeriesAnalyzer
from domain.quantlib.core.exceptions import DataValidationError, InsufficientDataError


def _has_statsmodels() -> bool:
    """Check if statsmodels is installed."""
    try:
        import statsmodels
        return True
    except ImportError:
        return False


class TestTimeSeriesAnalyzer:
    """Test TimeSeriesAnalyzer class."""

    def test_analyze_linear_trend(self):
        """Test linear trend analysis."""
        # Create data with known linear trend
        np.random.seed(42)
        n = 100
        time = np.arange(n)
        trend = 2.0 + 0.5 * time  # intercept=2, slope=0.5
        noise = np.random.randn(n) * 0.1
        data = trend + noise

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.analyze_trend(data, trend_type='linear')

        # Check slope and intercept are close to true values
        assert abs(result['value']['slope'] - 0.5) < 0.05
        assert abs(result['value']['intercept'] - 2.0) < 0.2

        # Check metadata
        assert result['metadata']['trend_significant'] == True
        assert result['metadata']['trend_direction'] == 'upward'
        assert result['metadata']['r_squared'] > 0.95

    def test_analyze_log_linear_trend(self):
        """Test log-linear trend analysis."""
        np.random.seed(42)
        n = 100
        time = np.arange(n)
        # Exponential growth: y = exp(2 + 0.01*t)
        data = np.exp(2.0 + 0.01 * time) * (1 + np.random.randn(n) * 0.01)

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.analyze_trend(data, trend_type='log_linear')

        # Check slope is positive (exponential growth)
        assert result['value']['slope'] > 0
        assert result['metadata']['trend_direction'] == 'upward'

    def test_analyze_trend_with_dates(self):
        """Test trend analysis with datetime index."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        data = np.arange(50) * 0.3 + np.random.randn(50) * 0.5

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.analyze_trend(data, dates=dates)

        assert 'fitted_values' in result['metadata']
        assert len(result['metadata']['fitted_values']) == 50

    def test_analyze_trend_insufficient_data(self):
        """Test that insufficient data raises error."""
        data = [1, 2, 3]  # Only 3 points
        analyzer = TimeSeriesAnalyzer()

        with pytest.raises(ValueError, match="Insufficient data"):
            analyzer.analyze_trend(data)

    def test_analyze_trend_invalid_type(self):
        """Test that invalid trend type raises error."""
        data = np.random.randn(50)
        analyzer = TimeSeriesAnalyzer()

        with pytest.raises(DataValidationError, match="Invalid trend_type"):
            analyzer.analyze_trend(data, trend_type='invalid')

    def test_log_linear_negative_data(self):
        """Test that log-linear with negative data raises error."""
        data = np.array([-1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11])  # 11 points, first is negative
        analyzer = TimeSeriesAnalyzer()

        with pytest.raises(DataValidationError, match="positive data"):
            analyzer.analyze_trend(data, trend_type='log_linear')

    @pytest.mark.skipif(
        not _has_statsmodels(),
        reason="statsmodels not installed"
    )
    def test_stationarity_adf(self):
        """Test ADF stationarity test."""
        # Stationary data (white noise)
        np.random.seed(42)
        stationary_data = np.random.randn(100)

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.test_stationarity(stationary_data, test_type='adf')

        assert 'adf' in result['value']
        assert 'statistic' in result['value']['adf']
        assert 'p_value' in result['value']['adf']
        assert result['value']['adf']['is_stationary'] == True

    @pytest.mark.skipif(
        not _has_statsmodels(),
        reason="statsmodels not installed"
    )
    def test_stationarity_non_stationary(self):
        """Test stationarity test on non-stationary data."""
        # Non-stationary data (random walk)
        np.random.seed(42)
        non_stationary = np.cumsum(np.random.randn(100))

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.test_stationarity(non_stationary, test_type='adf')

        # Random walk should be non-stationary
        assert result['metadata']['conclusion'] == 'non_stationary'

    @pytest.mark.skipif(
        not _has_statsmodels(),
        reason="statsmodels not installed"
    )
    def test_stationarity_both_tests(self):
        """Test both ADF and KPSS tests."""
        np.random.seed(42)
        data = np.random.randn(100)

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.test_stationarity(data, test_type='both')

        assert 'adf' in result['value']
        assert 'kpss' in result['value']
        assert 'conclusion' in result['metadata']

    @pytest.mark.skipif(
        not _has_statsmodels(),
        reason="statsmodels not installed"
    )
    def test_decompose_additive(self):
        """Test additive trend decomposition."""
        # Create data with trend and seasonality
        np.random.seed(42)
        n = 120
        time = np.arange(n)
        trend = 0.5 * time
        seasonal = 10 * np.sin(2 * np.pi * time / 12)
        noise = np.random.randn(n) * 2
        data = trend + seasonal + noise

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.decompose_trend(data, model='additive', period=12)

        assert 'trend' in result['value']
        assert 'seasonal' in result['value']
        assert 'residual' in result['value']
        assert len(result['value']['trend']) == n

    @pytest.mark.skipif(
        not _has_statsmodels(),
        reason="statsmodels not installed"
    )
    def test_decompose_multiplicative(self):
        """Test multiplicative trend decomposition."""
        np.random.seed(42)
        n = 120
        time = np.arange(n)
        trend = 10 + 0.5 * time
        seasonal = 1 + 0.3 * np.sin(2 * np.pi * time / 12)
        noise = 1 + np.random.randn(n) * 0.1
        data = trend * seasonal * noise

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.decompose_trend(data, model='multiplicative', period=12)

        assert 'trend_strength' in result['metadata']
        assert 'seasonal_strength' in result['metadata']

    def test_calculate_autocorrelation(self):
        """Test ACF and PACF calculation."""
        # AR(1) process
        np.random.seed(42)
        n = 100
        phi = 0.7
        data = np.zeros(n)
        data[0] = np.random.randn()
        for i in range(1, n):
            data[i] = phi * data[i-1] + np.random.randn()

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.calculate_autocorrelation(data, max_lag=20)

        assert 'acf' in result['value']
        assert 'pacf' in result['value']
        assert len(result['value']['acf']) == 21  # 0 to max_lag
        assert len(result['value']['pacf']) == 21

        # ACF[0] should be 1
        assert abs(result['value']['acf'][0] - 1.0) < 0.01

        # For AR(1), PACF should be significant only at lag 1
        assert result['metadata']['has_autocorrelation'] == True

    def test_autocorrelation_white_noise(self):
        """Test ACF/PACF on white noise."""
        np.random.seed(42)
        data = np.random.randn(200)

        analyzer = TimeSeriesAnalyzer()
        result = analyzer.calculate_autocorrelation(data, max_lag=20)

        # White noise should have few significant lags
        significant_lags = result['metadata']['significant_acf_lags']
        # Allow up to 5% false positives (1 out of 20 lags)
        assert len(significant_lags) <= 2

    def test_timing_metadata(self):
        """Test that timing decorator adds execution time."""
        data = np.random.randn(100)
        analyzer = TimeSeriesAnalyzer()
        result = analyzer.analyze_trend(data)

        assert 'execution_time_ms' in result['metadata']
        assert result['metadata']['execution_time_ms'] > 0

    def test_result_format(self):
        """Test standardized result format."""
        data = np.random.randn(50)
        analyzer = TimeSeriesAnalyzer()
        result = analyzer.analyze_trend(data)

        # Check standard fields
        assert 'value' in result
        assert 'method' in result
        assert 'parameters' in result
        assert 'metadata' in result
        assert 'timestamp' in result
        assert 'calculator' in result

        assert result['calculator'] == 'TimeSeriesAnalyzer'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
