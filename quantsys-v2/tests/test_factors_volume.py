"""
Tests for Volume Indicators
============================

Test suite for OBV, MFI, VWAP, and volume-related calculations.
"""

import pytest
import numpy as np

from domain.quantlib.factors.volume import VolumeFactors
from domain.quantlib.core.exceptions import InsufficientDataError, DataValidationError


class TestVolumeFactors:
    """Test volume indicator calculations."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return VolumeFactors()

    @pytest.fixture
    def sample_klines(self):
        """Create sample K-line data."""
        np.random.seed(42)
        base_price = 100.0
        prices = base_price + np.cumsum(np.random.randn(150) * 2)

        klines = []
        for i, price in enumerate(prices):
            klines.append({
                'open': float(price - 0.5),
                'high': float(price + 1.0),
                'low': float(price - 1.0),
                'close': float(price),
                'volume': float(1000000 + np.random.randint(-100000, 100000))
            })
        return klines

    # =========================================================================
    # OBV Tests
    # =========================================================================

    def test_obv_basic(self, calculator, sample_klines):
        """Test OBV calculation."""
        result = calculator.obv(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'obv'
        assert 'trend' in result['metadata']

    def test_obv_uptrend(self, calculator):
        """Test OBV with uptrend data."""
        klines = []
        for i in range(20):
            klines.append({
                'close': 100.0 + i,
                'volume': 1000000
            })

        result = calculator.obv(klines)
        # In uptrend, OBV should be positive
        assert result['value'] > 0
        assert result['metadata']['trend'] == 'bullish'

    def test_obv_downtrend(self, calculator):
        """Test OBV with downtrend data."""
        klines = []
        for i in range(20):
            klines.append({
                'close': 100.0 - i,
                'volume': 1000000
            })

        result = calculator.obv(klines)
        # In downtrend, OBV should be negative
        assert result['value'] < 0
        assert result['metadata']['trend'] == 'bearish'

    def test_obv_insufficient_data(self, calculator):
        """Test OBV with insufficient data."""
        short_klines = [{'close': 100.0, 'volume': 1000000}]

        with pytest.raises(InsufficientDataError):
            calculator.obv(short_klines)

    # =========================================================================
    # MFI Tests
    # =========================================================================

    def test_mfi14_basic(self, calculator, sample_klines):
        """Test MFI14 calculation."""
        result = calculator.mfi14(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert 0 <= result['value'] <= 100
        assert result['method'] == 'mfi14'
        assert result['parameters']['period'] == 14

    def test_mfi_range(self, calculator, sample_klines):
        """Test that MFI is always in valid range."""
        result = calculator.mfi14(sample_klines)
        assert 0 <= result['value'] <= 100

    def test_mfi_overbought_oversold(self, calculator):
        """Test MFI overbought/oversold detection."""
        # Create uptrend data (should be overbought)
        klines = []
        for i in range(20):
            klines.append({
                'high': 102.0 + i * 2,
                'low': 98.0 + i * 2,
                'close': 100.0 + i * 2,
                'volume': 1000000
            })

        result = calculator.mfi14(klines)
        # In strong uptrend, MFI should be high
        assert result['value'] > 50

    def test_mfi_insufficient_data(self, calculator):
        """Test MFI with insufficient data."""
        short_klines = [
            {'high': 101.0, 'low': 99.0, 'close': 100.0, 'volume': 1000000}
            for _ in range(10)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.mfi14(short_klines)

    # =========================================================================
    # VWAP Tests
    # =========================================================================

    def test_vwap_basic(self, calculator, sample_klines):
        """Test VWAP calculation."""
        result = calculator.vwap(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['value'] > 0
        assert result['method'] == 'vwap'
        assert result['parameters']['period'] == 20

    def test_vwap_metadata(self, calculator, sample_klines):
        """Test VWAP metadata."""
        result = calculator.vwap(sample_klines)

        assert 'total_volume' in result['metadata']
        assert 'latest_close' in result['metadata']
        assert 'price_position' in result['metadata']
        assert result['metadata']['price_position'] in ['above', 'below']

    def test_vwap_calculation_accuracy(self, calculator):
        """Test VWAP calculation with known values."""
        klines = []
        for i in range(25):
            klines.append({
                'high': 102.0,
                'low': 98.0,
                'close': 100.0,
                'volume': 1000000
            })

        result = calculator.vwap(klines)
        # With constant prices, VWAP should equal typical price
        typical_price = (102.0 + 98.0 + 100.0) / 3.0
        assert abs(result['value'] - typical_price) < 0.01

    def test_vwap_insufficient_data(self, calculator):
        """Test VWAP with insufficient data."""
        short_klines = [
            {'high': 101.0, 'low': 99.0, 'close': 100.0, 'volume': 1000000}
            for _ in range(15)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.vwap(short_klines)

    # =========================================================================
    # Volume MA Tests
    # =========================================================================

    def test_volume_ma5_basic(self, calculator, sample_klines):
        """Test Volume MA5 calculation."""
        result = calculator.volume_ma5(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['value'] > 0
        assert result['method'] == 'volume_ma5'
        assert result['parameters']['period'] == 5

    def test_volume_ma10_basic(self, calculator, sample_klines):
        """Test Volume MA10 calculation."""
        result = calculator.volume_ma10(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['value'] > 0
        assert result['method'] == 'volume_ma10'
        assert result['parameters']['period'] == 10

    def test_volume_ma_calculation_accuracy(self, calculator):
        """Test Volume MA calculation with known values."""
        klines = []
        for i in range(10):
            klines.append({
                'close': 100.0,
                'volume': 1000000.0
            })

        result = calculator.volume_ma5(klines)
        # With constant volume, MA should equal the volume
        assert abs(result['value'] - 1000000.0) < 0.01

    def test_volume_ma5_insufficient_data(self, calculator):
        """Test Volume MA5 with insufficient data."""
        short_klines = [{'close': 100.0, 'volume': 1000000} for _ in range(3)]

        with pytest.raises(InsufficientDataError):
            calculator.volume_ma5(short_klines)

    def test_volume_ma10_insufficient_data(self, calculator):
        """Test Volume MA10 with insufficient data."""
        short_klines = [{'close': 100.0, 'volume': 1000000} for _ in range(7)]

        with pytest.raises(InsufficientDataError):
            calculator.volume_ma10(short_klines)

    # =========================================================================
    # Volume Ratio Tests
    # =========================================================================

    def test_volume_ratio_basic(self, calculator, sample_klines):
        """Test volume ratio calculation."""
        result = calculator.volume_ratio(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['value'] > 0
        assert result['method'] == 'volume_ratio'

    def test_volume_ratio_high_volume(self, calculator):
        """Test volume ratio with high volume."""
        klines = []
        for i in range(10):
            volume = 1000000.0 if i < 9 else 2000000.0  # Last day has 2x volume
            klines.append({
                'close': 100.0,
                'volume': volume
            })

        result = calculator.volume_ratio(klines)
        # MA5 = (1000000*4 + 2000000)/5 = 1200000, ratio = 2000000/1200000 = 1.67
        assert 1.6 < result['value'] < 1.8
        assert result['metadata']['high_volume'] == True

    def test_volume_ratio_low_volume(self, calculator):
        """Test volume ratio with low volume."""
        klines = []
        for i in range(10):
            volume = 1000000.0 if i < 9 else 400000.0  # Last day has 0.4x volume
            klines.append({
                'close': 100.0,
                'volume': volume
            })

        result = calculator.volume_ratio(klines)
        # Last volume is 0.4x average
        assert result['value'] < 0.5
        assert result['metadata']['low_volume'] == True

    def test_volume_ratio_insufficient_data(self, calculator):
        """Test volume ratio with insufficient data."""
        short_klines = [{'close': 100.0, 'volume': 1000000} for _ in range(3)]

        with pytest.raises(InsufficientDataError):
            calculator.volume_ratio(short_klines)

    # =========================================================================
    # Turnover Rate Tests
    # =========================================================================

    def test_turnover_rate_with_shares(self, calculator, sample_klines):
        """Test turnover rate with total shares provided."""
        result = calculator.turnover_rate(sample_klines, total_shares=10000000.0)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['value'] > 0
        assert result['method'] == 'turnover_rate'
        assert result['metadata']['has_total_shares'] is True

    def test_turnover_rate_without_shares(self, calculator, sample_klines):
        """Test turnover rate without total shares (returns volume)."""
        result = calculator.turnover_rate(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['metadata']['has_total_shares'] is False
        # Should return volume as proxy
        assert result['value'] == result['metadata']['latest_volume']

    def test_turnover_rate_calculation(self, calculator):
        """Test turnover rate calculation accuracy."""
        klines = [{'close': 100.0, 'volume': 1000000.0}]
        total_shares = 10000000.0

        result = calculator.turnover_rate(klines, total_shares=total_shares)
        # Turnover = (1000000 / 10000000) * 100 = 10%
        assert abs(result['value'] - 10.0) < 0.01

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_empty_klines(self, calculator):
        """Test with empty K-line data."""
        with pytest.raises((DataValidationError, InsufficientDataError)):
            calculator.obv([])

    def test_all_methods_supported(self, calculator):
        """Test that all methods are listed in supported methods."""
        supported = calculator.get_supported_methods()

        expected_methods = [
            'obv', 'mfi14', 'vwap',
            'volume_ma5', 'volume_ma10',
            'volume_ratio', 'turnover_rate'
        ]

        for method in expected_methods:
            assert method in supported

    def test_timing_metadata(self, calculator, sample_klines):
        """Test that timing metadata is included."""
        result = calculator.obv(sample_klines)

        assert 'metadata' in result
        assert 'execution_time_ms' in result['metadata']
        assert result['metadata']['execution_time_ms'] >= 0

    def test_zero_volume_handling(self, calculator):
        """Test handling of zero volume."""
        klines = []
        for i in range(25):
            klines.append({
                'high': 102.0,
                'low': 98.0,
                'close': 100.0,
                'volume': 0.0
            })

        # VWAP should raise error with zero volume
        with pytest.raises(ValueError):
            calculator.vwap(klines)
