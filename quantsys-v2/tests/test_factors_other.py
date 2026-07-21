"""
Tests for Other Technical Indicators
=====================================

Test suite for WR, BIAS, PSY, AR, BR, DMA, TRIX, VR, EMV, WVAD, AD Line, and CCI20.
"""

import pytest
import numpy as np

from domain.quantlib.factors.other import OtherFactors
from domain.quantlib.core.exceptions import InsufficientDataError, DataValidationError


class TestOtherFactors:
    """Test other technical indicator calculations."""

    @pytest.fixture
    def calculator(self):
        """Create calculator instance."""
        return OtherFactors()

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
    # Williams %R Tests
    # =========================================================================

    def test_wr_basic(self, calculator, sample_klines):
        """Test Williams %R calculation."""
        result = calculator.wr(sample_klines, period=14)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert -100 <= result['value'] <= 0
        assert result['method'] == 'wr'
        assert result['parameters']['period'] == 14

    def test_wr_range(self, calculator, sample_klines):
        """Test that WR is always in valid range."""
        result = calculator.wr(sample_klines, period=14)
        assert -100 <= result['value'] <= 0

    def test_wr_oversold_overbought(self, calculator):
        """Test WR oversold/overbought detection."""
        # Create data with price at low (oversold)
        klines = []
        for i in range(20):
            klines.append({
                'high': 105.0,
                'low': 95.0,
                'close': 96.0  # Near low
            })

        result = calculator.wr(klines, period=14)
        assert result['value'] < -80
        assert result['metadata']['oversold'] == True

    def test_wr10(self, calculator, sample_klines):
        """Test 10-day WR."""
        result = calculator.wr10(sample_klines)
        assert result['parameters']['period'] == 10

    def test_wr6(self, calculator, sample_klines):
        """Test 6-day WR."""
        result = calculator.wr6(sample_klines)
        assert result['parameters']['period'] == 6

    def test_wr_insufficient_data(self, calculator):
        """Test WR with insufficient data."""
        short_klines = [
            {'high': 101.0, 'low': 99.0, 'close': 100.0}
            for _ in range(10)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.wr(short_klines, period=14)

    # =========================================================================
    # BIAS Tests
    # =========================================================================

    def test_bias_basic(self, calculator, sample_klines):
        """Test BIAS calculation."""
        result = calculator.bias(sample_klines, period=6)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'bias'
        assert result['parameters']['period'] == 6

    def test_bias_positive(self, calculator):
        """Test BIAS with uptrend (positive bias)."""
        klines = []
        for i in range(20):
            klines.append({
                'close': 100.0 + i * 2  # Uptrend
            })

        result = calculator.bias(klines, period=6)
        assert result['value'] > 0
        assert result['metadata']['positive_bias'] == True

    def test_bias_negative(self, calculator):
        """Test BIAS with downtrend (negative bias)."""
        klines = []
        for i in range(20):
            klines.append({
                'close': 120.0 - i * 2  # Downtrend
            })

        result = calculator.bias(klines, period=6)
        assert result['value'] < 0
        assert result['metadata']['positive_bias'] == False

    def test_bias6(self, calculator, sample_klines):
        """Test 6-day BIAS."""
        result = calculator.bias6(sample_klines)
        assert result['parameters']['period'] == 6

    def test_bias12(self, calculator, sample_klines):
        """Test 12-day BIAS."""
        result = calculator.bias12(sample_klines)
        assert result['parameters']['period'] == 12

    def test_bias24(self, calculator, sample_klines):
        """Test 24-day BIAS."""
        result = calculator.bias24(sample_klines)
        assert result['parameters']['period'] == 24

    def test_bias_insufficient_data(self, calculator):
        """Test BIAS with insufficient data."""
        short_klines = [{'close': 100.0} for _ in range(3)]

        with pytest.raises(InsufficientDataError):
            calculator.bias(short_klines, period=6)

    # =========================================================================
    # PSY Tests
    # =========================================================================

    def test_psy_basic(self, calculator, sample_klines):
        """Test PSY calculation."""
        result = calculator.psy(sample_klines, period=12)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert 0 <= result['value'] <= 100
        assert result['method'] == 'psy'
        assert result['parameters']['period'] == 12

    def test_psy_all_up(self, calculator):
        """Test PSY with all up days."""
        klines = []
        for i in range(20):
            klines.append({
                'close': 100.0 + i
            })

        result = calculator.psy(klines, period=12)
        assert result['value'] == 100.0
        assert result['metadata']['up_days'] == 12

    def test_psy_all_down(self, calculator):
        """Test PSY with all down days."""
        klines = []
        for i in range(20):
            klines.append({
                'close': 120.0 - i
            })

        result = calculator.psy(klines, period=12)
        assert result['value'] == 0.0
        assert result['metadata']['down_days'] == 12

    def test_psy12(self, calculator, sample_klines):
        """Test 12-day PSY."""
        result = calculator.psy12(sample_klines)
        assert result['parameters']['period'] == 12

    def test_psy_insufficient_data(self, calculator):
        """Test PSY with insufficient data."""
        short_klines = [{'close': 100.0 + i} for i in range(10)]

        with pytest.raises(InsufficientDataError):
            calculator.psy(short_klines, period=12)

    # =========================================================================
    # AR Tests
    # =========================================================================

    def test_ar_basic(self, calculator, sample_klines):
        """Test AR calculation."""
        result = calculator.ar(sample_klines, period=26)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['value'] > 0
        assert result['method'] == 'ar'
        assert result['parameters']['period'] == 26

    def test_ar_calculation(self, calculator):
        """Test AR calculation with known values."""
        klines = []
        for i in range(30):
            klines.append({
                'open': 100.0,
                'high': 105.0,
                'low': 95.0
            })

        result = calculator.ar(klines, period=26)
        # AR = sum(105-100) / sum(100-95) = (5*26) / (5*26) = 100
        assert abs(result['value'] - 100.0) < 0.01

    def test_ar_insufficient_data(self, calculator):
        """Test AR with insufficient data."""
        short_klines = [
            {'open': 100.0, 'high': 105.0, 'low': 95.0}
            for _ in range(20)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.ar(short_klines, period=26)

    # =========================================================================
    # BR Tests
    # =========================================================================

    def test_br_basic(self, calculator, sample_klines):
        """Test BR calculation."""
        result = calculator.br(sample_klines, period=26)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['value'] > 0
        assert result['method'] == 'br'
        assert result['parameters']['period'] == 26

    def test_br_calculation(self, calculator):
        """Test BR calculation with known values."""
        klines = []
        for i in range(30):
            klines.append({
                'high': 105.0,
                'low': 95.0,
                'close': 100.0
            })

        result = calculator.br(klines, period=26)
        # With constant prices, BR should be around 100
        assert result['value'] > 0

    def test_br_insufficient_data(self, calculator):
        """Test BR with insufficient data."""
        short_klines = [
            {'high': 105.0, 'low': 95.0, 'close': 100.0}
            for _ in range(20)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.br(short_klines, period=26)

    # =========================================================================
    # DMA Tests
    # =========================================================================

    def test_dma_basic(self, calculator, sample_klines):
        """Test DMA calculation."""
        result = calculator.dma(sample_klines, short_period=10, long_period=50)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'dma'
        assert result['parameters']['short_period'] == 10
        assert result['parameters']['long_period'] == 50

    def test_dma_bullish(self, calculator):
        """Test DMA with bullish signal."""
        klines = []
        for i in range(60):
            klines.append({
                'close': 100.0 + i * 0.5  # Uptrend
            })

        result = calculator.dma(klines, short_period=10, long_period=50)
        # Short MA should be above long MA in uptrend
        assert result['value'] > 0
        assert result['metadata']['bullish'] == True

    def test_dma_bearish(self, calculator):
        """Test DMA with bearish signal."""
        klines = []
        for i in range(60):
            klines.append({
                'close': 130.0 - i * 0.5  # Downtrend
            })

        result = calculator.dma(klines, short_period=10, long_period=50)
        # Short MA should be below long MA in downtrend
        assert result['value'] < 0
        assert result['metadata']['bearish'] == True

    def test_dma10_50(self, calculator, sample_klines):
        """Test DMA with 10/50 periods."""
        result = calculator.dma10_50(sample_klines)
        assert result['parameters']['short_period'] == 10
        assert result['parameters']['long_period'] == 50

    def test_dma_insufficient_data(self, calculator):
        """Test DMA with insufficient data."""
        short_klines = [{'close': 100.0} for _ in range(40)]

        with pytest.raises(InsufficientDataError):
            calculator.dma(short_klines, short_period=10, long_period=50)

    # =========================================================================
    # TRIX Tests
    # =========================================================================

    def test_trix_basic(self, calculator, sample_klines):
        """Test TRIX calculation."""
        result = calculator.trix(sample_klines, period=12)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'trix'
        assert result['parameters']['period'] == 12

    def test_trix12(self, calculator, sample_klines):
        """Test 12-day TRIX."""
        result = calculator.trix12(sample_klines)
        assert result['parameters']['period'] == 12

    def test_trix_insufficient_data(self, calculator):
        """Test TRIX with insufficient data."""
        short_klines = [{'close': 100.0 + i * 0.1} for i in range(30)]

        with pytest.raises(InsufficientDataError):
            calculator.trix(short_klines, period=12)

    # =========================================================================
    # VR Tests
    # =========================================================================

    def test_vr_basic(self, calculator, sample_klines):
        """Test VR calculation."""
        result = calculator.vr(sample_klines, period=26)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['value'] > 0
        assert result['method'] == 'vr'
        assert result['parameters']['period'] == 26

    def test_vr_calculation(self, calculator):
        """Test VR calculation with known values."""
        klines = []
        for i in range(30):
            # Alternating up and down days
            close = 100.0 + (1 if i % 2 == 0 else -1)
            prev_close = 100.0 + (1 if (i-1) % 2 == 0 else -1)
            klines.append({
                'close': close,
                'volume': 1000000.0
            })

        result = calculator.vr(klines, period=26)
        # With balanced up/down, VR should be around 100
        assert 50 < result['value'] < 150

    def test_vr26(self, calculator, sample_klines):
        """Test 26-day VR."""
        result = calculator.vr26(sample_klines)
        assert result['parameters']['period'] == 26

    def test_vr_insufficient_data(self, calculator):
        """Test VR with insufficient data."""
        short_klines = [
            {'close': 100.0 + i, 'volume': 1000000.0}
            for i in range(20)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.vr(short_klines, period=26)

    # =========================================================================
    # EMV Tests
    # =========================================================================

    def test_emv_basic(self, calculator, sample_klines):
        """Test EMV calculation."""
        result = calculator.emv(sample_klines, period=14)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'emv'
        assert result['parameters']['period'] == 14

    def test_emv14(self, calculator, sample_klines):
        """Test 14-day EMV."""
        result = calculator.emv14(sample_klines)
        assert result['parameters']['period'] == 14

    def test_emv_insufficient_data(self, calculator):
        """Test EMV with insufficient data."""
        short_klines = [
            {'high': 105.0, 'low': 95.0, 'volume': 1000000.0}
            for _ in range(10)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.emv(short_klines, period=14)

    # =========================================================================
    # WVAD Tests
    # =========================================================================

    def test_wvad_basic(self, calculator, sample_klines):
        """Test WVAD calculation."""
        result = calculator.wvad(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'wvad'

    def test_wvad_accumulation(self, calculator):
        """Test WVAD with accumulation (close > open)."""
        klines = []
        for i in range(20):
            klines.append({
                'open': 100.0,
                'high': 105.0,
                'low': 95.0,
                'close': 103.0,  # Close > Open
                'volume': 1000000.0
            })

        result = calculator.wvad(klines)
        assert result['value'] > 0
        assert result['metadata']['accumulation'] == True

    def test_wvad_distribution(self, calculator):
        """Test WVAD with distribution (close < open)."""
        klines = []
        for i in range(20):
            klines.append({
                'open': 100.0,
                'high': 105.0,
                'low': 95.0,
                'close': 97.0,  # Close < Open
                'volume': 1000000.0
            })

        result = calculator.wvad(klines)
        assert result['value'] < 0
        assert result['metadata']['distribution'] == True

    # =========================================================================
    # AD Line Tests
    # =========================================================================

    def test_ad_line_basic(self, calculator, sample_klines):
        """Test A/D Line calculation."""
        result = calculator.ad_line(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'ad_line'

    def test_ad_line_accumulation(self, calculator):
        """Test A/D Line with accumulation."""
        klines = []
        for i in range(20):
            klines.append({
                'high': 105.0,
                'low': 95.0,
                'close': 103.0,  # Close near high
                'volume': 1000000.0
            })

        result = calculator.ad_line(klines)
        assert result['value'] > 0
        assert result['metadata']['accumulation'] == True

    def test_ad_line_distribution(self, calculator):
        """Test A/D Line with distribution."""
        klines = []
        for i in range(20):
            klines.append({
                'high': 105.0,
                'low': 95.0,
                'close': 97.0,  # Close near low
                'volume': 1000000.0
            })

        result = calculator.ad_line(klines)
        assert result['value'] < 0
        assert result['metadata']['distribution'] == True

    # =========================================================================
    # CCI20 Tests
    # =========================================================================

    def test_cci20_basic(self, calculator, sample_klines):
        """Test CCI20 calculation."""
        result = calculator.cci20(sample_klines)

        assert result is not None
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['method'] == 'cci20'
        assert result['parameters']['period'] == 20

    def test_cci20_range(self, calculator, sample_klines):
        """Test CCI20 typical range."""
        result = calculator.cci20(sample_klines)
        # CCI typically ranges from -200 to +200
        assert -300 < result['value'] < 300

    def test_cci20_overbought(self, calculator):
        """Test CCI20 overbought detection."""
        klines = []
        for i in range(25):
            klines.append({
                'high': 100.0 + i * 2,
                'low': 98.0 + i * 2,
                'close': 99.5 + i * 2
            })

        result = calculator.cci20(klines)
        # Strong uptrend should produce high CCI
        assert result['value'] > 0

    def test_cci20_insufficient_data(self, calculator):
        """Test CCI20 with insufficient data."""
        short_klines = [
            {'high': 105.0, 'low': 95.0, 'close': 100.0}
            for _ in range(15)
        ]

        with pytest.raises(InsufficientDataError):
            calculator.cci20(short_klines)

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_empty_klines(self, calculator):
        """Test with empty K-line data."""
        with pytest.raises((DataValidationError, InsufficientDataError)):
            calculator.wr([])

    def test_all_methods_supported(self, calculator):
        """Test that all methods are listed in supported methods."""
        supported = calculator.get_supported_methods()

        expected_methods = [
            'wr', 'wr10', 'wr6',
            'bias', 'bias6', 'bias12', 'bias24',
            'psy', 'psy12',
            'ar', 'br',
            'dma', 'dma10_50',
            'trix', 'trix12',
            'vr', 'vr26',
            'emv', 'emv14',
            'wvad',
            'ad_line',
            'cci20'
        ]

        for method in expected_methods:
            assert method in supported

    def test_timing_metadata(self, calculator, sample_klines):
        """Test that timing metadata is included."""
        result = calculator.wr(sample_klines)

        assert 'metadata' in result
        assert 'execution_time_ms' in result['metadata']
        assert result['metadata']['execution_time_ms'] >= 0

    def test_zero_range_handling(self, calculator):
        """Test handling of zero price range."""
        klines = []
        for i in range(20):
            klines.append({
                'open': 100.0,
                'high': 100.0,
                'low': 100.0,
                'close': 100.0,
                'volume': 1000000.0
            })

        # WR should handle zero range gracefully
        result = calculator.wr(klines, period=14)
        assert result['value'] == -50.0  # Neutral value

    def test_result_dict_structure(self, calculator, sample_klines):
        """Test that result dictionary has correct structure."""
        result = calculator.bias(sample_klines)

        assert 'value' in result
        assert 'method' in result
        assert 'parameters' in result
        assert 'metadata' in result
        assert 'timestamp' in result
        assert 'calculator' in result

        assert isinstance(result['value'], float)
        assert isinstance(result['method'], str)
        assert isinstance(result['parameters'], dict)
        assert isinstance(result['metadata'], dict)
