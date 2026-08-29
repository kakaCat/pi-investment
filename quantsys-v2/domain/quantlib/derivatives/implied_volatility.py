"""
Implied Volatility Calculator
==============================

Calculate implied volatility from option market prices using numerical methods.

Implied volatility is the volatility value that, when input into an option pricing
model, yields the observed market price of the option.

Methods:
    - Newton-Raphson method (fast, requires vega)
    - Brent's method (robust, bracketing method)

Author: QuantSys V2
Date: 2026-05-24
"""
import structlog
logger = structlog.get_logger(__name__)

import numpy as np
from scipy.optimize import brentq, newton
from scipy.stats import norm
from typing import Dict, Any, Optional
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import DataValidationError, CalculationError, ConvergenceError


class ImpliedVolatilityCalculator(BaseCalculator):
    """
    Implied volatility calculator using multiple numerical methods.

    Features:
        - Newton-Raphson method (fast convergence)
        - Brent's method (robust bracketing)
        - Automatic method selection
        - Convergence diagnostics

    Example:
        >>> calc = ImpliedVolatilityCalculator()
        >>> result = calc.calculate(
        ...     option_price=10.45,
        ...     S=100, K=100, T=1, r=0.05,
        ...     option_type='call'
        ... )
        >>> print(f"Implied volatility: {result['value']:.4f}")
        Implied volatility: 0.2000
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize implied volatility calculator.

        Args:
            precision: Number of decimal places for results (default: 6)
            risk_free_rate: Default risk-free rate (default: 0.0)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  option_price: float,
                  S: float,
                  K: float,
                  T: float,
                  r: float,
                  option_type: str = 'call',
                  q: float = 0.0,
                  method: str = 'brent',
                  initial_guess: float = 0.3,
                  max_iterations: int = 100,
                  tolerance: float = 1e-6) -> Dict[str, Any]:
        """
        Calculate implied volatility from option price.

        Args:
            option_price: Observed market price of option
            S: Current spot price
            K: Strike price
            T: Time to maturity (years)
            r: Risk-free rate (annualized)
            option_type: 'call' or 'put'
            q: Dividend yield (default: 0.0)
            method: 'brent' or 'newton' (default: 'brent')
            initial_guess: Initial volatility guess for Newton method (default: 0.3)
            max_iterations: Maximum iterations (default: 100)
            tolerance: Convergence tolerance (default: 1e-6)

        Returns:
            Dictionary containing:
                - value: Implied volatility
                - iterations: Number of iterations
                - method: Method used
                - converged: Whether method converged
                - final_error: Final pricing error

        Raises:
            DataValidationError: If inputs are invalid
            ConvergenceError: If method fails to converge
        """
        # Validate inputs
        option_price = self._validate_positive(option_price, 'option_price')
        S = self._validate_positive(S, 'spot_price')
        K = self._validate_positive(K, 'strike_price')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'risk_free_rate')
        q = self._validate_numeric_input(q, 'dividend_yield')

        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise DataValidationError(
                "option_type must be 'call' or 'put'",
                field_name='option_type'
            )

        # Check intrinsic value
        intrinsic = max(0, S - K) if option_type == 'call' else max(0, K - S)
        if option_price < intrinsic:
            raise DataValidationError(
                f"Option price ({option_price}) below intrinsic value ({intrinsic})",
                field_name='option_price'
            )

        # Select method
        method = method.lower()
        if method == 'brent':
            result = self._brent_method(option_price, S, K, T, r, q, option_type, tolerance)
        elif method == 'newton':
            result = self._newton_method(option_price, S, K, T, r, q, option_type,
                                         initial_guess, max_iterations, tolerance)
        else:
            raise DataValidationError(
                "method must be 'brent' or 'newton'",
                field_name='method'
            )

        return self._create_result_dict(
            value=result['implied_vol'],
            method=f'implied_volatility_{method}',
            parameters={
                'option_price': option_price,
                'S': S,
                'K': K,
                'T': T,
                'r': r,
                'q': q,
                'option_type': option_type
            },
            metadata={
                'iterations': result.get('iterations', 0),
                'converged': result['converged'],
                'final_error': result.get('final_error', 0),
                'method_used': method
            }
        )

    def _black_scholes_price(self, S: float, K: float, T: float, r: float,
                             sigma: float, option_type: str, q: float = 0.0) -> float:
        """
        Calculate Black-Scholes price for given volatility.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            q: Dividend yield

        Returns:
            Option price
        """
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if option_type == 'call':
            price = S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:  # put
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)

        return price

    def _vega(self, S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
        """
        Calculate vega for Newton method.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            q: Dividend yield

        Returns:
            Vega value
        """
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        n_d1 = norm.pdf(d1)
        vega = S * n_d1 * np.sqrt(T) * np.exp(-q * T)
        return vega

    def _brent_method(self, option_price: float, S: float, K: float, T: float,
                      r: float, q: float, option_type: str, tolerance: float) -> Dict[str, Any]:
        """
        Calculate implied volatility using Brent's method.

        Brent's method is a robust bracketing method that combines bisection,
        secant, and inverse quadratic interpolation.

        Args:
            option_price: Target option price
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            q: Dividend yield
            option_type: 'call' or 'put'
            tolerance: Convergence tolerance

        Returns:
            Dictionary with implied volatility and convergence info
        """
        def objective(sigma):
            """Objective function: model_price - market_price"""
            try:
                model_price = self._black_scholes_price(S, K, T, r, sigma, option_type, q)
                return model_price - option_price
            except Exception:
                logger.debug("unexpected exception in module", exc_info=True)
                return np.inf

        try:
            # Bracket the solution between 0.001 and 5.0 (0.1% to 500% volatility)
            implied_vol = brentq(objective, 0.001, 5.0, xtol=tolerance, maxiter=100)

            # Calculate final error
            final_price = self._black_scholes_price(S, K, T, r, implied_vol, option_type, q)
            final_error = abs(final_price - option_price)

            return {
                'implied_vol': implied_vol,
                'converged': True,
                'final_error': final_error
            }

        except ValueError as e:
            raise ConvergenceError(
                f"Brent's method failed to converge: {str(e)}",
                iterations=100
            )

    def _newton_method(self, option_price: float, S: float, K: float, T: float,
                       r: float, q: float, option_type: str, initial_guess: float,
                       max_iterations: int, tolerance: float) -> Dict[str, Any]:
        """
        Calculate implied volatility using Newton-Raphson method.

        Newton-Raphson uses the derivative (vega) for faster convergence.

        Args:
            option_price: Target option price
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            q: Dividend yield
            option_type: 'call' or 'put'
            initial_guess: Initial volatility guess
            max_iterations: Maximum iterations
            tolerance: Convergence tolerance

        Returns:
            Dictionary with implied volatility and convergence info
        """
        sigma = initial_guess
        iterations = 0

        for i in range(max_iterations):
            iterations = i + 1

            # Calculate price and vega
            model_price = self._black_scholes_price(S, K, T, r, sigma, option_type, q)
            vega = self._vega(S, K, T, r, sigma, q)

            # Calculate error
            price_error = model_price - option_price

            # Check convergence
            if abs(price_error) < tolerance:
                return {
                    'implied_vol': sigma,
                    'converged': True,
                    'iterations': iterations,
                    'final_error': abs(price_error)
                }

            # Newton-Raphson update
            if vega < 1e-10:
                raise ConvergenceError(
                    "Vega too small for Newton method",
                    iterations=iterations
                )

            sigma = sigma - price_error / vega

            # Keep sigma in reasonable bounds
            sigma = max(0.001, min(sigma, 5.0))

        # Did not converge
        raise ConvergenceError(
            "Newton method failed to converge",
            iterations=max_iterations
        )

    def calculate_iv_surface(self,
                             option_prices: np.ndarray,
                             S: float,
                             strikes: np.ndarray,
                             maturities: np.ndarray,
                             r: float,
                             option_type: str = 'call',
                             q: float = 0.0) -> Dict[str, Any]:
        """
        Calculate implied volatility surface from option prices.

        Args:
            option_prices: 2D array of option prices (strikes x maturities)
            S: Current spot price
            strikes: Array of strike prices
            maturities: Array of times to maturity
            r: Risk-free rate
            option_type: 'call' or 'put'
            q: Dividend yield

        Returns:
            Dictionary with IV surface and metadata
        """
        if option_prices.shape != (len(strikes), len(maturities)):
            raise DataValidationError(
                f"option_prices shape {option_prices.shape} must match (strikes, maturities) = ({len(strikes)}, {len(maturities)})",
                field_name='option_prices'
            )

        iv_surface = np.zeros_like(option_prices)
        convergence_map = np.zeros_like(option_prices, dtype=bool)

        for i, K in enumerate(strikes):
            for j, T in enumerate(maturities):
                try:
                    result = self.calculate(
                        option_price=option_prices[i, j],
                        S=S, K=K, T=T, r=r,
                        option_type=option_type, q=q
                    )
                    iv_surface[i, j] = result['value']
                    convergence_map[i, j] = result['metadata']['converged']
                except Exception:
                    logger.debug("unexpected exception in module", exc_info=True)
                    iv_surface[i, j] = np.nan
                    convergence_map[i, j] = False

        return {
            'iv_surface': iv_surface,
            'strikes': strikes,
            'maturities': maturities,
            'convergence_map': convergence_map,
            'convergence_rate': np.mean(convergence_map)
        }

    def get_supported_methods(self) -> list:
        """Get list of supported calculation methods."""
        return ['implied_volatility', 'brent', 'newton', 'iv_surface']
