"""
Tests for fundamental factor calculators: FSCORE and Earnings Quality.
"""
import pytest
from domain.quantlib.factors.fundamental import (
    FScoreCalculator,
    EarningsQualityCalculator,
    compute_fundamental_factors,
)


# ── FSCORE Tests ──

class TestFScoreCalculator:
    """Test Piotroski FSCORE (0-9) calculator."""

    def setup_method(self):
        self.calc = FScoreCalculator()

    def test_perfect_score_all_9(self):
        """All 9 criteria pass → FSCORE = 9."""
        current = {
            'roa': 0.15, 'operating_cf': 1_000_000, 'net_income': 500_000,
            'long_term_debt': 100_000, 'total_assets': 1_000_000,
            'current_ratio': 2.5, 'total_shares': 10_000,
            'gross_margin': 0.45, 'revenue': 2_000_000,
        }
        previous = {
            'roa': 0.10, 'long_term_debt': 200_000, 'total_assets': 800_000,
            'current_ratio': 2.0, 'total_shares': 12_000,
            'gross_margin': 0.40, 'revenue': 1_500_000,
        }
        result = self.calc.calculate({'current': current, 'previous': previous})
        assert result == 9, f"Expected 9, got {result}"

    def test_zero_score_all_fail(self):
        """All 9 criteria fail → FSCORE = 0."""
        current = {
            'roa': -0.05, 'operating_cf': -500_000, 'net_income': -200_000,
            'long_term_debt': 500_000, 'total_assets': 1_000_000,
            'current_ratio': 1.2, 'total_shares': 15_000,
            'gross_margin': 0.15, 'revenue': 600_000,  # turnover 0.6 < prev 0.8
        }
        previous = {
            'roa': 0.10, 'long_term_debt': 200_000, 'total_assets': 1_000_000,
            'current_ratio': 2.0, 'total_shares': 10_000,
            'gross_margin': 0.40, 'revenue': 800_000,  # turnover 0.8
        }
        result = self.calc.calculate({'current': current, 'previous': previous})
        assert result == 0, f"Expected 0, got {result}"

    def test_missing_data_returns_none(self):
        """Missing critical data → returns None."""
        current = {'roa': None, 'operating_cf': 100_000}
        previous = {'roa': 0.10}
        result = self.calc.calculate({'current': current, 'previous': previous})
        assert result is None

    def test_direct_positional_call(self):
        """Direct call with positional args should work."""
        current = {'roa': 0.10, 'operating_cf': 100, 'net_income': 50,
                   'long_term_debt': 10, 'total_assets': 100,
                   'current_ratio': 1.5, 'total_shares': 100,
                   'gross_margin': 0.30, 'revenue': 200}
        previous = {'roa': 0.05, 'long_term_debt': 20, 'total_assets': 80,
                    'current_ratio': 1.2, 'total_shares': 150,
                    'gross_margin': 0.25, 'revenue': 150}
        result = self.calc.calculate(current, previous)
        assert result is not None
        assert 0 <= result <= 9

    def test_supported_methods(self):
        methods = self.calc.get_supported_methods()
        assert 'fscore' in methods


# ── Earnings Quality Tests ──

class TestEarningsQualityCalculator:
    """Test Earnings Quality 4-factor calculator."""

    def setup_method(self):
        self.calc = EarningsQualityCalculator()

    def test_normal_company(self):
        """Normal company with decent metrics."""
        data = {
            'net_income': 500_000, 'operating_cf': 600_000,
            'total_assets': 2_000_000, 'total_liabilities': 800_000,
            'roe': 0.25,
        }
        result = self.calc.calculate(data)
        assert result is not None
        assert 'total_score' in result
        assert 0 <= result['total_score'] <= 400

    def test_poor_quality(self):
        """Poor quality: negative CF, high leverage."""
        data = {
            'net_income': 500_000, 'operating_cf': -200_000,
            'total_assets': 2_000_000, 'total_liabilities': 1_800_000,
            'roe': 0.25,
        }
        result = self.calc.calculate(data)
        assert result is not None
        assert result['accrual_score'] < 50
        assert result['cf_score'] < 50

    def test_high_quality(self):
        """High quality: strong CF, low debt, high ROE."""
        data = {
            'net_income': 500_000, 'operating_cf': 520_000,
            'total_assets': 2_000_000, 'total_liabilities': 200_000,
            'roe': 0.35,
        }
        result = self.calc.calculate(data)
        assert result is not None
        assert result['total_score'] > 200
        assert result['da_score'] > 50

    def test_missing_data_returns_none(self):
        """Missing data → returns None."""
        data = {'net_income': None}
        result = self.calc.calculate(data)
        assert result is None

    def test_zero_assets_returns_none(self):
        """Zero total assets → returns None (division by zero)."""
        data = {
            'net_income': 100, 'operating_cf': 100,
            'total_assets': 0, 'total_liabilities': 50,
            'roe': 0.10,
        }
        result = self.calc.calculate(data)
        assert result is None

    def test_supported_methods(self):
        methods = self.calc.get_supported_methods()
        assert 'earnings_quality' in methods


# ── Convenience Wrapper Tests ──

class TestComputeFundamentalFactors:
    def test_with_both_current_and_previous(self):
        current = {
            'roa': 0.10, 'operating_cf': 100, 'net_income': 50,
            'long_term_debt': 10, 'total_assets': 100,
            'current_ratio': 1.5, 'total_shares': 100,
            'gross_margin': 0.30, 'revenue': 200,
            'total_liabilities': 50, 'roe': 0.50,  # needed for earnings quality
        }
        previous = {
            'roa': 0.05, 'long_term_debt': 20, 'total_assets': 80,
            'current_ratio': 1.2, 'total_shares': 150,
            'gross_margin': 0.25, 'revenue': 150,
        }
        result = compute_fundamental_factors(current, previous)
        assert 'fscore' in result
        assert 'earnings_quality' in result
        assert result['fscore'] is not None
        assert result['earnings_quality'] is not None

    def test_without_previous(self):
        current = {
            'net_income': 100, 'operating_cf': 120,
            'total_assets': 500, 'total_liabilities': 200,
            'roe': 0.20,
        }
        result = compute_fundamental_factors(current)
        assert result['fscore'] is None
        assert result['earnings_quality'] is not None
