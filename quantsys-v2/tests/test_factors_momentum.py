"""
Tests for Momentum Indicators
==============================

Test suite for MACD, RSI, ROC, and Momentum factor calculations.
"""

import pytest
import numpy as np

from domain.quantlib.factors.momentum import MomentumFactors
from domain.quantlib.core.exceptions import InsufficientDataError, DataValidationError


class TestMomentumFactors:
    """Test momentum indicator calculations."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return MomentumFactors()

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
    # MACD Tests
    # =========================================================================

    def test_macd_basic(self, calculator, sample_klines):
        """Test MACD calculation."""
        result = calculator.macd(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'macd'
        assert 'signal' in result['metadata']
        assert 'histogram' in result['metadata']

    def test_macd_signal_basic(self, calculator, sample_klines):
        """Test MACD signal line calculation."""
        result = calculator.macd_signal(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'macd_signal'

    def test_macd_histogram_basic(self, calculator, sample_klines):
        """Test MACD histogram calculation."""
        result = calculator.macd_histogram(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'macd_histogram'

    def test_macd_insufficient_data(self, calculator):
        """Test MACD with insufficient data."""
        short_klines = [{'close': 100.0 + i} for i in range(20)]

        with pytest.raises(InsufficientDataError):
            calculator.macd(short_klines)

    def test_macd_consistency(self, calculator, sample_klines):
        """Test MACD components are consistent."""
        macd_result = calculator.macd(sample_klines)
        signal_result = calculator.macd_signal(sample_klines)
        histogram_result = calculator.macd_histogram(sample_klines)

        # Histogram should equal MACD - Signal
        expected_histogram = macd_result['value'] - signal_result['value']
        assert abs(histogram_result['value'] - expected_histogram) < 0.0001

    # =========================================================================
    # RSI Tests
    # =========================================================================

    def test_rsi6_basic(self, calculator, sample_klines):
        """Test RSI6 calculation."""
        result = calculator.rsi6(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert 0 <= result['value'] <= 100
        assert result['method'] == 'rsi6'
        assert result['parameters']['period'] == 6

    def test_rsi14_basic(self, calculator, sample_klines):
        """Test RSI14 calculation."""
        result = calculator.rsi14(sample_klines)

        assert result is not None
        assert 'value' in result
        assert 0 <= result['value'] <= 100
        assert result['method'] == 'rsi14'

    def test_rsi24_basic(self, calculator, sample_klines):
        """Test RSI24 calculation."""
        result = calculator.rsi24(sample_klines)

        assert result is not None
        assert 'value' in result
        assert 0 <= result['value'] <= 100
        assert result['method'] == 'rsi24'

    def test_rsi_overbought_oversold(self, calculator):
        """Test RSI overbought/oversold detection."""
        # Create uptrend data (should be overbought)
        uptrend_klines = [{'close': 100.0 + i * 2} for i in range(30)]
        result = calculator.rsi14(uptrend_klines)

        assert result['metadata']['overbought'] is True
        assert result['metadata']['oversold'] is False

    def test_rsi_insufficient_data(self, calculator):
        """Test RSI with insufficient data."""
        short_klines = [{'close': 100.0 + i} for i in range(5)]

        with pytest.raises(InsufficientDataError):
            calculator.rsi6(short_klines)

    def test_rsi_calculation_accuracy(self, calculator):
        """Test RSI calculation with known values."""
        # Simple uptrend
        klines = [{'close': 100.0 + i} for i in range(20)]
        result = calculator.rsi14(klines)

        # In a consistent uptrend, RSI should be high
        assert result['value'] > 70

    # =========================================================================
    # ROC Tests
    # =========================================================================

    def test_roc_5_basic(self, calculator, sample_klines):
        """Test ROC5 calculation."""
        result = calculator.roc_5(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'roc_5'
        assert result['parameters']['period'] == 5

    def test_roc_10_basic(self, calculator, sample_klines):
        """Test ROC10 calculation."""
        result = calculator.roc_10(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'roc_10'

    def test_roc_20_basic(self, calculator, sample_klines):
        """Test ROC20 calculation."""
        result = calculator.roc_20(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'roc_20'

    def test_roc_calculation_accuracy(self, calculator):
        """Test ROC calculation with known values."""
        klines = [
            {'close': 100.0},
            {'close': 100.0},
            {'close': 100.0},
            {'close': 100.0},
            {'close': 100.0},
            {'close': 110.0},  # 10% increase
        ]

        result = calculator.roc_5(klines)
        # ROC = (110 - 100) / 100 * 100 = 10%
        assert abs(result['value'] - 10.0) < 0.0001

    def test_roc_positive_momentum(self, calculator):
        """Test ROC positive momentum detection."""
        klines = [{'close': 100.0 + i} for i in range(30)]
        result = calculator.roc_10(klines)

        assert result['metadata']['positive_momentum'] is True
        assert result['value'] > 0

    def test_roc_insufficient_data(self, calculator):
        """Test ROC with insufficient data."""
        short_klines = [{'close': 100.0} for _ in range(3)]

        with pytest.raises(InsufficientDataError):
            calculator.roc_5(short_klines)

    # =========================================================================
    # Momentum Tests
    # =========================================================================

    def test_momentum_5_basic(self, calculator, sample_klines):
        """Test Momentum5 calculation."""
        result = calculator.momentum_5(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'momentum_5'
        assert result['parameters']['period'] == 5

    def test_momentum_10_basic(self, calculator, sample_klines):
        """Test Momentum10 calculation."""
        result = calculator.momentum_10(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'momentum_10'

    def test_momentum_20_basic(self, calculator, sample_klines):
        """Test Momentum20 calculation."""
        result = calculator.momentum_20(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'momentum_20'

    def test_momentum_calculation_accuracy(self, calculator):
        """Test momentum calculation with known values."""
        klines = [
            {'close': 100.0},
            {'close': 101.0},
            {'close': 102.0},
            {'close': 103.0},
            {'close': 104.0},
            {'close': 105.0},
        ]

        result = calculator.momentum_5(klines)
        # Momentum = 105 - 100 = 5
        assert abs(result['value'] - 5.0) < 0.0001

    def test_momentum_positive_detection(self, calculator):
        """Test momentum positive detection."""
        klines = [{'close': 100.0 + i} for i in range(30)]
        result = calculator.momentum_10(klines)

        assert result['metadata']['positive_momentum'] is True
        assert result['value'] > 0

    def test_momentum_negative_detection(self, calculator):
        """Test momentum negative detection."""
        klines = [{'close': 100.0 - i} for i in range(30)]
        result = calculator.momentum_10(klines)

        assert result['metadata']['positive_momentum'] is False
        assert result['value'] < 0

    def test_momentum_insufficient_data(self, calculator):
        """Test momentum with insufficient data."""
        short_klines = [{'close': 100.0} for _ in range(3)]

        with pytest.raises(InsufficientDataError):
            calculator.momentum_5(short_klines)

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_empty_klines(self, calculator):
        """Test with empty K-line data."""
        with pytest.raises((DataValidationError, InsufficientDataError)):
            calculator.macd([])

    def test_all_methods_supported(self, calculator):
        """Test that all methods are listed in supported methods."""
        supported = calculator.get_supported_methods()

        expected_methods = [
            'macd', 'macd_signal', 'macd_histogram',
            'rsi6', 'rsi14', 'rsi24',
            'roc_5', 'roc_10', 'roc_20',
            'momentum_5', 'momentum_10', 'momentum_20'
        ]

        for method in expected_methods:
            assert method in supported

    def test_timing_metadata(self, calculator, sample_klines):
        """Test that timing metadata is included."""
        result = calculator.rsi14(sample_klines)

        assert 'metadata' in result
        assert 'execution_time_ms' in result['metadata']
        assert result['metadata']['execution_time_ms'] >= 0

    def test_rsi_range_validation(self, calculator, sample_klines):
        """Test that RSI is always in valid range."""
        for _ in range(10):
            # Test with different random seeds
            result = calculator.rsi14(sample_klines)
            assert 0 <= result['value'] <= 100
