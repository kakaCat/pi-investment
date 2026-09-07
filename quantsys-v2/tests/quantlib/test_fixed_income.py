"""
Fixed Income Module Tests
=========================

Comprehensive test suite for fixed income analysis module.

Tests cover:
- Bond pricing (zero, coupon, perpetual, callable)
- Duration and convexity calculations
- Yield curve construction and fitting
- Credit analysis
- Bond portfolio management

Author: QuantSys V2
Date: 2026-05-24
"""

import pytest
import numpy as np
from domain.quantlib.fixed_income import (
    BondPricingCalculator,
    DurationConvexityCalculator,
    YieldCurveCalculator,
    CreditAnalysisCalculator,
    BondPortfolioCalculator
)
from domain.quantlib.exceptions import DataValidationError, CalculationError


class TestBondPricing:
    """Test bond pricing calculations."""

    def test_zero_coupon_bond_pricing(self):
        """Test zero coupon bond pricing."""
        calc = BondPricingCalculator()
        result = calc.calculate_price(
            face_value=1000,
            coupon_rate=0,
            ytm=0.05,
            years_to_maturity=10,
            frequency=0,
            bond_type='zero'
        )

        assert result['value'] == pytest.approx(613.91, rel=0.01)
        assert result['metadata']['pv_coupons'] == 0
        assert result['metadata']['premium_discount'] == 'discount'

    def test_coupon_bond_pricing_at_par(self):
        """Test coupon bond pricing when YTM equals coupon rate."""
        calc = BondPricingCalculator()
        result = calc.calculate_price(
            face_value=1000,
            coupon_rate=0.05,
            ytm=0.05,
            years_to_maturity=10,
            frequency=2
        )

        # When YTM = coupon rate, price should equal face value
        assert result['value'] == pytest.approx(1000, rel=0.01)
        assert result['metadata']['premium_discount'] == 'par'

    def test_coupon_bond_pricing_premium(self):
        """Test coupon bond pricing at premium."""
        calc = BondPricingCalculator()
        result = calc.calculate_price(
            face_value=1000,
            coupon_rate=0.06,
            ytm=0.05,
            years_to_maturity=10,
            frequency=2
        )

        # When coupon > YTM, bond trades at premium
        assert result['value'] > 1000
        assert result['metadata']['premium_discount'] == 'premium'

    def test_coupon_bond_pricing_discount(self):
        """Test coupon bond pricing at discount."""
        calc = BondPricingCalculator()
        result = calc.calculate_price(
            face_value=1000,
            coupon_rate=0.04,
            ytm=0.05,
            years_to_maturity=10,
            frequency=2
        )

        # When coupon < YTM, bond trades at discount
        assert result['value'] < 1000
        assert result['metadata']['premium_discount'] == 'discount'

    def test_perpetual_bond_pricing(self):
        """Test perpetual bond pricing."""
        calc = BondPricingCalculator()
        result = calc.calculate_price(
            face_value=1000,
            coupon_rate=0.05,
            ytm=0.05,
            frequency=2,
            bond_type='perpetual'
        )

        # Perpetual bond: Price = Coupon / YTM
        expected_price = (1000 * 0.05 / 2) / (0.05 / 2)
        assert result['value'] == pytest.approx(expected_price, rel=0.01)

    def test_ytm_calculation(self):
        """Test YTM calculation."""
        calc = BondPricingCalculator()
        result = calc.calculate_ytm(
            price=950,
            face_value=1000,
            coupon_rate=0.05,
            years_to_maturity=10,
            frequency=2
        )

        # YTM should be higher than coupon rate for discount bond
        assert result['value'] > 0.05
        assert result['metadata']['is_discount'] is True

    def test_ytc_calculation(self):
        """Test yield to call calculation."""
        calc = BondPricingCalculator()
        result = calc.calculate_ytc(
            price=1050,
            face_value=1000,
            coupon_rate=0.06,
            years_to_call=5,
            call_price=1020,
            frequency=2
        )

        assert result['value'] > 0
        assert 'ytc_percent' in result['metadata']

    def test_accrued_interest(self):
        """Test accrued interest calculation."""
        calc = BondPricingCalculator()
        result = calc.calculate_accrued_interest(
            face_value=1000,
            coupon_rate=0.06,
            frequency=2,
            days_since_last_coupon=45,
            day_count_convention='30/360'
        )

        # 45 days out of 180 days (semi-annual)
        expected_accrued = (1000 * 0.06 / 2) * (45 / 180)
        assert result['value'] == pytest.approx(expected_accrued, rel=0.01)


class TestDurationConvexity:
    """Test duration and convexity calculations."""

    def test_macaulay_duration_zero_coupon(self):
        """Test Macaulay duration for zero coupon bond."""
        calc = DurationConvexityCalculator()
        result = calc.calculate_macaulay_duration(
            face_value=1000,
            coupon_rate=0,
            years_to_maturity=10,
            ytm=0.05,
            frequency=0
        )

        # Zero coupon bond duration equals maturity
        assert result['value'] == 10

    def test_macaulay_duration_coupon_bond(self):
        """Test Macaulay duration for coupon bond."""
        calc = DurationConvexityCalculator()
        result = calc.calculate_macaulay_duration(
            face_value=1000,
            coupon_rate=0.05,
            years_to_maturity=10,
            ytm=0.05,
            frequency=2
        )

        # Coupon bond duration < maturity
        assert result['value'] < 10
        assert result['value'] > 0

    def test_modified_duration(self):
        """Test modified duration calculation."""
        calc = DurationConvexityCalculator()
        result = calc.calculate_modified_duration(
            face_value=1000,
            coupon_rate=0.05,
            years_to_maturity=10,
            ytm=0.05,
            frequency=2
        )

        # Modified duration < Macaulay duration
        assert result['value'] < result['metadata']['macaulay_duration']
        assert 'dv01' in result['metadata']

    def test_effective_duration(self):
        """Test effective duration calculation."""
        calc = DurationConvexityCalculator()
        result = calc.calculate_effective_duration(
            price=1000,
            price_up=980,
            price_down=1020,
            delta_yield=0.01
        )

        # Effective duration = (1020 - 980) / (2 * 1000 * 0.01) = 2.0
        assert result['value'] == pytest.approx(2.0, rel=0.01)

    def test_convexity(self):
        """Test convexity calculation."""
        calc = DurationConvexityCalculator()
        result = calc.calculate_convexity(
            face_value=1000,
            coupon_rate=0.05,
            years_to_maturity=10,
            ytm=0.05,
            frequency=2
        )

        # Convexity should be positive
        assert result['value'] > 0
        assert 'dollar_convexity' in result['metadata']

    def test_effective_convexity(self):
        """Test effective convexity calculation."""
        calc = DurationConvexityCalculator()
        result = calc.calculate_effective_convexity(
            price=1000,
            price_up=980,
            price_down=1020,
            delta_yield=0.01
        )

        # Effective convexity should be positive for typical bonds
        assert result['value'] >= 0


class TestYieldCurve:
    """Test yield curve calculations."""

    def test_bootstrap_spot_curve(self):
        """Test spot curve bootstrapping."""
        calc = YieldCurveCalculator()

        bonds = [
            {'price': 980, 'coupon_rate': 0.04, 'maturity': 1, 'face_value': 1000},
            {'price': 970, 'coupon_rate': 0.045, 'maturity': 2, 'face_value': 1000},
            {'price': 960, 'coupon_rate': 0.05, 'maturity': 3, 'face_value': 1000},
        ]

        result = calc.bootstrap_spot_curve(bonds, frequency=1)

        assert len(result['metadata']['spot_curve']) == 3
        assert all(point['spot_rate'] > 0 for point in result['metadata']['spot_curve'])

    def test_forward_curve(self):
        """Test forward rate calculation."""
        calc = YieldCurveCalculator()

        spot_rates = [
            (1, 0.03),
            (2, 0.035),
            (3, 0.04),
            (5, 0.045),
        ]

        result = calc.calculate_forward_curve(spot_rates)

        assert len(result['metadata']['forward_curve']) > 0
        assert all(fr['forward_rate'] > 0 for fr in result['metadata']['forward_curve'])

    def test_nelson_siegel_fitting(self):
        """Test Nelson-Siegel model fitting."""
        calc = YieldCurveCalculator()

        maturities = [0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30]
        yields = [0.02, 0.025, 0.03, 0.035, 0.038, 0.04, 0.042, 0.043, 0.044, 0.045]

        result = calc.fit_nelson_siegel(maturities, yields)

        assert 'beta0' in result['value']
        assert 'beta1' in result['value']
        assert 'beta2' in result['value']
        assert 'tau' in result['value']
        assert result['metadata']['fit_statistics']['r_squared'] > 0.9

    def test_curve_interpolation(self):
        """Test yield curve interpolation."""
        calc = YieldCurveCalculator()

        maturities = [1, 2, 3, 5, 7, 10]
        yields = [0.03, 0.035, 0.038, 0.04, 0.042, 0.043]
        target_maturities = [1.5, 4, 6, 8]

        result = calc.interpolate_curve(maturities, yields, target_maturities, method='cubic')

        assert len(result['value']) == len(target_maturities)
        assert all(y > 0 for y in result['value'])


class TestCreditAnalysis:
    """Test credit analysis calculations."""

    def test_expected_loss(self):
        """Test expected loss calculation."""
        calc = CreditAnalysisCalculator()
        result = calc.calculate_expected_loss(
            probability_of_default=0.02,
            exposure=1000,
            recovery_rate=0.40
        )

        # EL = PD * LGD * EAD = 0.02 * 0.6 * 1000 = 12
        assert result['value'] == pytest.approx(12, rel=0.01)
        assert result['metadata']['lgd'] == 0.6

    def test_cumulative_pd(self):
        """Test cumulative default probability."""
        calc = CreditAnalysisCalculator()
        result = calc.calculate_cumulative_pd(
            annual_pd=0.02,
            years=5,
            method='hazard'
        )

        # Cumulative PD should increase with time
        cumulative_pds = [cpd['cumulative_pd'] for cpd in result['metadata']['cumulative_pds']]
        assert all(cumulative_pds[i] < cumulative_pds[i+1] for i in range(len(cumulative_pds)-1))

    def test_pd_from_credit_spread(self):
        """Test PD derivation from credit spread."""
        calc = CreditAnalysisCalculator()
        result = calc.pd_from_credit_spread(
            credit_spread=0.02,
            recovery_rate=0.40,
            risk_free_rate=0.03
        )

        # PD ≈ Spread / LGD = 0.02 / 0.6 ≈ 0.0333
        assert result['value'] == pytest.approx(0.0333, rel=0.01)

    def test_merton_model(self):
        """Test Merton structural model."""
        calc = CreditAnalysisCalculator()
        result = calc.pd_from_merton_model(
            asset_value=100,
            asset_volatility=0.25,
            debt_face_value=80,
            risk_free_rate=0.03,
            time_horizon=1.0
        )

        # PD should be between 0 and 1
        assert 0 <= result['value'] <= 1
        assert 'distance_to_default' in result['metadata']

    def test_credit_var(self):
        """Test Credit VaR calculation."""
        calc = CreditAnalysisCalculator()
        result = calc.calculate_credit_var(
            probability_of_default=0.02,
            exposure=1000,
            recovery_rate=0.40,
            confidence_level=0.99
        )

        assert result['value'] >= 0
        assert 'expected_loss' in result['metadata']

    def test_historical_pd(self):
        """Test historical default probability lookup."""
        calc = CreditAnalysisCalculator()
        result = calc.get_historical_pd(rating='BBB', years=1)

        assert result['value'] > 0
        assert result['metadata']['grade'] == 'Investment Grade'


class TestBondPortfolio:
    """Test bond portfolio calculations."""

    def test_portfolio_duration(self):
        """Test portfolio duration calculation."""
        calc = BondPortfolioCalculator()

        bonds = [
            {'weight': 0.4, 'duration': 5, 'convexity': 30, 'price': 1000, 'ytm': 0.04},
            {'weight': 0.6, 'duration': 8, 'convexity': 50, 'price': 1050, 'ytm': 0.045},
        ]

        result = calc.calculate_portfolio_duration(bonds)

        # Portfolio duration = 0.4*5 + 0.6*8 = 6.8
        assert result['value'] == pytest.approx(6.8, rel=0.01)

    def test_immunization_strategy(self):
        """Test immunization strategy."""
        calc = BondPortfolioCalculator()

        available_bonds = [
            {'duration': 3, 'convexity': 15, 'price': 980, 'ytm': 0.04},
            {'duration': 10, 'convexity': 80, 'price': 1020, 'ytm': 0.045},
        ]

        result = calc.calculate_immunization(
            liability_amount=10000,
            liability_duration=6,
            available_bonds=available_bonds,
            strategy='duration_match'
        )

        # Check that weights are positive and sum to 1
        w1 = result['metadata']['short_bond']['weight']
        w2 = result['metadata']['long_bond']['weight']
        assert w1 > 0 and w2 > 0
        assert w1 + w2 == pytest.approx(1.0, rel=0.01)

    def test_risk_contribution(self):
        """Test risk contribution analysis."""
        calc = BondPortfolioCalculator()

        bonds = [
            {'weight': 0.5, 'duration': 4, 'price': 1000},
            {'weight': 0.5, 'duration': 8, 'price': 1000},
        ]

        result = calc.calculate_risk_contribution(bonds)

        # Risk contributions should sum to 100%
        total_risk = sum(rc['risk_contribution_pct'] for rc in result['value'])
        assert total_risk == pytest.approx(100, rel=0.01)

    def test_portfolio_rebalancing(self):
        """Test portfolio rebalancing."""
        calc = BondPortfolioCalculator()

        current_portfolio = [
            {'weight': 0.5, 'duration': 4, 'price': 1000},
            {'weight': 0.5, 'duration': 8, 'price': 1000},
        ]

        result = calc.calculate_rebalancing(
            current_portfolio=current_portfolio,
            target_duration=7
        )

        # Should recommend rebalancing
        assert result['metadata']['rebalancing_needed'] is True


class TestInputValidation:
    """Test input validation and error handling."""

    def test_negative_face_value(self):
        """Test that negative face value raises error."""
        calc = BondPricingCalculator()
        with pytest.raises(ValueError):
            calc.calculate_price(face_value=-1000, coupon_rate=0.05, ytm=0.05, years_to_maturity=10)

    def test_invalid_frequency(self):
        """Test that invalid frequency raises error."""
        calc = BondPricingCalculator()
        with pytest.raises(DataValidationError):
            calc.calculate_price(face_value=1000, coupon_rate=0.05, ytm=0.05, years_to_maturity=10, frequency=3)

    def test_invalid_probability(self):
        """Test that invalid probability raises error."""
        calc = CreditAnalysisCalculator()
        with pytest.raises(ValueError):
            calc.calculate_expected_loss(probability_of_default=1.5, exposure=1000)

    def test_empty_bonds_list(self):
        """Test that empty bonds list raises error."""
        calc = BondPortfolioCalculator()
        with pytest.raises(DataValidationError):
            calc.calculate_portfolio_duration(bonds=[])

    def test_weights_not_sum_to_one(self):
        """Test that weights not summing to 1 raises error."""
        calc = BondPortfolioCalculator()
        bonds = [
            {'weight': 0.3, 'duration': 5, 'convexity': 30, 'price': 1000, 'ytm': 0.04},
            {'weight': 0.5, 'duration': 8, 'convexity': 50, 'price': 1050, 'ytm': 0.045},
        ]
        with pytest.raises(DataValidationError):
            calc.calculate_portfolio_duration(bonds)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
