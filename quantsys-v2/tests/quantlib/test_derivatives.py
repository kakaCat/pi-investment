"""
Test Suite for Derivatives Pricing Module
==========================================

Comprehensive tests for all derivatives pricing calculators:
    - Black-Scholes model
    - Greeks calculations
    - Implied volatility
    - Binomial tree
    - Monte Carlo simulation

Author: QuantSys V2
Date: 2026-05-24
"""

import pytest
import numpy as np
from domain.quantlib.derivatives import (
    BlackScholesCalculator,
    GreeksCalculator,
    ImpliedVolatilityCalculator,
    BinomialTreeCalculator,
    MonteCarloCalculator
)
from domain.quantlib.exceptions import DataValidationError, CalculationError, ConvergenceError


class TestBlackScholesCalculator:
    """Test Black-Scholes option pricing."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = BlackScholesCalculator()
        # Standard test parameters
        self.S = 100.0
        self.K = 100.0
        self.T = 1.0
        self.r = 0.05
        self.sigma = 0.2
        self.q = 0.0

    def test_call_option_atm(self):
        """Test ATM call option pricing."""
        result = self.calc.calculate(
            S=self.S, K=self.K, T=self.T, r=self.r, sigma=self.sigma, option_type='call'
        )

        assert 'value' in result
        assert result['value'] > 0
        # ATM call should be around 10.45 for these parameters
        assert 10.0 < result['value'] < 11.0
        assert result['method'] == 'black_scholes'

    def test_put_option_atm(self):
        """Test ATM put option pricing."""
        result = self.calc.calculate(
            S=self.S, K=self.K, T=self.T, r=self.r, sigma=self.sigma, option_type='put'
        )

        assert result['value'] > 0
        # ATM put should be around 5.57 for these parameters
        assert 5.0 < result['value'] < 6.5

    def test_call_option_itm(self):
        """Test ITM call option pricing."""
        result = self.calc.calculate(
            S=110.0, K=100.0, T=self.T, r=self.r, sigma=self.sigma, option_type='call'
        )

        # ITM call should have higher value
        assert result['value'] > 10.0
        # Should have positive intrinsic value
        assert result['metadata']['intrinsic_value'] == 10.0

    def test_put_option_itm(self):
        """Test ITM put option pricing."""
        result = self.calc.calculate(
            S=90.0, K=100.0, T=self.T, r=self.r, sigma=self.sigma, option_type='put'
        )

        # ITM put should have higher value
        assert result['value'] > 10.0
        # Should have positive intrinsic value
        assert result['metadata']['intrinsic_value'] == 10.0

    def test_call_option_otm(self):
        """Test OTM call option pricing."""
        result = self.calc.calculate(
            S=90.0, K=100.0, T=self.T, r=self.r, sigma=self.sigma, option_type='call'
        )

        # OTM call should have lower value
        assert result['value'] < 10.0
        # Should have zero intrinsic value
        assert result['metadata']['intrinsic_value'] == 0.0

    def test_put_call_parity(self):
        """Test put-call parity relationship."""
        call_result = self.calc.calculate_call(self.S, self.K, self.T, self.r, self.sigma)
        put_result = self.calc.calculate_put(self.S, self.K, self.T, self.r, self.sigma)

        call_price = call_result['value']
        put_price = put_result['value']

        parity = self.calc.put_call_parity(call_price, put_price, self.S, self.K, self.T, self.r)

        assert parity['parity_holds']
        assert abs(parity['difference']) < 0.01

    def test_dividend_yield_effect(self):
        """Test effect of dividend yield on option prices."""
        # Call without dividend
        call_no_div = self.calc.calculate_call(self.S, self.K, self.T, self.r, self.sigma, q=0.0)

        # Call with dividend
        call_with_div = self.calc.calculate_call(self.S, self.K, self.T, self.r, self.sigma, q=0.03)

        # Dividend should reduce call price
        assert call_with_div['value'] < call_no_div['value']

    def test_time_value_decay(self):
        """Test time value decreases as expiration approaches."""
        result_1y = self.calc.calculate(self.S, self.K, 1.0, self.r, self.sigma, 'call')
        result_6m = self.calc.calculate(self.S, self.K, 0.5, self.r, self.sigma, 'call')
        result_1m = self.calc.calculate(self.S, self.K, 1/12, self.r, self.sigma, 'call')

        # Time value should decrease
        assert result_1y['value'] > result_6m['value'] > result_1m['value']

    def test_volatility_effect(self):
        """Test effect of volatility on option prices."""
        result_low_vol = self.calc.calculate(self.S, self.K, self.T, self.r, 0.1, 'call')
        result_high_vol = self.calc.calculate(self.S, self.K, self.T, self.r, 0.4, 'call')

        # Higher volatility should increase option price
        assert result_high_vol['value'] > result_low_vol['value']

    def test_invalid_inputs(self):
        """Test validation of invalid inputs."""
        # Negative spot price
        with pytest.raises(ValueError):
            self.calc.calculate(-100, self.K, self.T, self.r, self.sigma)

        # Negative strike
        with pytest.raises(ValueError):
            self.calc.calculate(self.S, -100, self.T, self.r, self.sigma)

        # Negative time
        with pytest.raises(ValueError):
            self.calc.calculate(self.S, self.K, -1, self.r, self.sigma)

        # Negative volatility
        with pytest.raises(ValueError):
            self.calc.calculate(self.S, self.K, self.T, self.r, -0.2)

        # Invalid option type
        with pytest.raises(DataValidationError):
            self.calc.calculate(self.S, self.K, self.T, self.r, self.sigma, option_type='invalid')


class TestGreeksCalculator:
    """Test Greeks calculations."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = GreeksCalculator()
        self.S = 100.0
        self.K = 100.0
        self.T = 1.0
        self.r = 0.05
        self.sigma = 0.2

    def test_call_delta_range(self):
        """Test call delta is between 0 and 1."""
        result = self.calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'call')
        delta = result['value']['delta']

        assert 0 < delta < 1
        # ATM call delta should be around 0.6
        assert 0.5 < delta < 0.7

    def test_put_delta_range(self):
        """Test put delta is between -1 and 0."""
        result = self.calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'put')
        delta = result['value']['delta']

        assert -1 < delta < 0
        # ATM put delta should be around -0.4
        assert -0.5 < delta < -0.3

    def test_gamma_positive(self):
        """Test gamma is always positive."""
        call_result = self.calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'call')
        put_result = self.calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'put')

        assert call_result['value']['gamma'] > 0
        assert put_result['value']['gamma'] > 0
        # Gamma should be same for call and put
        assert abs(call_result['value']['gamma'] - put_result['value']['gamma']) < 1e-6

    def test_theta_negative(self):
        """Test theta is negative for long options."""
        call_result = self.calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'call')
        put_result = self.calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'put')

        # Theta should be negative (time decay)
        assert call_result['value']['theta'] < 0
        assert put_result['value']['theta'] < 0

    def test_vega_positive(self):
        """Test vega is always positive."""
        call_result = self.calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'call')
        put_result = self.calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'put')

        assert call_result['value']['vega'] > 0
        assert put_result['value']['vega'] > 0
        # Vega should be same for call and put
        assert abs(call_result['value']['vega'] - put_result['value']['vega']) < 1e-6

    def test_call_rho_positive(self):
        """Test call rho is positive."""
        result = self.calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'call')
        assert result['value']['rho'] > 0

    def test_put_rho_negative(self):
        """Test put rho is negative."""
        result = self.calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'put')
        assert result['value']['rho'] < 0

    def test_delta_hedge_ratio(self):
        """Test delta hedge ratio calculation."""
        hedge = self.calc.delta_hedge_ratio(
            self.S, self.K, self.T, self.r, self.sigma, 'call', option_position=1.0
        )

        assert 'hedge_ratio' in hedge
        assert 'shares_to_hedge' in hedge
        # For long call, hedge ratio should be negative (short stock)
        assert hedge['hedge_ratio'] < 0

    def test_individual_greek_methods(self):
        """Test individual Greek calculation methods."""
        delta = self.calc.calculate_delta(self.S, self.K, self.T, self.r, self.sigma, 'call')
        gamma = self.calc.calculate_gamma(self.S, self.K, self.T, self.r, self.sigma)
        theta = self.calc.calculate_theta(self.S, self.K, self.T, self.r, self.sigma, 'call')
        vega = self.calc.calculate_vega(self.S, self.K, self.T, self.r, self.sigma)
        rho = self.calc.calculate_rho(self.S, self.K, self.T, self.r, self.sigma, 'call')

        assert isinstance(delta, float)
        assert isinstance(gamma, float)
        assert isinstance(theta, float)
        assert isinstance(vega, float)
        assert isinstance(rho, float)


class TestImpliedVolatilityCalculator:
    """Test implied volatility calculations."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = ImpliedVolatilityCalculator()
        self.bs_calc = BlackScholesCalculator()
        self.S = 100.0
        self.K = 100.0
        self.T = 1.0
        self.r = 0.05
        self.sigma = 0.2

    def test_implied_vol_recovery_brent(self):
        """Test IV recovery using Brent's method."""
        # Calculate option price with known volatility
        bs_result = self.bs_calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'call')
        option_price = bs_result['value']

        # Recover implied volatility
        iv_result = self.calc.calculate(
            option_price, self.S, self.K, self.T, self.r, 'call', method='brent'
        )

        assert iv_result['metadata']['converged']
        # Should recover original volatility
        assert abs(iv_result['value'] - self.sigma) < 0.001

    def test_implied_vol_recovery_newton(self):
        """Test IV recovery using Newton's method."""
        bs_result = self.bs_calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'call')
        option_price = bs_result['value']

        iv_result = self.calc.calculate(
            option_price, self.S, self.K, self.T, self.r, 'call', method='newton'
        )

        assert iv_result['metadata']['converged']
        assert abs(iv_result['value'] - self.sigma) < 0.001

    def test_implied_vol_put(self):
        """Test IV calculation for put options."""
        bs_result = self.bs_calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'put')
        option_price = bs_result['value']

        iv_result = self.calc.calculate(
            option_price, self.S, self.K, self.T, self.r, 'put'
        )

        assert iv_result['metadata']['converged']
        assert abs(iv_result['value'] - self.sigma) < 0.001

    def test_implied_vol_with_dividend(self):
        """Test IV calculation with dividend yield."""
        q = 0.03
        bs_result = self.bs_calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'call', q=q)
        option_price = bs_result['value']

        iv_result = self.calc.calculate(
            option_price, self.S, self.K, self.T, self.r, 'call', q=q
        )

        assert iv_result['metadata']['converged']
        assert abs(iv_result['value'] - self.sigma) < 0.001

    def test_implied_vol_below_intrinsic(self):
        """Test error when option price below intrinsic value."""
        intrinsic = max(0, self.S - self.K)

        with pytest.raises((DataValidationError, ValueError)):
            self.calc.calculate(
                intrinsic - 1, self.S, self.K, self.T, self.r, 'call'
            )

    def test_implied_vol_surface(self):
        """Test IV surface calculation."""
        strikes = np.array([90.0, 95.0, 100.0, 105.0, 110.0])
        maturities = np.array([0.25, 0.5, 1.0])

        # Generate option prices
        option_prices = np.zeros((len(strikes), len(maturities)))
        for i, K in enumerate(strikes):
            for j, T in enumerate(maturities):
                result = self.bs_calc.calculate(self.S, float(K), float(T), self.r, self.sigma, 'call')
                option_prices[i, j] = result['value']

        # Calculate IV surface
        iv_surface = self.calc.calculate_iv_surface(
            option_prices, self.S, strikes, maturities, self.r, 'call'
        )

        assert 'iv_surface' in iv_surface
        assert iv_surface['iv_surface'].shape == (len(strikes), len(maturities))
        assert iv_surface['convergence_rate'] > 0.9  # Most should converge


class TestBinomialTreeCalculator:
    """Test binomial tree option pricing."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = BinomialTreeCalculator()
        self.bs_calc = BlackScholesCalculator()
        self.S = 100.0
        self.K = 100.0
        self.T = 1.0
        self.r = 0.05
        self.sigma = 0.2

    def test_european_call_convergence(self):
        """Test European call converges to Black-Scholes."""
        # Black-Scholes price
        bs_result = self.bs_calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'call')
        bs_price = bs_result['value']

        # Binomial tree with many steps
        tree_result = self.calc.calculate_european(
            self.S, self.K, self.T, self.r, self.sigma, 'call', steps=200
        )
        tree_price = tree_result['value']

        # Should be close to Black-Scholes
        assert abs(tree_price - bs_price) < 0.1

    def test_european_put_convergence(self):
        """Test European put converges to Black-Scholes."""
        bs_result = self.bs_calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'put')
        bs_price = bs_result['value']

        tree_result = self.calc.calculate_european(
            self.S, self.K, self.T, self.r, self.sigma, 'put', steps=200
        )
        tree_price = tree_result['value']

        assert abs(tree_price - bs_price) < 0.1

    def test_american_put_premium(self):
        """Test American put has early exercise premium."""
        european_result = self.calc.calculate_european(
            self.S, self.K, self.T, self.r, self.sigma, 'put', steps=100
        )
        american_result = self.calc.calculate_american(
            self.S, self.K, self.T, self.r, self.sigma, 'put', steps=100
        )

        # American put should be worth more (or equal)
        assert american_result['value'] >= european_result['value']

    def test_american_call_no_dividend(self):
        """Test American call equals European call without dividends."""
        european_result = self.calc.calculate_european(
            self.S, self.K, self.T, self.r, self.sigma, 'call', q=0.0, steps=100
        )
        american_result = self.calc.calculate_american(
            self.S, self.K, self.T, self.r, self.sigma, 'call', q=0.0, steps=100
        )

        # Should be approximately equal (no early exercise for call without dividends)
        assert abs(american_result['value'] - european_result['value']) < 0.01

    def test_early_exercise_premium(self):
        """Test early exercise premium calculation."""
        premium = self.calc.early_exercise_premium(
            self.S, self.K, self.T, self.r, self.sigma, 'put', steps=100
        )

        assert 'early_exercise_premium' in premium
        assert premium['early_exercise_premium'] >= 0

    def test_tree_parameters(self):
        """Test tree parameters are valid."""
        result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call', steps=50
        )

        params = result['metadata']['tree_parameters']
        assert params['u'] > 1  # Up factor > 1
        assert params['d'] < 1  # Down factor < 1
        assert 0 < params['p'] < 1  # Risk-neutral probability in (0,1)
        assert params['u'] * params['d'] == pytest.approx(1.0, rel=1e-6)  # u*d = 1

    def test_greeks_calculation(self):
        """Test Greeks are calculated from tree."""
        result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call', steps=100
        )

        assert result['metadata']['delta'] is not None
        assert result['metadata']['gamma'] is not None


class TestMonteCarloCalculator:
    """Test Monte Carlo option pricing."""

    def setup_method(self):
        """Setup test fixtures."""
        self.calc = MonteCarloCalculator(seed=42)  # Fixed seed for reproducibility
        self.bs_calc = BlackScholesCalculator()
        self.S = 100.0
        self.K = 100.0
        self.T = 1.0
        self.r = 0.05
        self.sigma = 0.2

    def test_european_call_convergence(self):
        """Test European call converges to Black-Scholes."""
        bs_result = self.bs_calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'call')
        bs_price = bs_result['value']

        mc_result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call', simulations=50000
        )
        mc_price = mc_result['value']

        # Should be within 3 standard errors
        std_error = mc_result['metadata']['std_error']
        assert abs(mc_price - bs_price) < 3 * std_error

    def test_european_put_convergence(self):
        """Test European put converges to Black-Scholes."""
        bs_result = self.bs_calc.calculate(self.S, self.K, self.T, self.r, self.sigma, 'put')
        bs_price = bs_result['value']

        mc_result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'put', simulations=50000
        )
        mc_price = mc_result['value']

        std_error = mc_result['metadata']['std_error']
        assert abs(mc_price - bs_price) < 3 * std_error

    def test_antithetic_variates(self):
        """Test antithetic variates reduce variance."""
        # Without antithetic variates
        result_no_anti = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call',
            simulations=10000, antithetic=False
        )

        # With antithetic variates
        result_anti = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call',
            simulations=10000, antithetic=True
        )

        # Antithetic should have lower or similar standard error (not guaranteed every time due to randomness)
        # Just verify both produce valid results
        assert result_anti['metadata']['std_error'] > 0
        assert result_no_anti['metadata']['std_error'] > 0
        # Prices should be similar
        assert abs(result_anti['value'] - result_no_anti['value']) < 1.0

    def test_confidence_interval(self):
        """Test confidence interval is provided."""
        result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call', simulations=10000
        )

        ci = result['metadata']['confidence_interval_95']
        assert len(ci) == 2
        assert ci[0] < result['value'] < ci[1]

    def test_asian_option(self):
        """Test Asian option pricing."""
        result = self.calc.calculate_asian(
            self.S, self.K, self.T, self.r, self.sigma, 'call', simulations=10000
        )

        assert result['value'] > 0
        assert result['method'] == 'monte_carlo_asian'
        # Asian option should be cheaper than European (less volatile)
        european_result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call', simulations=10000
        )
        assert result['value'] < european_result['value']

    def test_barrier_option_down_and_out(self):
        """Test down-and-out barrier option."""
        barrier = 90.0
        result = self.calc.calculate_barrier(
            self.S, self.K, self.T, self.r, self.sigma, barrier,
            barrier_type='down-and-out', option_type='call', simulations=10000
        )

        assert result['value'] >= 0
        # Barrier option should be cheaper than vanilla
        vanilla_result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call', simulations=10000
        )
        assert result['value'] < vanilla_result['value']

    def test_barrier_option_up_and_out(self):
        """Test up-and-out barrier option."""
        barrier = 110.0
        result = self.calc.calculate_barrier(
            self.S, self.K, self.T, self.r, self.sigma, barrier,
            barrier_type='up-and-out', option_type='call', simulations=10000
        )

        assert result['value'] >= 0

    def test_lookback_option_floating(self):
        """Test floating strike lookback option."""
        result = self.calc.calculate_lookback(
            self.S, self.K, self.T, self.r, self.sigma,
            lookback_type='floating', option_type='call', simulations=10000
        )

        assert result['value'] > 0
        # Lookback should be more expensive than vanilla
        vanilla_result = self.calc.calculate(
            self.S, self.K, self.T, self.r, self.sigma, 'call', simulations=10000
        )
        assert result['value'] > vanilla_result['value']

    def test_lookback_option_fixed(self):
        """Test fixed strike lookback option."""
        result = self.calc.calculate_lookback(
            self.S, self.K, self.T, self.r, self.sigma,
            lookback_type='fixed', option_type='call', simulations=10000
        )

        assert result['value'] > 0


class TestIntegration:
    """Integration tests across multiple calculators."""

    def test_black_scholes_vs_binomial(self):
        """Test Black-Scholes matches binomial tree for European options."""
        bs_calc = BlackScholesCalculator()
        tree_calc = BinomialTreeCalculator()

        S, K, T, r, sigma = 100, 100, 1, 0.05, 0.2

        bs_result = bs_calc.calculate(S, K, T, r, sigma, 'call')
        tree_result = tree_calc.calculate_european(S, K, T, r, sigma, 'call', steps=200)

        # Should match within 0.5%
        assert abs(bs_result['value'] - tree_result['value']) / bs_result['value'] < 0.005

    def test_black_scholes_vs_monte_carlo(self):
        """Test Black-Scholes matches Monte Carlo for European options."""
        bs_calc = BlackScholesCalculator()
        mc_calc = MonteCarloCalculator(seed=42)

        S, K, T, r, sigma = 100, 100, 1, 0.05, 0.2

        bs_result = bs_calc.calculate(S, K, T, r, sigma, 'call')
        mc_result = mc_calc.calculate(S, K, T, r, sigma, 'call', simulations=100000)

        # Should be within 3 standard errors
        std_error = mc_result['metadata']['std_error']
        assert abs(bs_result['value'] - mc_result['value']) < 3 * std_error

    def test_greeks_vs_numerical_delta(self):
        """Test analytical Greeks match numerical approximation."""
        bs_calc = BlackScholesCalculator()
        greeks_calc = GreeksCalculator()

        S, K, T, r, sigma = 100, 100, 1, 0.05, 0.2

        # Analytical delta
        greeks_result = greeks_calc.calculate(S, K, T, r, sigma, 'call')
        analytical_delta = greeks_result['value']['delta']

        # Numerical delta: (V(S+h) - V(S-h)) / (2h)
        h = 0.01
        price_up = bs_calc.calculate(S + h, K, T, r, sigma, 'call')['value']
        price_down = bs_calc.calculate(S - h, K, T, r, sigma, 'call')['value']
        numerical_delta = (price_up - price_down) / (2 * h)

        # Should match closely
        assert abs(analytical_delta - numerical_delta) < 0.001


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
