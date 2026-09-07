"""
Greeks Calculations
===================

Calculate option Greeks (sensitivities) for risk management and hedging.

Greeks measure the sensitivity of option prices to various factors:
    - Delta: Sensitivity to underlying price changes
    - Gamma: Sensitivity of delta to underlying price changes
    - Theta: Time decay (sensitivity to time passage)
    - Vega: Sensitivity to volatility changes
    - Rho: Sensitivity to interest rate changes

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
from scipy.stats import norm
from typing import Dict, Any
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import DataValidationError, CalculationError


class GreeksCalculator(BaseCalculator):
    """
    Option Greeks calculator.

    Calculates all first-order and second-order Greeks for European options.

    Features:
        - Delta, Gamma, Theta, Vega, Rho
        - Second-order Greeks (Vanna, Volga, Charm)
        - Call and put support
        - Dividend yield support

    Example:
        >>> calc = GreeksCalculator()
        >>> greeks = calc.calculate(S=100, K=100, T=1, r=0.05, sigma=0.2, option_type='call')
        >>> print(f"Delta: {greeks['value']['delta']:.4f}")
        Delta: 0.6368
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Greeks calculator.

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
        Calculate all Greeks for an option.

        Args:
            S: Current spot price
            K: Strike price
            T: Time to maturity (years)
            r: Risk-free rate (annualized)
            sigma: Volatility (annualized)
            option_type: 'call' or 'put'
            q: Dividend yield (default: 0.0)

        Returns:
            Dictionary containing all Greeks:
                - delta: Price sensitivity
                - gamma: Delta sensitivity
                - theta: Time decay (per day)
                - vega: Volatility sensitivity (per 1% change)
                - rho: Interest rate sensitivity (per 1% change)
                - vanna: Delta sensitivity to volatility
                - volga: Vega sensitivity to volatility
                - charm: Delta decay over time

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

            # Standard normal PDF and CDF
            n_d1 = norm.pdf(d1)  # φ(d1)
            N_d1 = norm.cdf(d1)  # Φ(d1)
            N_d2 = norm.cdf(d2)  # Φ(d2)

            # Calculate Greeks
            greeks = {}

            # Delta
            if option_type == 'call':
                greeks['delta'] = np.exp(-q * T) * N_d1
            else:  # put
                greeks['delta'] = -np.exp(-q * T) * norm.cdf(-d1)

            # Gamma (same for call and put)
            greeks['gamma'] = (n_d1 * np.exp(-q * T)) / (S * sigma * np.sqrt(T))

            # Theta (per day)
            term1 = -(S * n_d1 * sigma * np.exp(-q * T)) / (2 * np.sqrt(T))
            if option_type == 'call':
                term2 = -r * K * np.exp(-r * T) * N_d2
                term3 = q * S * np.exp(-q * T) * N_d1
                greeks['theta'] = (term1 + term2 + term3) / 365
            else:  # put
                term2 = r * K * np.exp(-r * T) * norm.cdf(-d2)
                term3 = -q * S * np.exp(-q * T) * norm.cdf(-d1)
                greeks['theta'] = (term1 + term2 + term3) / 365

            # Vega (per 1% change in volatility)
            greeks['vega'] = (S * n_d1 * np.sqrt(T) * np.exp(-q * T)) / 100

            # Rho (per 1% change in interest rate)
            if option_type == 'call':
                greeks['rho'] = (K * T * np.exp(-r * T) * N_d2) / 100
            else:  # put
                greeks['rho'] = -(K * T * np.exp(-r * T) * norm.cdf(-d2)) / 100

            # Second-order Greeks
            # Vanna: sensitivity of delta to volatility
            greeks['vanna'] = -(greeks['vega'] * 100 * d2) / sigma

            # Volga (Vomma): sensitivity of vega to volatility
            greeks['volga'] = (greeks['vega'] * 100 * d1 * d2) / sigma

            # Charm: delta decay over time (per day)
            if option_type == 'call':
                charm_term1 = q * np.exp(-q * T) * N_d1
                charm_term2 = np.exp(-q * T) * n_d1 * (2 * (r - q) * T - d2 * sigma * np.sqrt(T))
                charm_term2 /= (2 * T * sigma * np.sqrt(T))
                greeks['charm'] = (charm_term1 - charm_term2) / 365
            else:  # put
                charm_term1 = -q * np.exp(-q * T) * norm.cdf(-d1)
                charm_term2 = np.exp(-q * T) * n_d1 * (2 * (r - q) * T - d2 * sigma * np.sqrt(T))
                charm_term2 /= (2 * T * sigma * np.sqrt(T))
                greeks['charm'] = (charm_term1 - charm_term2) / 365

            return self._create_result_dict(
                value=greeks,
                method='greeks',
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
                    'n_d1': n_d1,
                    'N_d1': N_d1,
                    'N_d2': N_d2
                }
            )

        except Exception as e:
            raise CalculationError(
                f"Greeks calculation failed: {str(e)}",
                calculation_type='greeks'
            )

    def calculate_delta(self, S: float, K: float, T: float, r: float, sigma: float,
                        option_type: str = 'call', q: float = 0.0) -> float:
        """
        Calculate delta only.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            q: Dividend yield

        Returns:
            Delta value
        """
        result = self.calculate(S, K, T, r, sigma, option_type, q)
        return result['value']['delta']

    def calculate_gamma(self, S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
        """
        Calculate gamma only.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield

        Returns:
            Gamma value
        """
        result = self.calculate(S, K, T, r, sigma, 'call', q)
        return result['value']['gamma']

    def calculate_theta(self, S: float, K: float, T: float, r: float, sigma: float,
                        option_type: str = 'call', q: float = 0.0) -> float:
        """
        Calculate theta only.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            q: Dividend yield

        Returns:
            Theta value (per day)
        """
        result = self.calculate(S, K, T, r, sigma, option_type, q)
        return result['value']['theta']

    def calculate_vega(self, S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
        """
        Calculate vega only.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield

        Returns:
            Vega value (per 1% volatility change)
        """
        result = self.calculate(S, K, T, r, sigma, 'call', q)
        return result['value']['vega']

    def calculate_rho(self, S: float, K: float, T: float, r: float, sigma: float,
                      option_type: str = 'call', q: float = 0.0) -> float:
        """
        Calculate rho only.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            q: Dividend yield

        Returns:
            Rho value (per 1% rate change)
        """
        result = self.calculate(S, K, T, r, sigma, option_type, q)
        return result['value']['rho']

    def delta_hedge_ratio(self, S: float, K: float, T: float, r: float, sigma: float,
                          option_type: str = 'call', q: float = 0.0,
                          option_position: float = 1.0) -> Dict[str, Any]:
        """
        Calculate delta hedge ratio for a given option position.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            q: Dividend yield
            option_position: Number of option contracts (positive for long, negative for short)

        Returns:
            Dictionary with hedge information
        """
        delta = self.calculate_delta(S, K, T, r, sigma, option_type, q)
        hedge_ratio = -delta * option_position  # Opposite sign for hedging

        return {
            'option_position': option_position,
            'option_delta': delta,
            'hedge_ratio': hedge_ratio,
            'shares_to_hedge': hedge_ratio,
            'interpretation': f"{'Buy' if hedge_ratio > 0 else 'Sell'} {abs(hedge_ratio):.4f} shares per option"
        }

    def get_supported_methods(self) -> list:
        """Get list of supported calculation methods."""
        return ['greeks', 'delta', 'gamma', 'theta', 'vega', 'rho', 'delta_hedge']
