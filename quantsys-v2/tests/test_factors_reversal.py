"""
Test cases for Reversal Factor Calculators
==========================================

Tests for reversal_1d, reversal_5d, and overnight_return factors.
"""

import pytest
from domain.quantlib.factors.reversal import ReversalFactors


class TestReversalFactors:
    """Test suite for ReversalFactors calculator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calc = ReversalFactors()

    # =========================================================================
    # Test reversal_1d
    # =========================================================================

    def test_reversal_1d_basic(self):
        """Test 1-day reversal with basic data."""
        klines = [
            {'close': 100.0, 'high': 101.0, 'low': 99.0, 'open': 100.0, 'volume': 1000},
            {'close': 102.0, 'high': 103.0, 'low': 101.0, 'open': 101.0, 'volume': 1100},
        ]
        result = self.calc.reversal_1d(klines)

        # Yesterday rose 2%, reversal = -2%
        assert result['value'] == pytest.approx(-0.02, abs=0.001)
        assert result['method'] == 'reversal_1d'
        assert result['parameters']['lookback'] == 1
        assert result['metadata']['yesterday_return'] == pytest.approx(0.02, abs=0.001)
        assert result['metadata']['signal'] == 'neutral'  # 2% is at threshold, signal is neutral

    def test_reversal_1d_positive_signal(self):
        """Test 1-day reversal with buy signal (yesterday fell)."""
        klines = [
            {'close': 100.0, 'high': 101.0, 'low': 99.0, 'open': 100.0, 'volume': 1000},
            {'close': 97.0, 'high': 100.0, 'low': 97.0, 'open': 99.0, 'volume': 1200},
        ]
        result = self.calc.reversal_1d(klines)

        # Yesterday fell 3%, reversal = +3%
        assert result['value'] == pytest.approx(0.03, abs=0.001)
        assert result['metadata']['signal'] == 'buy'
        assert result['metadata']['yesterday_return'] == pytest.approx(-0.03, abs=0.001)

    def test_reversal_1d_insufficient_data(self):
        """Test 1-day reversal with insufficient data."""
        klines = [
            {'close': 100.0, 'high': 101.0, 'low': 99.0, 'open': 100.0, 'volume': 1000},
        ]
        result = self.calc.reversal_1d(klines)

        assert result['value'] is None
        assert 'error' in result['metadata']

    # =========================================================================
    # Test reversal_5d
    # =========================================================================

    def test_reversal_5d_basic(self):
        """Test 5-day reversal with basic data."""
        klines = [
            {'close': 100.0 + i, 'high': 101.0 + i, 'low': 99.0 + i, 'open': 100.0 + i, 'volume': 1000}
            for i in range(7)
        ]
        result = self.calc.reversal_5d(klines)

        # Price: [100, 101, 102, 103, 104, 105, 106]
        # closes[-1] = 106, closes[-6] = 101
        # 5d_return = (106 - 101) / 101 = 0.0495
        # reversal_5d = -0.0495
        assert result['value'] == pytest.approx(-0.0495, abs=0.001)
        assert result['method'] == 'reversal_5d'
        assert result['parameters']['lookback'] == 5
        assert result['metadata']['5d_return'] == pytest.approx(0.0495, abs=0.001)

    def test_reversal_5d_negative_return(self):
        """Test 5-day reversal when price fell."""
        klines = []
        for i in range(7):
            # Price falling from 100 to 94
            price = 100.0 - i
            klines.append({
                'close': price,
                'high': price + 1.0,
                'low': price - 1.0,
                'open': price,
                'volume': 1000
            })

        result = self.calc.reversal_5d(klines)

        # Price: [100, 99, 98, 97, 96, 95, 94]
        # closes[-1] = 94, closes[-6] = 99
        # 5d_return = (94 - 99) / 99 = -0.0505
        # reversal_5d = -(-0.0505) = +0.0505
        assert result['value'] == pytest.approx(0.0505, abs=0.001)

    def test_reversal_5d_insufficient_data(self):
        """Test 5-day reversal with insufficient data."""
        klines = [
            {'close': 100.0 + i, 'high': 101.0 + i, 'low': 99.0 + i, 'open': 100.0 + i, 'volume': 1000}
            for i in range(5)
        ]
        result = self.calc.reversal_5d(klines)

        assert result['value'] is None
        assert 'error' in result['metadata']

    # =========================================================================
    # Test overnight_return
    # =========================================================================

    def test_overnight_return_gap_up(self):
        """Test overnight return with gap up."""
        klines = [
            {'close': 100.0, 'high': 101.0, 'low': 99.0, 'open': 99.5, 'volume': 1000},
            {'close': 102.0, 'high': 103.0, 'low': 101.0, 'open': 101.0, 'volume': 1100},
        ]
        result = self.calc.overnight_return(klines)

        # Overnight: (101 - 100) / 100 = 1%
        assert result['value'] == pytest.approx(0.01, abs=0.001)
        assert result['metadata']['today_open'] == 101.0
        assert result['metadata']['yesterday_close'] == 100.0
        assert result['metadata']['gap_pct'] == pytest.approx(1.0, abs=0.01)

    def test_overnight_return_gap_down(self):
        """Test overnight return with gap down."""
        klines = [
            {'close': 100.0, 'high': 101.0, 'low': 99.0, 'open': 99.5, 'volume': 1000},
            {'close': 97.0, 'high': 98.0, 'low': 96.0, 'open': 98.0, 'volume': 1200},
        ]
        result = self.calc.overnight_return(klines)

        # Overnight: (98 - 100) / 100 = -2%
        assert result['value'] == pytest.approx(-0.02, abs=0.001)
        assert result['metadata']['gap_pct'] == pytest.approx(-2.0, abs=0.01)

    def test_overnight_return_no_gap(self):
        """Test overnight return with no gap."""
        klines = [
            {'close': 100.0, 'high': 101.0, 'low': 99.0, 'open': 99.5, 'volume': 1000},
            {'close': 101.0, 'high': 102.0, 'low': 100.0, 'open': 100.0, 'volume': 1100},
        ]
        result = self.calc.overnight_return(klines)

        # Overnight: (100 - 100) / 100 = 0%
        assert result['value'] == pytest.approx(0.0, abs=0.001)

    def test_overnight_return_insufficient_data(self):
        """Test overnight return with insufficient data."""
        klines = [
            {'close': 100.0, 'high': 101.0, 'low': 99.0, 'open': 99.5, 'volume': 1000},
        ]
        result = self.calc.overnight_return(klines)

        assert result['value'] is None
        assert 'error' in result['metadata']

    def test_overnight_return_zero_close(self):
        """Test overnight return with zero yesterday close (edge case)."""
        klines = [
            {'close': 0.0, 'high': 1.0, 'low': 0.0, 'open': 0.5, 'volume': 1000},
            {'close': 100.0, 'high': 101.0, 'low': 99.0, 'open': 100.0, 'volume': 1100},
        ]
        result = self.calc.overnight_return(klines)

        assert result['value'] is None
        assert 'error' in result['metadata']

    # =========================================================================
    # Test get_supported_methods
    # =========================================================================

    def test_get_supported_methods(self):
        """Test that all expected methods are registered."""
        methods = self.calc.get_supported_methods()

        assert 'reversal_1d' in methods
        assert 'reversal_5d' in methods
        assert 'overnight_return' in methods
        assert len(methods) == 3
