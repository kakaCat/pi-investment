"""
Tests for Volatility Indicators
================================

Test suite for Bollinger Bands, ATR, Keltner Channels, and volatility calculations.
"""

import pytest
import numpy as np

from domain.quantlib.factors.volatility import VolatilityFactors
from domain.quantlib.core.exceptions import InsufficientDataError, DataValidationError


class TestVolatilityFactors:
    """Test volatility indicator calculations."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return VolatilityFactors()

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
    # Bollinger Bands Tests
    # =========================================================================

    def test_bollinger_upper_basic(self, calculator, sample_klines):
        """Test Bollinger upper band calculation."""
        result = calculator.bollinger_upper(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'bollinger_upper'
        assert 'middle' in result['metadata']
        assert 'lower' in result['metadata']

    def test_bollinger_middle_basic(self, calculator, sample_klines):
        """Test Bollinger middle band calculation."""
        result = calculator.bollinger_middle(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'bollinger_middle'

    def test_bollinger_lower_basic(self, calculator, sample_klines):
        """Test Bollinger lower band calculation."""
        result = calculator.bollinger_lower(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'bollinger_lower'

    def test_bollinger_bands_ordering(self, calculator, sample_klines):
        """Test that Bollinger bands are properly ordered."""
        upper = calculator.bollinger_upper(sample_klines)['value']
        middle = calculator.bollinger_middle(sample_klines)['value']
        lower = calculator.bollinger_lower(sample_klines)['value']

        # Upper > Middle > Lower
        assert upper > middle
        assert middle > lower

    def test_bollinger_bands_consistency(self, calculator, sample_klines):
        """Test that all three bands return consistent values."""
        upper_result = calculator.bollinger_upper(sample_klines)
        middle_result = calculator.bollinger_middle(sample_klines)
        lower_result = calculator.bollinger_lower(sample_klines)

        # Check metadata consistency
        assert abs(upper_result['metadata']['middle'] - middle_result['value']) < 0.0001
        assert abs(lower_result['metadata']['middle'] - middle_result['value']) < 0.0001

    def test_bollinger_insufficient_data(self, calculator):
        """Test Bollinger bands with insufficient data."""
        short_klines = [{'close': 100.0 + i} for i in range(15)]

        with pytest.raises(InsufficientDataError):
            calculator.bollinger_upper(short_klines)

    # =========================================================================
    # ATR Tests
    # =========================================================================

    def test_atr14_basic(self, calculator, sample_klines):
        """Test ATR14 calculation."""
        result = calculator.atr14(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['value'] > 0
        assert result['method'] == 'atr14'
        assert result['parameters']['period'] == 14

    def test_atr20_basic(self, calculator, sample_klines):
        """Test ATR20 calculation."""
        result = calculator.atr20(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['value'] > 0
        assert result['method'] == 'atr20'
        assert result['parameters']['period'] == 20

    def test_atr_positive_value(self, calculator, sample_klines):
        """Test that ATR is always positive."""
        atr14 = calculator.atr14(sample_klines)['value']
        atr20 = calculator.atr20(sample_klines)['value']

        assert atr14 > 0
        assert atr20 > 0

    def test_atr_insufficient_data(self, calculator):
        """Test ATR with insufficient data."""
        short_klines = [
            {'high': 101.0, 'low': 99.0, 'close': 100.0}
            for _ in range(10)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.atr14(short_klines)

    def test_atr_calculation_accuracy(self, calculator):
        """Test ATR calculation with known values."""
        # Simple data with constant range
        klines = []
        for i in range(30):
            klines.append({
                'high': 102.0,
                'low': 98.0,
                'close': 100.0,
                'volume': 1000000
            })

        result = calculator.atr14(klines)
        # With constant range of 4, ATR should be close to 4
        assert 3.5 < result['value'] < 4.5

    # =========================================================================
    # Keltner Channels Tests
    # =========================================================================

    def test_keltner_upper_basic(self, calculator, sample_klines):
        """Test Keltner upper channel calculation."""
        result = calculator.keltner_upper(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'keltner_upper'
        assert 'middle' in result['metadata']
        assert 'lower' in result['metadata']

    def test_keltner_middle_basic(self, calculator, sample_klines):
        """Test Keltner middle line calculation."""
        result = calculator.keltner_middle(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'keltner_middle'

    def test_keltner_lower_basic(self, calculator, sample_klines):
        """Test Keltner lower channel calculation."""
        result = calculator.keltner_lower(sample_klines)

        assert result is not None
        assert 'value' in result
        assert result['method'] == 'keltner_lower'

    def test_keltner_channels_ordering(self, calculator, sample_klines):
        """Test that Keltner channels are properly ordered."""
        upper = calculator.keltner_upper(sample_klines)['value']
        middle = calculator.keltner_middle(sample_klines)['value']
        lower = calculator.keltner_lower(sample_klines)['value']

        # Upper > Middle > Lower
        assert upper > middle
        assert middle > lower

    def test_keltner_channels_consistency(self, calculator, sample_klines):
        """Test that all three channels return consistent values."""
        upper_result = calculator.keltner_upper(sample_klines)
        middle_result = calculator.keltner_middle(sample_klines)
        lower_result = calculator.keltner_lower(sample_klines)

        # Check metadata consistency
        assert abs(upper_result['metadata']['middle'] - middle_result['value']) < 0.0001
        assert abs(lower_result['metadata']['middle'] - middle_result['value']) < 0.0001

    def test_keltner_insufficient_data(self, calculator):
        """Test Keltner channels with insufficient data."""
        short_klines = [
            {'high': 101.0, 'low': 99.0, 'close': 100.0}
            for _ in range(15)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.keltner_upper(short_klines)

    # =========================================================================
    # Volatility Tests
    # =========================================================================

    def test_volatility_20_basic(self, calculator, sample_klines):
        """Test 20-day volatility calculation."""
        result = calculator.volatility_20(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['value'] > 0
        assert result['method'] == 'volatility_20'
        assert result['parameters']['period'] == 20
        assert result['parameters']['annualized'] is True

    def test_volatility_positive(self, calculator, sample_klines):
        """Test that volatility is always positive."""
        result = calculator.volatility_20(sample_klines)
        assert result['value'] > 0

    def test_volatility_metadata(self, calculator, sample_klines):
        """Test volatility metadata."""
        result = calculator.volatility_20(sample_klines)

        assert 'daily_volatility' in result['metadata']
        assert 'latest_close' in result['metadata']
        assert result['metadata']['daily_volatility'] > 0

    def test_volatility_insufficient_data(self, calculator):
        """Test volatility with insufficient data."""
        short_klines = [{'close': 100.0 + i} for i in range(15)]

        with pytest.raises(InsufficientDataError):
            calculator.volatility_20(short_klines)

    def test_volatility_calculation_accuracy(self, calculator):
        """Test volatility with constant prices (should be near zero)."""
        # Constant prices should have very low volatility
        klines = [{'close': 100.0} for _ in range(30)]

        result = calculator.volatility_20(klines)
        # With constant prices, volatility should be 0
        assert result['value'] < 0.01

    # =========================================================================
    # Comparison Tests
    # =========================================================================

    def test_bollinger_vs_keltner_width(self, calculator, sample_klines):
        """Test that Bollinger and Keltner have different widths."""
        boll_upper = calculator.bollinger_upper(sample_klines)['value']
        boll_lower = calculator.bollinger_lower(sample_klines)['value']
        boll_width = boll_upper - boll_lower

        kelt_upper = calculator.keltner_upper(sample_klines)['value']
        kelt_lower = calculator.keltner_lower(sample_klines)['value']
        kelt_width = kelt_upper - kelt_lower

        # Widths should be different (Bollinger uses std, Keltner uses ATR)
        assert abs(boll_width - kelt_width) > 0.01

    def test_atr14_vs_atr20(self, calculator, sample_klines):
        """Test that ATR14 and ATR20 produce different values."""
        atr14 = calculator.atr14(sample_klines)['value']
        atr20 = calculator.atr20(sample_klines)['value']

        # Different periods should produce different values
        # (unless data is perfectly uniform, which is unlikely)
        assert atr14 != atr20

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_empty_klines(self, calculator):
        """Test with empty K-line data."""
        with pytest.raises((DataValidationError, InsufficientDataError)):
            calculator.bollinger_upper([])

    def test_all_methods_supported(self, calculator):
        """Test that all methods are listed in supported methods."""
        supported = calculator.get_supported_methods()

        expected_methods = [
            'bollinger_upper', 'bollinger_middle', 'bollinger_lower',
            'atr14', 'atr20',
            'keltner_upper', 'keltner_middle', 'keltner_lower',
            'volatility_20'
        ]

        for method in expected_methods:
            assert method in supported

    def test_timing_metadata(self, calculator, sample_klines):
        """Test that timing metadata is included."""
        result = calculator.atr14(sample_klines)

        assert 'metadata' in result
        assert 'execution_time_ms' in result['metadata']
        assert result['metadata']['execution_time_ms'] >= 0

    def test_bollinger_bandwidth(self, calculator, sample_klines):
        """Test Bollinger bandwidth calculation."""
        result = calculator.bollinger_upper(sample_klines)

        assert 'bandwidth' in result['metadata']
        assert result['metadata']['bandwidth'] > 0

    def test_keltner_width(self, calculator, sample_klines):
        """Test Keltner channel width calculation."""
        result = calculator.keltner_upper(sample_klines)

        assert 'width' in result['metadata']
        assert result['metadata']['width'] > 0
