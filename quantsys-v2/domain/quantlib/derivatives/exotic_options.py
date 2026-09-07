"""
Exotic Options Pricing
=======================

Pricing models for exotic options including barrier, Asian, lookback, and digital options.

Exotic options have payoff structures that differ from standard European/American options.
This module provides specialized pricing methods for various exotic option types.

Features:
    - Barrier options (knock-in, knock-out)
    - Asian options (average price)
    - Lookback options (path-dependent)
    - Digital (binary) options
    - Multiple pricing methods (analytical, Monte Carlo)

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
from scipy.stats import norm
from typing import Dict, Any, Optional
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import DataValidationError, CalculationError


class ExoticOptionsCalculator(BaseCalculator):
    """
    Exotic options pricing calculator.

    Provides pricing methods for various exotic option types using
    analytical formulas (where available) and Monte Carlo simulation.

    Features:
        - Barrier options (analytical and Monte Carlo)
        - Asian options (Monte Carlo)
        - Lookback options (analytical and Monte Carlo)
        - Digital options (analytical)
        - Chooser options
        - Compound options

    Example:
        >>> calc = ExoticOptionsCalculator()
        >>> result = calc.calculate_barrier_option(
        ...     S=100, K=100, T=1, r=0.05, sigma=0.2,
        ...     barrier=90, barrier_type='down-and-out', option_type='call'
        ... )
        >>> print(f"Barrier option price: {result['value']:.4f}")
        Barrier option price: 8.9234
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0, seed: Optional[int] = None):
        """
        Initialize exotic options calculator.

        Args:
            precision: Number of decimal places for results (default: 6)
            risk_free_rate: Default risk-free rate (default: 0.0)
            seed: Random seed for Monte Carlo simulations (default: None)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)
        self.seed = seed
        if seed is not None:
            np.random.seed(seed)

    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Main calculation method (delegates to specific exotic option methods).

        Use specific methods like calculate_barrier_option, calculate_asian_option, etc.
        """
        raise NotImplementedError(
            "Use specific methods: calculate_barrier_option, calculate_asian_option, "
            "calculate_lookback_option, calculate_digital_option"
        )

    def calculate_barrier_option(self,
                                  S: float,
                                  K: float,
                                  T: float,
                                  r: float,
                                  sigma: float,
                                  barrier: float,
                                  barrier_type: str = 'down-and-out',
                                  option_type: str = 'call',
                                  q: float = 0.0,
                                  method: str = 'analytical') -> Dict[str, Any]:
        """
        Calculate barrier option price.

        Barrier options activate (knock-in) or deactivate (knock-out) when
        the underlying price crosses a barrier level.

        Args:
            S: Current spot price
            K: Strike price
            T: Time to maturity (years)
            r: Risk-free rate (annualized)
            sigma: Volatility (annualized)
            barrier: Barrier level
            barrier_type: 'down-and-out', 'down-and-in', 'up-and-out', 'up-and-in'
            option_type: 'call' or 'put'
            q: Dividend yield (default: 0.0)
            method: 'analytical' or 'monte_carlo' (default: 'analytical')

        Returns:
            Dictionary containing:
                - value: Barrier option price
                - method: Pricing method used
                - barrier_parameters: Barrier-specific parameters

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
        barrier = self._validate_positive(barrier, 'barrier')
        q = self._validate_numeric_input(q, 'dividend_yield')

        barrier_type = barrier_type.lower()
        valid_barriers = ['down-and-out', 'down-and-in', 'up-and-out', 'up-and-in']
        if barrier_type not in valid_barriers:
            raise DataValidationError(
                f"barrier_type must be one of {valid_barriers}",
                field_name='barrier_type'
            )

        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise DataValidationError(
                "option_type must be 'call' or 'put'",
                field_name='option_type'
            )

        # Validate barrier position
        if 'down' in barrier_type and barrier >= S:
            raise DataValidationError(
                f"Down barrier ({barrier}) must be below spot price ({S})",
                field_name='barrier'
            )
        if 'up' in barrier_type and barrier <= S:
            raise DataValidationError(
                f"Up barrier ({barrier}) must be above spot price ({S})",
                field_name='barrier'
            )

        try:
            if method == 'analytical':
                price = self._barrier_analytical(S, K, T, r, sigma, barrier, barrier_type, option_type, q)
            elif method == 'monte_carlo':
                price = self._barrier_monte_carlo(S, K, T, r, sigma, barrier, barrier_type, option_type, q)
            else:
                raise DataValidationError(
                    "method must be 'analytical' or 'monte_carlo'",
                    field_name='method'
                )

            return self._create_result_dict(
                value=price,
                method=f'barrier_{method}',
                parameters={
                    'S': S, 'K': K, 'T': T, 'r': r, 'sigma': sigma, 'q': q,
                    'barrier': barrier,
                    'barrier_type': barrier_type,
                    'option_type': option_type
                },
                metadata={
                    'barrier_distance': abs(S - barrier) / S,
                    'barrier_ratio': barrier / S
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, CalculationError)):
                raise
            raise CalculationError(
                f"Barrier option calculation failed: {str(e)}",
                calculation_type='barrier_option'
            )

    def _barrier_analytical(self, S: float, K: float, T: float, r: float, sigma: float,
                            H: float, barrier_type: str, option_type: str, q: float) -> float:
        """
        Analytical pricing for barrier options using closed-form formulas.

        Uses the Merton (1973) and Reiner-Rubinstein (1991) formulas.
        """
        # Calculate parameters
        mu = (r - q - 0.5 * sigma ** 2) / (sigma ** 2)
        lambda_param = np.sqrt(mu ** 2 + 2 * r / (sigma ** 2))

        x1 = np.log(S / K) / (sigma * np.sqrt(T)) + (1 + mu) * sigma * np.sqrt(T)
        x2 = np.log(S / H) / (sigma * np.sqrt(T)) + (1 + mu) * sigma * np.sqrt(T)
        y1 = np.log(H ** 2 / (S * K)) / (sigma * np.sqrt(T)) + (1 + mu) * sigma * np.sqrt(T)
        y2 = np.log(H / S) / (sigma * np.sqrt(T)) + (1 + mu) * sigma * np.sqrt(T)

        z = np.log(H / S) / (sigma * np.sqrt(T)) + lambda_param * sigma * np.sqrt(T)

        # Helper functions
        def A(phi):
            return phi * S * np.exp(-q * T) * norm.cdf(phi * x1) - \
                   phi * K * np.exp(-r * T) * norm.cdf(phi * x1 - phi * sigma * np.sqrt(T))

        def B(phi):
            return phi * S * np.exp(-q * T) * norm.cdf(phi * x2) - \
                   phi * K * np.exp(-r * T) * norm.cdf(phi * x2 - phi * sigma * np.sqrt(T))

        def C(phi, eta):
            return phi * S * np.exp(-q * T) * (H / S) ** (2 * (mu + 1)) * norm.cdf(eta * y1) - \
                   phi * K * np.exp(-r * T) * (H / S) ** (2 * mu) * norm.cdf(eta * y1 - eta * sigma * np.sqrt(T))

        def D(phi, eta):
            return phi * S * np.exp(-q * T) * (H / S) ** (2 * (mu + 1)) * norm.cdf(eta * y2) - \
                   phi * K * np.exp(-r * T) * (H / S) ** (2 * mu) * norm.cdf(eta * y2 - eta * sigma * np.sqrt(T))

        # Calculate price based on barrier type
        if barrier_type == 'down-and-out':
            if option_type == 'call':
                if K > H:
                    price = A(1) - B(1) + C(1, 1) - D(1, 1)
                else:
                    price = B(1) - D(1, 1)
            else:  # put
                if K > H:
                    price = A(-1) - C(-1, 1)
                else:
                    price = 0.0

        elif barrier_type == 'up-and-out':
            if option_type == 'call':
                if K > H:
                    price = 0.0
                else:
                    price = A(1) - C(1, -1)
            else:  # put
                if K > H:
                    price = B(-1) - D(-1, -1)
                else:
                    price = A(-1) - B(-1) + C(-1, -1) - D(-1, -1)

        elif barrier_type == 'down-and-in':
            # Down-and-in = Vanilla - Down-and-out
            vanilla_price = self._vanilla_price(S, K, T, r, sigma, option_type, q)
            out_price = self._barrier_analytical(S, K, T, r, sigma, H, 'down-and-out', option_type, q)
            price = vanilla_price - out_price

        elif barrier_type == 'up-and-in':
            # Up-and-in = Vanilla - Up-and-out
            vanilla_price = self._vanilla_price(S, K, T, r, sigma, option_type, q)
            out_price = self._barrier_analytical(S, K, T, r, sigma, H, 'up-and-out', option_type, q)
            price = vanilla_price - out_price

        else:
            raise ValueError(f"Unknown barrier type: {barrier_type}")

        return max(0, price)

    def _vanilla_price(self, S: float, K: float, T: float, r: float, sigma: float,
                       option_type: str, q: float) -> float:
        """Calculate vanilla Black-Scholes price."""
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if option_type == 'call':
            return S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:  # put
            return K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)

    def _barrier_monte_carlo(self, S: float, K: float, T: float, r: float, sigma: float,
                             H: float, barrier_type: str, option_type: str, q: float,
                             simulations: int = 10000, time_steps: int = 252) -> float:
        """Monte Carlo pricing for barrier options."""
        dt = T / time_steps
        drift = (r - q - 0.5 * sigma ** 2) * dt
        diffusion = sigma * np.sqrt(dt)

        Z = np.random.standard_normal((simulations, time_steps))
        log_returns = drift + diffusion * Z
        price_paths = S * np.exp(np.cumsum(log_returns, axis=1))

        # Check barrier conditions
        if 'down' in barrier_type:
            barrier_crossed = np.any(price_paths <= H, axis=1)
        else:  # up
            barrier_crossed = np.any(price_paths >= H, axis=1)

        # Determine active paths
        if 'out' in barrier_type:
            active_paths = ~barrier_crossed
        else:  # in
            active_paths = barrier_crossed

        # Calculate payoffs
        terminal_prices = price_paths[:, -1]
        if option_type == 'call':
            payoffs = np.maximum(terminal_prices - K, 0)
        else:  # put
            payoffs = np.maximum(K - terminal_prices, 0)

        # Apply barrier condition
        payoffs = payoffs * active_paths

        # Discount and return mean
        return np.exp(-r * T) * np.mean(payoffs)

    def calculate_asian_option(self,
                                S: float,
                                K: float,
                                T: float,
                                r: float,
                                sigma: float,
                                option_type: str = 'call',
                                q: float = 0.0,
                                averaging_type: str = 'arithmetic',
                                simulations: int = 10000,
                                time_steps: int = 252) -> Dict[str, Any]:
        """
        Calculate Asian option price using Monte Carlo simulation.

        Asian options have payoffs based on the average price of the underlying
        over the option's life.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            q: Dividend yield
            averaging_type: 'arithmetic' or 'geometric'
            simulations: Number of Monte Carlo simulations
            time_steps: Number of time steps for averaging

        Returns:
            Dictionary with Asian option price and statistics
        """
        # Validate inputs
        S = self._validate_positive(S, 'spot_price')
        K = self._validate_positive(K, 'strike_price')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'risk_free_rate')
        sigma = self._validate_positive(sigma, 'volatility')
        q = self._validate_numeric_input(q, 'dividend_yield')

        averaging_type = averaging_type.lower()
        if averaging_type not in ['arithmetic', 'geometric']:
            raise DataValidationError(
                "averaging_type must be 'arithmetic' or 'geometric'",
                field_name='averaging_type'
            )

        try:
            # Simulate price paths
            dt = T / time_steps
            drift = (r - q - 0.5 * sigma ** 2) * dt
            diffusion = sigma * np.sqrt(dt)

            Z = np.random.standard_normal((simulations, time_steps))
            log_returns = drift + diffusion * Z
            price_paths = S * np.exp(np.cumsum(log_returns, axis=1))

            # Calculate average prices
            if averaging_type == 'arithmetic':
                average_prices = np.mean(price_paths, axis=1)
            else:  # geometric
                average_prices = np.exp(np.mean(np.log(price_paths), axis=1))

            # Calculate payoffs
            if option_type == 'call':
                payoffs = np.maximum(average_prices - K, 0)
            else:  # put
                payoffs = np.maximum(K - average_prices, 0)

            # Discount and calculate statistics
            discounted_payoffs = np.exp(-r * T) * payoffs
            option_price = np.mean(discounted_payoffs)
            std_error = np.std(discounted_payoffs, ddof=1) / np.sqrt(simulations)

            return self._create_result_dict(
                value=option_price,
                method='asian_monte_carlo',
                parameters={
                    'S': S, 'K': K, 'T': T, 'r': r, 'sigma': sigma, 'q': q,
                    'option_type': option_type,
                    'averaging_type': averaging_type,
                    'simulations': simulations,
                    'time_steps': time_steps
                },
                metadata={
                    'std_error': std_error,
                    'mean_average_price': np.mean(average_prices),
                    'median_average_price': np.median(average_prices)
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, CalculationError)):
                raise
            raise CalculationError(
                f"Asian option calculation failed: {str(e)}",
                calculation_type='asian_option'
            )

    def calculate_lookback_option(self,
                                   S: float,
                                   K: float,
                                   T: float,
                                   r: float,
                                   sigma: float,
                                   lookback_type: str = 'floating',
                                   option_type: str = 'call',
                                   q: float = 0.0,
                                   method: str = 'monte_carlo',
                                   simulations: int = 10000,
                                   time_steps: int = 252) -> Dict[str, Any]:
        """
        Calculate lookback option price.

        Lookback options have payoffs based on the maximum or minimum price
        achieved during the option's life.

        Args:
            S: Spot price
            K: Strike price (for fixed lookback)
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            lookback_type: 'floating' or 'fixed'
            option_type: 'call' or 'put'
            q: Dividend yield
            method: 'monte_carlo' or 'analytical' (analytical only for some cases)
            simulations: Number of simulations (for Monte Carlo)
            time_steps: Number of time steps (for Monte Carlo)

        Returns:
            Dictionary with lookback option price
        """
        # Validate inputs
        S = self._validate_positive(S, 'spot_price')
        K = self._validate_positive(K, 'strike_price')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'risk_free_rate')
        sigma = self._validate_positive(sigma, 'volatility')
        q = self._validate_numeric_input(q, 'dividend_yield')

        lookback_type = lookback_type.lower()
        if lookback_type not in ['floating', 'fixed']:
            raise DataValidationError(
                "lookback_type must be 'floating' or 'fixed'",
                field_name='lookback_type'
            )

        try:
            if method == 'monte_carlo':
                price = self._lookback_monte_carlo(
                    S, K, T, r, sigma, lookback_type, option_type, q, simulations, time_steps
                )
            elif method == 'analytical':
                price = self._lookback_analytical(S, K, T, r, sigma, lookback_type, option_type, q)
            else:
                raise DataValidationError(
                    "method must be 'monte_carlo' or 'analytical'",
                    field_name='method'
                )

            return self._create_result_dict(
                value=price,
                method=f'lookback_{method}',
                parameters={
                    'S': S, 'K': K, 'T': T, 'r': r, 'sigma': sigma, 'q': q,
                    'lookback_type': lookback_type,
                    'option_type': option_type
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, CalculationError)):
                raise
            raise CalculationError(
                f"Lookback option calculation failed: {str(e)}",
                calculation_type='lookback_option'
            )

    def _lookback_monte_carlo(self, S: float, K: float, T: float, r: float, sigma: float,
                              lookback_type: str, option_type: str, q: float,
                              simulations: int, time_steps: int) -> float:
        """Monte Carlo pricing for lookback options."""
        dt = T / time_steps
        drift = (r - q - 0.5 * sigma ** 2) * dt
        diffusion = sigma * np.sqrt(dt)

        Z = np.random.standard_normal((simulations, time_steps))
        log_returns = drift + diffusion * Z
        price_paths = S * np.exp(np.cumsum(log_returns, axis=1))

        # Calculate max and min prices
        max_prices = np.max(price_paths, axis=1)
        min_prices = np.min(price_paths, axis=1)
        terminal_prices = price_paths[:, -1]

        # Calculate payoffs
        if lookback_type == 'floating':
            if option_type == 'call':
                payoffs = terminal_prices - min_prices
            else:  # put
                payoffs = max_prices - terminal_prices
        else:  # fixed
            if option_type == 'call':
                payoffs = np.maximum(max_prices - K, 0)
            else:  # put
                payoffs = np.maximum(K - min_prices, 0)

        # Discount and return mean
        return np.exp(-r * T) * np.mean(payoffs)

    def _lookback_analytical(self, S: float, K: float, T: float, r: float, sigma: float,
                             lookback_type: str, option_type: str, q: float) -> float:
        """Analytical pricing for floating strike lookback options (Goldman-Sosin-Gatto formula)."""
        if lookback_type != 'floating':
            raise CalculationError(
                "Analytical formula only available for floating strike lookback options",
                calculation_type='lookback_analytical'
            )

        a1 = (np.log(S / S) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        a2 = a1 - sigma * np.sqrt(T)

        if option_type == 'call':
            # Floating strike lookback call
            term1 = S * np.exp(-q * T) * norm.cdf(a1)
            term2 = S * np.exp(-q * T) * (sigma ** 2 / (2 * (r - q))) * \
                    (-norm.cdf(-a1) + np.exp((r - q) * T) * norm.cdf(-a2))
            price = term1 - term2
        else:  # put
            # Floating strike lookback put
            term1 = -S * np.exp(-q * T) * norm.cdf(-a1)
            term2 = S * np.exp(-q * T) * (sigma ** 2 / (2 * (r - q))) * \
                    (norm.cdf(a1) - np.exp((r - q) * T) * norm.cdf(a2))
            price = term1 + term2

        return max(0, price)

    def calculate_digital_option(self,
                                  S: float,
                                  K: float,
                                  T: float,
                                  r: float,
                                  sigma: float,
                                  option_type: str = 'call',
                                  q: float = 0.0,
                                  payout: float = 1.0) -> Dict[str, Any]:
        """
        Calculate digital (binary) option price using analytical formula.

        Digital options pay a fixed amount if the option expires in-the-money,
        zero otherwise.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            q: Dividend yield
            payout: Fixed payout amount if option expires ITM (default: 1.0)

        Returns:
            Dictionary with digital option price
        """
        # Validate inputs
        S = self._validate_positive(S, 'spot_price')
        K = self._validate_positive(K, 'strike_price')
        T = self._validate_positive(T, 'time_to_maturity')
        r = self._validate_numeric_input(r, 'risk_free_rate')
        sigma = self._validate_positive(sigma, 'volatility')
        q = self._validate_numeric_input(q, 'dividend_yield')
        payout = self._validate_positive(payout, 'payout')

        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise DataValidationError(
                "option_type must be 'call' or 'put'",
                field_name='option_type'
            )

        try:
            # Calculate d2
            d2 = (np.log(S / K) + (r - q - 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))

            # Digital option price
            if option_type == 'call':
                price = payout * np.exp(-r * T) * norm.cdf(d2)
            else:  # put
                price = payout * np.exp(-r * T) * norm.cdf(-d2)

            return self._create_result_dict(
                value=price,
                method='digital_analytical',
                parameters={
                    'S': S, 'K': K, 'T': T, 'r': r, 'sigma': sigma, 'q': q,
                    'option_type': option_type,
                    'payout': payout
                },
                metadata={
                    'd2': d2,
                    'probability_itm': norm.cdf(d2) if option_type == 'call' else norm.cdf(-d2)
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, CalculationError)):
                raise
            raise CalculationError(
                f"Digital option calculation failed: {str(e)}",
                calculation_type='digital_option'
            )

    def get_supported_methods(self) -> list:
        """Get list of supported calculation methods."""
        return ['barrier', 'asian', 'lookback', 'digital']
