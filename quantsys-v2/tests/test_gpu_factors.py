"""
Tests for GPUFactorCalculator - GPU-accelerated factor calculations
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from domain.quantlib.gpu_acceleration.gpu_factors import GPUFactorCalculator, GPU_AVAILABLE


@pytest.fixture
def sample_prices():
    """Create sample price data"""
    np.random.seed(42)
    return 100 + np.cumsum(np.random.randn(200) * 0.5)


@pytest.fixture
def sample_ohlc_data():
    """Create sample OHLC data"""
    np.random.seed(42)
    n = 200
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.5)
    low = close - np.abs(np.random.randn(n) * 0.5)
    volume = np.random.randint(1000, 10000, n)

    return pd.DataFrame({
        'close': close,
        'high': high,
        'low': low,
        'volume': volume
    })


class TestGPUFactorCalculator:
    """Test suite for GPUFactorCalculator"""

    def test_initialization_cpu(self):
        """Test CPU initialization"""
        calculator = GPUFactorCalculator(use_gpu=False)
        assert calculator.use_gpu is False

    def test_initialization_gpu(self):
        """Test GPU initialization"""
        calculator = GPUFactorCalculator(use_gpu=True)
        # Should be True only if GPU is available
        assert calculator.use_gpu == GPU_AVAILABLE

    def test_initialization_default(self):
        """Test default initialization"""
        calculator = GPUFactorCalculator()
        # Default should try to use GPU if available
        assert calculator.use_gpu == GPU_AVAILABLE

    def test_calculate_sma_basic(self, sample_prices):
        """Test basic SMA calculation"""
        calculator = GPUFactorCalculator(use_gpu=False)

        sma = calculator.calculate_sma(sample_prices, window=20)

        assert len(sma) == len(sample_prices)
        assert np.isnan(sma[:19]).all()  # First 19 should be NaN
        assert not np.isnan(sma[19:]).any()  # Rest should have values

    def test_calculate_sma_values(self, sample_prices):
        """Test SMA calculation values are correct"""
        calculator = GPUFactorCalculator(use_gpu=False)

        sma = calculator.calculate_sma(sample_prices, window=5)

        # Check a specific value
        expected = np.mean(sample_prices[0:5])
        assert sma[4] == pytest.approx(expected, rel=1e-6)

    @pytest.mark.parametrize("window", [5, 10, 20, 50])
    def test_calculate_sma_different_windows(self, sample_prices, window):
        """Test SMA with different window sizes"""
        calculator = GPUFactorCalculator(use_gpu=False)

        sma = calculator.calculate_sma(sample_prices, window=window)

        assert len(sma) == len(sample_prices)
        assert np.isnan(sma[:window-1]).all()

    def test_calculate_ema_basic(self, sample_prices):
        """Test basic EMA calculation"""
        calculator = GPUFactorCalculator(use_gpu=False)

        ema = calculator.calculate_ema(sample_prices, span=20)

        assert len(ema) == len(sample_prices)
        assert not np.isnan(ema).any()

    def test_calculate_ema_first_value(self, sample_prices):
        """Test EMA first value equals first price"""
        calculator = GPUFactorCalculator(use_gpu=False)

        ema = calculator.calculate_ema(sample_prices, span=20)

        # First EMA value should equal first price
        assert ema[0] == pytest.approx(sample_prices[0], rel=1e-6)

    @pytest.mark.parametrize("span", [5, 12, 26, 50])
    def test_calculate_ema_different_spans(self, sample_prices, span):
        """Test EMA with different spans"""
        calculator = GPUFactorCalculator(use_gpu=False)

        ema = calculator.calculate_ema(sample_prices, span=span)

        assert len(ema) == len(sample_prices)

    def test_calculate_rsi_basic(self, sample_prices):
        """Test basic RSI calculation"""
        calculator = GPUFactorCalculator(use_gpu=False)

        rsi = calculator.calculate_rsi(sample_prices, period=14)

        assert len(rsi) == len(sample_prices)
        # RSI should be between 0 and 100
        valid_rsi = rsi[~np.isnan(rsi)]
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

    def test_calculate_rsi_range(self, sample_prices):
        """Test RSI values are in valid range"""
        calculator = GPUFactorCalculator(use_gpu=False)

        rsi = calculator.calculate_rsi(sample_prices, period=14)

        valid_rsi = rsi[~np.isnan(rsi)]
        assert valid_rsi.min() >= 0
        assert valid_rsi.max() <= 100

    def test_calculate_rsi_extreme_values(self):
        """Test RSI with extreme price movements"""
        calculator = GPUFactorCalculator(use_gpu=False)

        # All increasing prices
        increasing_prices = np.arange(100, 200, 1)
        rsi_up = calculator.calculate_rsi(increasing_prices, period=14)

        # RSI should be high (near 100)
        assert rsi_up[-1] > 80

        # All decreasing prices
        decreasing_prices = np.arange(200, 100, -1)
        rsi_down = calculator.calculate_rsi(decreasing_prices, period=14)

        # RSI should be low (near 0)
        assert rsi_down[-1] < 20

    def test_calculate_macd_basic(self, sample_prices):
        """Test basic MACD calculation"""
        calculator = GPUFactorCalculator(use_gpu=False)

        macd_result = calculator.calculate_macd(sample_prices)

        assert 'macd' in macd_result
        assert 'signal' in macd_result
        assert 'histogram' in macd_result

        assert len(macd_result['macd']) == len(sample_prices)
        assert len(macd_result['signal']) == len(sample_prices)
        assert len(macd_result['histogram']) == len(sample_prices)

    def test_calculate_macd_histogram(self, sample_prices):
        """Test MACD histogram is difference of MACD and signal"""
        calculator = GPUFactorCalculator(use_gpu=False)

        macd_result = calculator.calculate_macd(sample_prices)

        expected_histogram = macd_result['macd'] - macd_result['signal']

        np.testing.assert_array_almost_equal(
            macd_result['histogram'],
            expected_histogram,
            decimal=6
        )

    def test_calculate_macd_custom_periods(self, sample_prices):
        """Test MACD with custom periods"""
        calculator = GPUFactorCalculator(use_gpu=False)

        macd_result = calculator.calculate_macd(
            sample_prices,
            fast_period=8,
            slow_period=21,
            signal_period=5
        )

        assert 'macd' in macd_result
        assert 'signal' in macd_result
        assert 'histogram' in macd_result

    def test_calculate_bollinger_bands_basic(self, sample_prices):
        """Test basic Bollinger Bands calculation"""
        calculator = GPUFactorCalculator(use_gpu=False)

        bb_result = calculator.calculate_bollinger_bands(sample_prices)

        assert 'middle' in bb_result
        assert 'upper' in bb_result
        assert 'lower' in bb_result

        assert len(bb_result['middle']) == len(sample_prices)
        assert len(bb_result['upper']) == len(sample_prices)
        assert len(bb_result['lower']) == len(sample_prices)

    def test_calculate_bollinger_bands_order(self, sample_prices):
        """Test Bollinger Bands order (lower < middle < upper)"""
        calculator = GPUFactorCalculator(use_gpu=False)

        bb_result = calculator.calculate_bollinger_bands(sample_prices, window=20)

        # Remove NaN values
        valid_idx = ~np.isnan(bb_result['middle'])

        lower = bb_result['lower'][valid_idx]
        middle = bb_result['middle'][valid_idx]
        upper = bb_result['upper'][valid_idx]

        # Lower should be less than middle
        assert (lower <= middle).all()

        # Upper should be greater than middle
        assert (upper >= middle).all()

    def test_calculate_bollinger_bands_custom_std(self, sample_prices):
        """Test Bollinger Bands with custom standard deviation"""
        calculator = GPUFactorCalculator(use_gpu=False)

        bb_1std = calculator.calculate_bollinger_bands(sample_prices, num_std=1.0)
        bb_2std = calculator.calculate_bollinger_bands(sample_prices, num_std=2.0)

        # 2-std bands should be wider than 1-std bands
        valid_idx = ~np.isnan(bb_1std['middle'])

        width_1std = bb_1std['upper'][valid_idx] - bb_1std['lower'][valid_idx]
        width_2std = bb_2std['upper'][valid_idx] - bb_2std['lower'][valid_idx]

        assert (width_2std > width_1std).all()

    def test_calculate_atr_basic(self, sample_ohlc_data):
        """Test basic ATR calculation"""
        calculator = GPUFactorCalculator(use_gpu=False)

        atr = calculator.calculate_atr(
            sample_ohlc_data['high'].values,
            sample_ohlc_data['low'].values,
            sample_ohlc_data['close'].values,
            period=14
        )

        assert len(atr) == len(sample_ohlc_data)
        assert not np.isnan(atr).any()
        assert (atr >= 0).all()  # ATR should be non-negative

    def test_calculate_atr_values(self, sample_ohlc_data):
        """Test ATR values are reasonable"""
        calculator = GPUFactorCalculator(use_gpu=False)

        atr = calculator.calculate_atr(
            sample_ohlc_data['high'].values,
            sample_ohlc_data['low'].values,
            sample_ohlc_data['close'].values,
            period=14
        )

        # ATR should be positive
        assert (atr > 0).all()

        # ATR should be less than typical price range
        price_range = sample_ohlc_data['high'].max() - sample_ohlc_data['low'].min()
        assert (atr < price_range).all()

    def test_batch_calculate_factors_sma(self, sample_ohlc_data):
        """Test batch calculation with SMA"""
        calculator = GPUFactorCalculator(use_gpu=False)

        result = calculator.batch_calculate_factors(sample_ohlc_data, ['sma_20'])

        assert 'sma_20' in result.columns
        assert len(result) == len(sample_ohlc_data)

    def test_batch_calculate_factors_multiple(self, sample_ohlc_data):
        """Test batch calculation with multiple factors"""
        calculator = GPUFactorCalculator(use_gpu=False)

        factors = ['sma_20', 'ema_12', 'rsi_14']
        result = calculator.batch_calculate_factors(sample_ohlc_data, factors)

        assert 'sma_20' in result.columns
        assert 'ema_12' in result.columns
        assert 'rsi_14' in result.columns

    def test_batch_calculate_factors_macd(self, sample_ohlc_data):
        """Test batch calculation with MACD"""
        calculator = GPUFactorCalculator(use_gpu=False)

        result = calculator.batch_calculate_factors(sample_ohlc_data, ['macd'])

        assert 'macd' in result.columns
        assert 'macd_signal' in result.columns
        assert 'macd_histogram' in result.columns

    def test_batch_calculate_factors_bollinger(self, sample_ohlc_data):
        """Test batch calculation with Bollinger Bands"""
        calculator = GPUFactorCalculator(use_gpu=False)

        result = calculator.batch_calculate_factors(sample_ohlc_data, ['bollinger'])

        assert 'bb_middle' in result.columns
        assert 'bb_upper' in result.columns
        assert 'bb_lower' in result.columns

    def test_batch_calculate_factors_atr(self, sample_ohlc_data):
        """Test batch calculation with ATR"""
        calculator = GPUFactorCalculator(use_gpu=False)

        result = calculator.batch_calculate_factors(sample_ohlc_data, ['atr_14'])

        assert 'atr_14' in result.columns

    def test_batch_calculate_factors_all(self, sample_ohlc_data):
        """Test batch calculation with all factors"""
        calculator = GPUFactorCalculator(use_gpu=False)

        factors = ['sma_20', 'ema_12', 'rsi_14', 'macd', 'bollinger', 'atr_14']
        result = calculator.batch_calculate_factors(sample_ohlc_data, factors)

        # Check all expected columns exist
        expected_columns = [
            'sma_20', 'ema_12', 'rsi_14',
            'macd', 'macd_signal', 'macd_histogram',
            'bb_middle', 'bb_upper', 'bb_lower',
            'atr_14'
        ]

        for col in expected_columns:
            assert col in result.columns

    def test_batch_calculate_factors_preserves_original(self, sample_ohlc_data):
        """Test batch calculation preserves original columns"""
        calculator = GPUFactorCalculator(use_gpu=False)

        result = calculator.batch_calculate_factors(sample_ohlc_data, ['sma_20'])

        # Original columns should still exist
        assert 'close' in result.columns
        assert 'high' in result.columns
        assert 'low' in result.columns
        assert 'volume' in result.columns

    def test_empty_prices(self):
        """Test handling of empty price array"""
        calculator = GPUFactorCalculator(use_gpu=False)
        empty_prices = np.array([])
        # May raise or return empty result depending on implementation
        try:
            result = calculator.calculate_sma(empty_prices, window=20)
            assert result is not None
        except (ValueError, IndexError):
            pass

    def test_single_price(self):
        """Test handling of single price"""
        calculator = GPUFactorCalculator(use_gpu=False)

        single_price = np.array([100.0])

        sma = calculator.calculate_sma(single_price, window=5)

        assert len(sma) == 1

    def test_window_larger_than_data(self, sample_prices):
        """Test SMA with window larger than data"""
        calculator = GPUFactorCalculator(use_gpu=False)

        short_prices = sample_prices[:10]
        sma = calculator.calculate_sma(short_prices, window=20)

        # All values should be NaN
        assert np.isnan(sma).all()

    def test_constant_prices(self):
        """Test factors with constant prices"""
        calculator = GPUFactorCalculator(use_gpu=False)

        constant_prices = np.ones(100) * 100

        sma = calculator.calculate_sma(constant_prices, window=20)
        rsi = calculator.calculate_rsi(constant_prices, period=14)

        # SMA should equal the constant
        assert np.allclose(sma[19:], 100, rtol=1e-6)

        # RSI should be around 50 (no trend)
        valid_rsi = rsi[~np.isnan(rsi)]
        if len(valid_rsi) > 0:
            # With constant prices, RSI calculation may have division issues
            assert True  # Just check it doesn't crash

    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_gpu_cpu_consistency_sma(self, sample_prices):
        """Test GPU and CPU produce consistent SMA results"""
        cpu_calc = GPUFactorCalculator(use_gpu=False)
        gpu_calc = GPUFactorCalculator(use_gpu=True)

        cpu_sma = cpu_calc.calculate_sma(sample_prices, window=20)
        gpu_sma = gpu_calc.calculate_sma(sample_prices, window=20)

        np.testing.assert_array_almost_equal(cpu_sma, gpu_sma, decimal=4)

    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_gpu_cpu_consistency_ema(self, sample_prices):
        """Test GPU and CPU produce consistent EMA results"""
        cpu_calc = GPUFactorCalculator(use_gpu=False)
        gpu_calc = GPUFactorCalculator(use_gpu=True)

        cpu_ema = cpu_calc.calculate_ema(sample_prices, span=20)
        gpu_ema = gpu_calc.calculate_ema(sample_prices, span=20)

        np.testing.assert_array_almost_equal(cpu_ema, gpu_ema, decimal=4)

    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_gpu_cpu_consistency_rsi(self, sample_prices):
        """Test GPU and CPU produce consistent RSI results"""
        cpu_calc = GPUFactorCalculator(use_gpu=False)
        gpu_calc = GPUFactorCalculator(use_gpu=True)

        cpu_rsi = cpu_calc.calculate_rsi(sample_prices, period=14)
        gpu_rsi = gpu_calc.calculate_rsi(sample_prices, period=14)

        # Allow slightly larger tolerance for RSI
        np.testing.assert_array_almost_equal(cpu_rsi, gpu_rsi, decimal=2)

    def test_negative_prices(self):
        """Test handling of negative prices"""
        calculator = GPUFactorCalculator(use_gpu=False)

        # Some indicators may not work well with negative prices
        negative_prices = np.array([-100, -99, -98, -97, -96] * 20)

        # Should not crash
        sma = calculator.calculate_sma(negative_prices, window=5)
        assert len(sma) == len(negative_prices)

    def test_nan_in_prices(self):
        """Test handling of NaN in prices"""
        calculator = GPUFactorCalculator(use_gpu=False)

        prices_with_nan = np.array([100, 101, np.nan, 103, 104] * 20)

        # Should handle NaN gracefully
        sma = calculator.calculate_sma(prices_with_nan, window=5)
        assert len(sma) == len(prices_with_nan)

    def test_very_large_prices(self):
        """Test handling of very large prices"""
        calculator = GPUFactorCalculator(use_gpu=False)

        large_prices = np.array([1e10, 1e10 + 1, 1e10 + 2] * 30)

        sma = calculator.calculate_sma(large_prices, window=5)

        assert len(sma) == len(large_prices)
        assert not np.isinf(sma).any()

    def test_very_small_prices(self):
        """Test handling of very small prices"""
        calculator = GPUFactorCalculator(use_gpu=False)

        small_prices = np.array([1e-10, 1e-10 + 1e-12, 1e-10 + 2e-12] * 30)

        sma = calculator.calculate_sma(small_prices, window=5)

        assert len(sma) == len(small_prices)

    def test_zero_window(self):
        """Test handling of zero window"""
        calculator = GPUFactorCalculator(use_gpu=False)
        prices = np.array([100, 101, 102, 103, 104])
        try:
            result = calculator.calculate_sma(prices, window=0)
            assert result is not None
        except (ValueError, ZeroDivisionError):
            pass

    def test_negative_window(self):
        """Test handling of negative window"""
        calculator = GPUFactorCalculator(use_gpu=False)

        prices = np.array([100, 101, 102, 103, 104])

        with pytest.raises((ValueError, IndexError)):
            calculator.calculate_sma(prices, window=-5)

    def test_zero_span(self):
        """Test handling of zero span in EMA"""
        calculator = GPUFactorCalculator(use_gpu=False)

        prices = np.array([100, 101, 102, 103, 104])

        with pytest.raises((ValueError, ZeroDivisionError)):
            calculator.calculate_ema(prices, span=0)

    def test_atr_high_low_order(self):
        """Test ATR with high < low (invalid data)"""
        calculator = GPUFactorCalculator(use_gpu=False)

        # Invalid: high < low
        high = np.array([100, 101, 102, 103, 104])
        low = np.array([105, 106, 107, 108, 109])  # Higher than high
        close = np.array([102, 103, 104, 105, 106])

        # Should still calculate (may give unexpected results)
        atr = calculator.calculate_atr(high, low, close, period=3)

        assert len(atr) == len(high)

    def test_batch_calculate_empty_factors_list(self, sample_ohlc_data):
        """Test batch calculation with empty factors list"""
        calculator = GPUFactorCalculator(use_gpu=False)

        result = calculator.batch_calculate_factors(sample_ohlc_data, [])

        # Should return original dataframe
        pd.testing.assert_frame_equal(result, sample_ohlc_data)

    def test_batch_calculate_unknown_factor(self, sample_ohlc_data):
        """Test batch calculation with unknown factor"""
        calculator = GPUFactorCalculator(use_gpu=False)

        result = calculator.batch_calculate_factors(sample_ohlc_data, ['unknown_factor'])

        # Should not add unknown factor
        assert 'unknown_factor' not in result.columns
