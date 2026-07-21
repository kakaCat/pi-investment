"""
Black-Scholes Option Pricing Model
===================================

Implementation of the Black-Scholes-Merton model for European option pricing.

The Black-Scholes formula provides closed-form solutions for European call and put options.

Formula:
    Call: C = S*N(d1) - K*e^(-rT)*N(d2)
    Put:  P = K*e^(-rT)*N(-d2) - S*N(-d1)

    where:
        d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)
        d2 = d1 - σ√T
        N(x) = cumulative standard normal distribution

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
from scipy.stats import norm
from typing import Dict, Any, Union
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import DataValidationError, CalculationError


class BlackScholesCalculator(BaseCalculator):
    """
    Black-Scholes-Merton option pricing calculator.

    Calculates European option prices using the Black-Scholes formula.

    Features:
        - Call and put option pricing
        - Dividend yield support
        - Input validation
        - Standardized result format

    Example:
        >>> calc = BlackScholesCalculator()
        >>> result = calc.calculate(S=100, K=100, T=1, r=0.05, sigma=0.2, option_type='call')
        >>> print(f"Option price: {result['value']:.4f}")
        Option price: 10.4506
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Black-Scholes calculator.

        Args:
            precision: Number of decimal places for results (default: 6)
            risk_free_rate: Default risk-free rate (default: 0.0)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  S: float,
                  K: float,
                  T: float,
                  r: float,
                  sigma: float,
                  option_type: str = 'call',
                  q: float = 0.0) -> Dict[str, Any]:
        """
        Calculate Black-Scholes option price.

        Args:
            S: Current spot price of underlying asset
            K: Strike price
            T: Time to maturity (in years)
            r: Risk-free interest rate (annualized)
            sigma: Volatility (annualized standard deviation)
            option_type: 'call' or 'put' (default: 'call')
            q: Dividend yield (default: 0.0)

        Returns:
            Dictionary containing:
                - value: Option price
                - d1: d1 parameter
                - d2: d2 parameter
                - N_d1: N(d1) or N(-d1) for put
                - N_d2: N(d2) or N(-d2) for put
                - intrinsic_value: Intrinsic value of option
                - time_value: Time value of option
                - method: 'black_scholes'
                - parameters: Input parameters

        Raises:
            DataValidationError: If inputs are invalid
            CalculationError: If calculation fails
        """
        # Validate inputs
        S = self._validate_positive(S, 'spot_price')
        K = self._validate_positive(K, 'strike_price')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'risk_free_rate')
        sigma = self._validate_positive(sigma, 'volatility')
        q = self._validate_numeric_input(q, 'dividend_yield')

        # Validate option type
        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise DataValidationError(
                "option_type must be 'call' or 'put'",
                field_name='option_type'
            )

        try:
            # Calculate d1 and d2
            d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)

            # Calculate option price
            if option_type == 'call':
                N_d1 = norm.cdf(d1)
                N_d2 = norm.cdf(d2)
                price = S * np.exp(-q * T) * N_d1 - K * np.exp(-r * T) * N_d2
                intrinsic_value = max(0, S - K)
            else:  # put
                N_d1 = norm.cdf(-d1)
                N_d2 = norm.cdf(-d2)
                price = K * np.exp(-r * T) * N_d2 - S * np.exp(-q * T) * N_d1
                intrinsic_value = max(0, K - S)

            time_value = price - intrinsic_value

            return self._create_result_dict(
                value=price,
                method='black_scholes',
                parameters={
                    'S': S,
                    'K': K,
                    'T': T,
                    'r': r,
                    'sigma': sigma,
                    'q': q,
                    'option_type': option_type
                },
                metadata={
                    'd1': d1,
                    'd2': d2,
                    'N_d1': N_d1,
                    'N_d2': N_d2,
                    'intrinsic_value': intrinsic_value,
                    'time_value': time_value
                }
            )

        except Exception as e:
            raise CalculationError(
                f"Black-Scholes calculation failed: {str(e)}",
                calculation_type='black_scholes'
            )

    def calculate_call(self, S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> Dict[str, Any]:
        """
        Calculate call option price.

        Convenience method for call options.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield (default: 0.0)

        Returns:
            Result dictionary with option price
        """
        return self.calculate(S, K, T, r, sigma, option_type='call', q=q)

    def calculate_put(self, S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> Dict[str, Any]:
        """
        Calculate put option price.

        Convenience method for put options.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield (default: 0.0)

        Returns:
            Result dictionary with option price
        """
        return self.calculate(S, K, T, r, sigma, option_type='put', q=q)

    def put_call_parity(self, call_price: float, put_price: float, S: float, K: float,
                        T: float, r: float, q: float = 0.0) -> Dict[str, Any]:
        """
        Verify put-call parity relationship.

        Put-call parity: C - P = S*e^(-qT) - K*e^(-rT)

        Args:
            call_price: Call option price
            put_price: Put option price
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            q: Dividend yield (default: 0.0)

        Returns:
            Dictionary with parity analysis
        """
        # Validate inputs
        call_price = self._validate_positive(call_price, 'call_price')
        put_price = self._validate_positive(put_price, 'put_price')
        S = self._validate_positive(S, 'spot_price')
        K = self._validate_positive(K, 'strike_price')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'risk_free_rate')
        q = self._validate_numeric_input(q, 'dividend_yield')

        # Calculate parity components
        left_side = call_price - put_price
        right_side = S * np.exp(-q * T) - K * np.exp(-r * T)

        difference = abs(left_side - right_side)
        parity_holds = difference < 0.01  # Tolerance of 1 cent

        return {
            'call_price': call_price,
            'put_price': put_price,
            'left_side': left_side,
            'right_side': right_side,
            'difference': difference,
            'parity_holds': parity_holds,
            'interpretation': 'Parity holds' if parity_holds else 'Arbitrage opportunity exists'
        }

    def get_supported_methods(self) -> list:
        """Get list of supported calculation methods."""
        return ['black_scholes', 'call', 'put', 'put_call_parity']
