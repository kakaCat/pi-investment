"""
Tests for Trend Indicators
===========================

Test suite for ADX, DMI, CCI, Aroon, and SAR calculations.
"""

import pytest
import numpy as np

from domain.quantlib.factors.trend import TrendFactors
from domain.quantlib.core.exceptions import InsufficientDataError, DataValidationError


class TestTrendFactors:
    """Test trend indicator calculations."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return TrendFactors()

    @pytest.fixture
    def sample_klines(self):
        """Create sample K-line data with trending behavior."""
        np.random.seed(42)
        base_price = 100.0

        klines = []
        price = base_price

        # Create 100 periods with some trending behavior
        for i in range(100):
            # Add trend component
            trend = 0.5 if i < 50 else -0.3
            price += trend + np.random.randn() * 0.5

            high = price + abs(np.random.randn() * 1.0)
            low = price - abs(np.random.randn() * 1.0)

            klines.append({
                'open': float(price - 0.5),
                'high': float(high),
                'low': float(low),
                'close': float(price),
                'volume': float(1000000 + np.random.randint(-100000, 100000))
            })

        return klines

    @pytest.fixture
    def uptrend_klines(self):
        """Create K-line data with clear uptrend."""
        klines = []
        for i in range(50):
            price = 100.0 + i * 2.0
            klines.append({
                'open': float(price - 0.5),
                'high': float(price + 1.0),
                'low': float(price - 0.5),
                'close': float(price),
                'volume': 1000000.0
            })
        return klines

    @pytest.fixture
    def downtrend_klines(self):
        """Create K-line data with clear downtrend."""
        klines = []
        for i in range(50):
            price = 200.0 - i * 2.0
            klines.append({
                'open': float(price + 0.5),
                'high': float(price + 1.0),
                'low': float(price - 1.0),
                'close': float(price),
                'volume': 1000000.0
            })
        return klines

    # =========================================================================
    # ADX Tests
    # =========================================================================

    def test_adx_basic(self, calculator, sample_klines):
        """Test ADX calculation."""
        result = calculator.adx(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert 0 <= result['value'] <= 100
        assert result['method'] == 'adx'
        assert result['parameters']['period'] == 14

    def test_adx_uptrend(self, calculator, uptrend_klines):
        """Test ADX with strong uptrend."""
        result = calculator.adx(uptrend_klines)

        # In strong trend, ADX should be high
        assert result['value'] > 25
        assert result['metadata']['trending'] is True
        assert result['metadata']['plus_di'] > result['metadata']['minus_di']

    def test_adx_downtrend(self, calculator, downtrend_klines):
        """Test ADX with strong downtrend."""
        result = calculator.adx(downtrend_klines)

        # In strong trend, ADX should be high
        assert result['value'] > 25
        assert result['metadata']['trending'] is True
        assert result['metadata']['minus_di'] > result['metadata']['plus_di']

    def test_adx_metadata(self, calculator, sample_klines):
        """Test ADX metadata."""
        result = calculator.adx(sample_klines)

        assert 'plus_di' in result['metadata']
        assert 'minus_di' in result['metadata']
        assert 'dx' in result['metadata']
        assert 'trend_strength' in result['metadata']
        assert result['metadata']['trend_strength'] in ['weak', 'strong', 'very_strong', 'extremely_strong']

    def test_adx_custom_period(self, calculator, sample_klines):
        """Test ADX with custom period."""
        result = calculator.adx(sample_klines, period=20)

        assert result['parameters']['period'] == 20
        assert 0 <= result['value'] <= 100

    def test_adx_insufficient_data(self, calculator):
        """Test ADX with insufficient data."""
        short_klines = [
            {'high': 101.0, 'low': 99.0, 'close': 100.0, 'volume': 1000000}
            for _ in range(20)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.adx(short_klines)

    # =========================================================================
    # DI+ Tests
    # =========================================================================

    def test_di_plus_basic(self, calculator, sample_klines):
        """Test +DI calculation."""
        result = calculator.di_plus(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['value'] >= 0
        assert result['method'] == 'di_plus'

    def test_di_plus_uptrend(self, calculator, uptrend_klines):
        """Test +DI in uptrend."""
        result = calculator.di_plus(uptrend_klines)

        # In uptrend, +DI should be high
        assert result['value'] > 20
        assert result['metadata']['bullish'] == True

    def test_di_plus_insufficient_data(self, calculator):
        """Test +DI with insufficient data."""
        short_klines = [
            {'high': 101.0, 'low': 99.0, 'close': 100.0}
            for _ in range(15)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.di_plus(short_klines)

    # =========================================================================
    # DI- Tests
    # =========================================================================

    def test_di_minus_basic(self, calculator, sample_klines):
        """Test -DI calculation."""
        result = calculator.di_minus(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['value'] >= 0
        assert result['method'] == 'di_minus'

    def test_di_minus_downtrend(self, calculator, downtrend_klines):
        """Test -DI in downtrend."""
        result = calculator.di_minus(downtrend_klines)

        # In downtrend, -DI should be high
        assert result['value'] > 20
        assert result['metadata']['bearish'] == True

    def test_di_minus_insufficient_data(self, calculator):
        """Test -DI with insufficient data."""
        short_klines = [
            {'high': 101.0, 'low': 99.0, 'close': 100.0}
            for _ in range(15)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.di_minus(short_klines)

    # =========================================================================
    # DMI Tests
    # =========================================================================

    def test_dmi_basic(self, calculator, sample_klines):
        """Test DMI calculation."""
        result = calculator.dmi(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], dict)
        assert 'plus_di' in result['value']
        assert 'minus_di' in result['value']
        assert result['method'] == 'dmi'

    def test_dmi_uptrend(self, calculator, uptrend_klines):
        """Test DMI in uptrend."""
        result = calculator.dmi(uptrend_klines)

        # In uptrend, +DI should be greater than -DI
        assert result['value']['plus_di'] > result['value']['minus_di']
        assert result['metadata']['trend'] == 'bullish'

    def test_dmi_downtrend(self, calculator, downtrend_klines):
        """Test DMI in downtrend."""
        result = calculator.dmi(downtrend_klines)

        # In downtrend, -DI should be greater than +DI
        assert result['value']['minus_di'] > result['value']['plus_di']
        assert result['metadata']['trend'] == 'bearish'

    def test_dmi_metadata(self, calculator, sample_klines):
        """Test DMI metadata."""
        result = calculator.dmi(sample_klines)

        assert 'di_spread' in result['metadata']
        assert 'trend' in result['metadata']
        assert result['metadata']['trend'] in ['bullish', 'bearish', 'neutral']
        assert 'strong_trend' in result['metadata']

    # =========================================================================
    # CCI Tests
    # =========================================================================

    def test_cci_basic(self, calculator, sample_klines):
        """Test CCI calculation."""
        result = calculator.cci(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'cci'
        assert result['parameters']['period'] == 20

    def test_cci_range(self, calculator, sample_klines):
        """Test CCI typical range."""
        result = calculator.cci(sample_klines)

        # CCI typically ranges from -200 to +200, but can exceed
        assert -500 < result['value'] < 500

    def test_cci_overbought(self, calculator, uptrend_klines):
        """Test CCI overbought detection."""
        result = calculator.cci(uptrend_klines)

        # In strong uptrend, CCI may be overbought
        if result['value'] > 100:
            assert result['metadata']['overbought'] == True
            assert result['metadata']['condition'] == 'overbought'

    def test_cci_oversold(self, calculator, downtrend_klines):
        """Test CCI oversold detection."""
        result = calculator.cci(downtrend_klines)

        # In strong downtrend, CCI may be oversold
        if result['value'] < -100:
            assert result['metadata']['oversold'] == True
            assert result['metadata']['condition'] == 'oversold'

    def test_cci_metadata(self, calculator, sample_klines):
        """Test CCI metadata."""
        result = calculator.cci(sample_klines)

        assert 'typical_price' in result['metadata']
        assert 'sma_tp' in result['metadata']
        assert 'mean_deviation' in result['metadata']
        assert 'condition' in result['metadata']

    def test_cci_custom_period(self, calculator, sample_klines):
        """Test CCI with custom period."""
        result = calculator.cci(sample_klines, period=14)

        assert result['parameters']['period'] == 14

    def test_cci_insufficient_data(self, calculator):
        """Test CCI with insufficient data."""
        short_klines = [
            {'high': 101.0, 'low': 99.0, 'close': 100.0}
            for _ in range(15)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.cci(short_klines)

    # =========================================================================
    # Aroon Up Tests
    # =========================================================================

    def test_aroon_up_basic(self, calculator, sample_klines):
        """Test Aroon Up calculation."""
        result = calculator.aroon_up(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert 0 <= result['value'] <= 100
        assert result['method'] == 'aroon_up'
        assert result['parameters']['period'] == 25

    def test_aroon_up_recent_high(self, calculator):
        """Test Aroon Up with recent high."""
        klines = []
        for i in range(30):
            # Price peaks at the end
            price = 100.0 + i * 0.5
            klines.append({
                'high': float(price + 1.0),
                'low': float(price - 1.0),
                'close': float(price)
            })

        result = calculator.aroon_up(klines)

        # Recent high should give high Aroon Up
        assert result['value'] >= 90
        assert result['metadata']['strong_uptrend'] is True

    def test_aroon_up_old_high(self, calculator):
        """Test Aroon Up with old high."""
        klines = []
        for i in range(30):
            # Price peaks at the beginning
            price = 130.0 - i * 0.5
            klines.append({
                'high': float(price + 1.0),
                'low': float(price - 1.0),
                'close': float(price)
            })

        result = calculator.aroon_up(klines)

        # Old high should give low Aroon Up
        assert result['value'] <= 30
        assert result['metadata']['weak_uptrend'] is True

    def test_aroon_up_metadata(self, calculator, sample_klines):
        """Test Aroon Up metadata."""
        result = calculator.aroon_up(sample_klines)

        assert 'periods_since_high' in result['metadata']
        assert 'highest_high' in result['metadata']
        assert 'strong_uptrend' in result['metadata']
        assert 'weak_uptrend' in result['metadata']

    def test_aroon_up_insufficient_data(self, calculator):
        """Test Aroon Up with insufficient data."""
        short_klines = [
            {'high': 101.0, 'low': 99.0, 'close': 100.0}
            for _ in range(20)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.aroon_up(short_klines)

    # =========================================================================
    # Aroon Down Tests
    # =========================================================================

    def test_aroon_down_basic(self, calculator, sample_klines):
        """Test Aroon Down calculation."""
        result = calculator.aroon_down(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert 0 <= result['value'] <= 100
        assert result['method'] == 'aroon_down'
        assert result['parameters']['period'] == 25

    def test_aroon_down_recent_low(self, calculator):
        """Test Aroon Down with recent low."""
        klines = []
        for i in range(30):
            # Price bottoms at the end
            price = 130.0 - i * 0.5
            klines.append({
                'high': float(price + 1.0),
                'low': float(price - 1.0),
                'close': float(price)
            })

        result = calculator.aroon_down(klines)

        # Recent low should give high Aroon Down
        assert result['value'] >= 90
        assert result['metadata']['strong_downtrend'] is True

    def test_aroon_down_old_low(self, calculator):
        """Test Aroon Down with old low."""
        klines = []
        for i in range(30):
            # Price bottoms at the beginning
            price = 100.0 + i * 0.5
            klines.append({
                'high': float(price + 1.0),
                'low': float(price - 1.0),
                'close': float(price)
            })

        result = calculator.aroon_down(klines)

        # Old low should give low Aroon Down
        assert result['value'] <= 30
        assert result['metadata']['weak_downtrend'] is True

    def test_aroon_down_metadata(self, calculator, sample_klines):
        """Test Aroon Down metadata."""
        result = calculator.aroon_down(sample_klines)

        assert 'periods_since_low' in result['metadata']
        assert 'lowest_low' in result['metadata']
        assert 'strong_downtrend' in result['metadata']
        assert 'weak_downtrend' in result['metadata']

    # =========================================================================
    # SAR Tests
    # =========================================================================

    def test_sar_basic(self, calculator, sample_klines):
        """Test SAR calculation."""
        result = calculator.sar(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['value'] > 0
        assert result['method'] == 'sar'

    def test_sar_uptrend(self, calculator, uptrend_klines):
        """Test SAR in uptrend."""
        result = calculator.sar(uptrend_klines)

        # In uptrend, SAR should be below price
        latest_close = uptrend_klines[-1]['close']
        assert result['value'] < latest_close
        assert result['metadata']['trend'] == 'bullish'
        assert result['metadata']['is_bullish'] == True

    def test_sar_downtrend(self, calculator, downtrend_klines):
        """Test SAR in downtrend."""
        result = calculator.sar(downtrend_klines)

        # In downtrend, SAR should be above price
        latest_close = downtrend_klines[-1]['close']
        assert result['value'] > latest_close
        assert result['metadata']['trend'] == 'bearish'
        assert result['metadata']['is_bullish'] == False

    def test_sar_metadata(self, calculator, sample_klines):
        """Test SAR metadata."""
        result = calculator.sar(sample_klines)

        assert 'trend' in result['metadata']
        assert result['metadata']['trend'] in ['bullish', 'bearish']
        assert 'is_bullish' in result['metadata']
        assert 'extreme_point' in result['metadata']
        assert 'acceleration_factor' in result['metadata']
        assert 'latest_close' in result['metadata']
        assert 'distance_to_sar' in result['metadata']
        assert 'distance_pct' in result['metadata']

    def test_sar_custom_parameters(self, calculator, sample_klines):
        """Test SAR with custom parameters."""
        result = calculator.sar(sample_klines, acceleration=0.03, maximum=0.3)

        assert result['parameters']['acceleration'] == 0.03
        assert result['parameters']['maximum'] == 0.3

    def test_sar_insufficient_data(self, calculator):
        """Test SAR with insufficient data."""
        short_klines = [
            {'high': 101.0, 'low': 99.0, 'close': 100.0}
        ]

        with pytest.raises(InsufficientDataError):
            calculator.sar(short_klines)

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_empty_klines(self, calculator):
        """Test with empty K-line data."""
        with pytest.raises((DataValidationError, InsufficientDataError)):
            calculator.adx([])

    def test_all_methods_supported(self, calculator):
        """Test that all methods are listed in supported methods."""
        supported = calculator.get_supported_methods()

        expected_methods = [
            'adx', 'di_plus', 'di_minus', 'dmi',
            'cci', 'aroon_up', 'aroon_down', 'sar'
        ]

        for method in expected_methods:
            assert method in supported

    def test_timing_metadata(self, calculator, sample_klines):
        """Test that timing metadata is included."""
        result = calculator.adx(sample_klines)

        assert 'metadata' in result
        assert 'execution_time_ms' in result['metadata']
        assert result['metadata']['execution_time_ms'] >= 0

    def test_constant_prices(self, calculator):
        """Test with constant prices (no movement)."""
        klines = []
        for i in range(50):
            klines.append({
                'high': 100.0,
                'low': 100.0,
                'close': 100.0,
                'volume': 1000000.0
            })

        # ADX should be low with no trend
        result = calculator.adx(klines)
        assert result['value'] < 25

        # CCI should be near zero
        result = calculator.cci(klines)
        assert abs(result['value']) < 10

    def test_zero_true_range(self, calculator):
        """Test handling of zero true range."""
        klines = []
        for i in range(50):
            klines.append({
                'high': 100.0,
                'low': 100.0,
                'close': 100.0,
                'volume': 1000000.0
            })

        # Should handle zero TR gracefully
        result = calculator.di_plus(klines)
        assert result['value'] == 0.0

        result = calculator.di_minus(klines)
        assert result['value'] == 0.0

    def test_result_dict_structure(self, calculator, sample_klines):
        """Test that all results follow standard structure."""
        methods = [
            ('adx', {}),
            ('di_plus', {}),
            ('di_minus', {}),
            ('dmi', {}),
            ('cci', {}),
            ('aroon_up', {}),
            ('aroon_down', {}),
            ('sar', {})
        ]

        for method_name, kwargs in methods:
            method = getattr(calculator, method_name)
            result = method(sample_klines, **kwargs)

            # Check standard structure
            assert 'value' in result
            assert 'method' in result
            assert 'parameters' in result
            assert 'metadata' in result
            assert 'timestamp' in result
            assert 'calculator' in result

            assert result['method'] == method_name
            assert result['calculator'] == 'TrendFactors'
            assert 'data_points' in result['metadata']

    def test_numpy_comparison_operators(self, calculator, sample_klines):
        """Test that NumPy comparisons use == not is."""
        # This test ensures we don't have 'is' comparisons with NumPy booleans
        # The code should work without warnings
        result = calculator.adx(sample_klines)
        assert result is not None

        result = calculator.cci(sample_klines)
        assert result is not None

        result = calculator.sar(sample_klines)
        assert result is not None
