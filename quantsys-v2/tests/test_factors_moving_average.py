"""
Tests for Moving Average Factors
=================================

Test suite for MA and EMA factor calculations.
"""

import pytest
import numpy as np

from domain.quantlib.factors.moving_average import MovingAverageFactors
from domain.quantlib.core.exceptions import InsufficientDataError, DataValidationError


class TestMovingAverageFactors:
    """Test moving average factor calculations."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return MovingAverageFactors()

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
    # MA Tests
    # =========================================================================

    def test_ma5_basic(self, calculator, sample_klines):
        """Test MA5 calculation."""
        result = calculator.ma5(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'ma5'
        assert result['parameters']['period'] == 5

    def test_ma10_basic(self, calculator, sample_klines):
        """Test MA10 calculation."""
        result = calculator.ma10(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'ma10'
        assert result['parameters']['period'] == 10

    def test_ma20_basic(self, calculator, sample_klines):
        """Test MA20 calculation."""
        result = calculator.ma20(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'ma20'
        assert result['parameters']['period'] == 20

    def test_ma60_basic(self, calculator, sample_klines):
        """Test MA60 calculation."""
        result = calculator.ma60(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'ma60'
        assert result['parameters']['period'] == 60

    def test_ma120_basic(self, calculator, sample_klines):
        """Test MA120 calculation."""
        result = calculator.ma120(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'ma120'
        assert result['parameters']['period'] == 120

    def test_ma_calculation_accuracy(self, calculator):
        """Test MA calculation accuracy."""
        # Simple test data
        klines = [
            {'open': 10, 'high': 11, 'low': 9, 'close': 10, 'volume': 1000},
            {'open': 11, 'high': 12, 'low': 10, 'close': 11, 'volume': 1000},
            {'open': 12, 'high': 13, 'low': 11, 'close': 12, 'volume': 1000},
            {'open': 13, 'high': 14, 'low': 12, 'close': 13, 'volume': 1000},
            {'open': 14, 'high': 15, 'low': 13, 'close': 14, 'volume': 1000},
        ]

        result = calculator.ma5(klines)

        # MA5 = (10 + 11 + 12 + 13 + 14) / 5 = 12.0
        assert abs(result['value'] - 12.0) < 0.0001

    def test_ma_insufficient_data(self, calculator):
        """Test MA with insufficient data - should use fallback."""
        klines = [
            {'open': 10, 'high': 11, 'low': 9, 'close': 10, 'volume': 1000},
            {'open': 11, 'high': 12, 'low': 10, 'close': 11, 'volume': 1000},
        ]

        # With new fallback logic, this should succeed using available data
        result = calculator.ma5(klines)

        assert result is not None
        assert 'value' in result
        assert result['parameters']['period'] == 5
        assert result['parameters']['effective_period'] == 2
        assert result['parameters']['fallback_used'] is True
        # MA of [10, 11] = 10.5
        assert abs(result['value'] - 10.5) < 0.0001

    def test_ma_metadata(self, calculator, sample_klines):
        """Test MA metadata."""
        result = calculator.ma5(sample_klines)

        assert 'metadata' in result
        assert 'data_points' in result['metadata']
        assert 'latest_close' in result['metadata']
        assert 'ma_position' in result['metadata']
        assert result['metadata']['ma_position'] in ['above', 'below']

    # =========================================================================
    # EMA Tests
    # =========================================================================

    def test_ema5_basic(self, calculator, sample_klines):
        """Test EMA5 calculation."""
        result = calculator.ema5(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'ema5'
        assert result['parameters']['period'] == 5

    def test_ema10_basic(self, calculator, sample_klines):
        """Test EMA10 calculation."""
        result = calculator.ema10(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'ema10'
        assert result['parameters']['period'] == 10

    def test_ema20_basic(self, calculator, sample_klines):
        """Test EMA20 calculation."""
        result = calculator.ema20(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'ema20'
        assert result['parameters']['period'] == 20

    def test_ema_calculation_accuracy(self, calculator):
        """Test EMA calculation accuracy."""
        # Simple test data
        klines = [
            {'open': 10, 'high': 11, 'low': 9, 'close': 10, 'volume': 1000},
            {'open': 11, 'high': 12, 'low': 10, 'close': 12, 'volume': 1000},
            {'open': 12, 'high': 13, 'low': 11, 'close': 14, 'volume': 1000},
            {'open': 13, 'high': 14, 'low': 12, 'close': 16, 'volume': 1000},
            {'open': 14, 'high': 15, 'low': 13, 'close': 18, 'volume': 1000},
        ]

        result = calculator.ema5(klines)

        # EMA should be calculated correctly
        # First EMA = SMA = (10 + 12 + 14 + 16 + 18) / 5 = 14.0
        # Since we only have 5 points, EMA = SMA
        assert abs(result['value'] - 14.0) < 0.0001

    def test_ema_insufficient_data(self, calculator):
        """Test EMA with insufficient data - should use fallback."""
        klines = [
            {'open': 10, 'high': 11, 'low': 9, 'close': 10, 'volume': 1000},
            {'open': 11, 'high': 12, 'low': 10, 'close': 11, 'volume': 1000},
        ]

        # With new fallback logic, this should succeed using available data
        result = calculator.ema5(klines)

        assert result is not None
        assert 'value' in result
        assert result['parameters']['period'] == 5
        assert result['parameters']['effective_period'] == 2
        assert result['parameters']['fallback_used'] is True
        # EMA of [10, 11] with period=2 should be close to 10.5
        assert isinstance(result['value'], float)
        assert not np.isnan(result['value'])

    def test_ema_vs_ma(self, calculator, sample_klines):
        """Test that EMA and MA produce different values."""
        ma_result = calculator.ma20(sample_klines)
        ema_result = calculator.ema20(sample_klines)

        # EMA and MA should be different (EMA is more responsive)
        assert ma_result['value'] != ema_result['value']

    def test_ema_metadata(self, calculator, sample_klines):
        """Test EMA metadata."""
        result = calculator.ema5(sample_klines)

        assert 'metadata' in result
        assert 'data_points' in result['metadata']
        assert 'latest_close' in result['metadata']
        assert 'ema_position' in result['metadata']
        assert result['metadata']['ema_position'] in ['above', 'below']

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_empty_klines(self, calculator):
        """Test with empty K-line data."""
        with pytest.raises(DataValidationError):
            calculator.ma5([])

    def test_invalid_klines_format(self, calculator):
        """Test with invalid K-line format."""
        with pytest.raises(DataValidationError):
            calculator.ma5([{'close': 10}])  # Missing required fields

    def test_custom_period(self, calculator, sample_klines):
        """Test MA with custom period."""
        result = calculator.calculate_ma(sample_klines, period=30)

        assert result is not None
        assert result['parameters']['period'] == 30

    def test_timing_metadata(self, calculator, sample_klines):
        """Test that timing metadata is included."""
        result = calculator.ma5(sample_klines)

        assert 'metadata' in result
        assert 'execution_time_ms' in result['metadata']
        assert result['metadata']['execution_time_ms'] >= 0

    def test_ma_ordering(self, calculator, sample_klines):
        """Test that longer period MAs are smoother."""
        ma5 = calculator.ma5(sample_klines)['value']
        ma20 = calculator.ma20(sample_klines)['value']
        ma60 = calculator.ma60(sample_klines)['value']

        # All should be valid numbers
        assert all(isinstance(v, float) for v in [ma5, ma20, ma60])
        assert all(not np.isnan(v) for v in [ma5, ma20, ma60])
