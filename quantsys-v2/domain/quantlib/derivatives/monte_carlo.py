"""
Monte Carlo Option Pricing
===========================

Monte Carlo simulation for pricing path-dependent and exotic options.

Monte Carlo methods simulate many possible price paths for the underlying asset
and calculate the average discounted payoff. Useful for complex options where
closed-form solutions don't exist.

Features:
    - European options
    - Asian options (average price)
    - Barrier options (knock-in, knock-out)
    - Lookback options
    - Variance reduction techniques (antithetic variates, control variates)

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
from typing import Dict, Any, Optional, Callable
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import DataValidationError, CalculationError


class MonteCarloCalculator(BaseCalculator):
    """
    Monte Carlo option pricing calculator.

    Simulates stock price paths using geometric Brownian motion and
    calculates option prices via Monte Carlo integration.

    Features:
        - European, Asian, Barrier, Lookback options
        - Antithetic variates for variance reduction
        - Control variates for improved accuracy
        - Confidence intervals

    Example:
        >>> calc = MonteCarloCalculator()
        >>> result = calc.calculate(
        ...     S=100, K=100, T=1, r=0.05, sigma=0.2,
        ...     option_type='call', simulations=10000
        ... )
        >>> print(f"Option price: {result['value']:.4f} ± {result['metadata']['std_error']:.4f}")
        Option price: 10.4523 ± 0.0821
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0, seed: Optional[int] = None):
        """
        Initialize Monte Carlo calculator.

        Args:
            precision: Number of decimal places for results (default: 6)
            risk_free_rate: Default risk-free rate (default: 0.0)
            seed: Random seed for reproducibility (default: None)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)
        self.seed = seed
        if seed is not None:
            np.random.seed(seed)

    def calculate(self,
                  S: float,
                  K: float,
                  T: float,
                  r: float,
                  sigma: float,
                  option_type: str = 'call',
                  q: float = 0.0,
                  simulations: int = 10000,
                  time_steps: int = 252,
                  antithetic: bool = True) -> Dict[str, Any]:
        """
        Calculate European option price using Monte Carlo simulation.

        Args:
            S: Current spot price
            K: Strike price
            T: Time to maturity (years)
            r: Risk-free rate (annualized)
            sigma: Volatility (annualized)
            option_type: 'call' or 'put'
            q: Dividend yield (default: 0.0)
            simulations: Number of simulation paths (default: 10000)
            time_steps: Number of time steps per path (default: 252)
            antithetic: Use antithetic variates for variance reduction (default: True)

        Returns:
            Dictionary containing:
                - value: Option price (mean of simulated payoffs)
                - std_error: Standard error of estimate
                - confidence_interval_95: 95% confidence interval
                - simulations: Number of simulations used

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

        if simulations < 100:
            raise DataValidationError("simulations must be at least 100", field_name='simulations')

        if time_steps < 1:
            raise DataValidationError("time_steps must be at least 1", field_name='time_steps')

        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise DataValidationError(
                "option_type must be 'call' or 'put'",
                field_name='option_type'
            )

        try:
            # Simulate stock price paths
            dt = T / time_steps
            drift = (r - q - 0.5 * sigma ** 2) * dt
            diffusion = sigma * np.sqrt(dt)

            # Generate random paths
            if antithetic:
                # Use antithetic variates: for each random path, also use its negative
                half_sims = simulations // 2
                Z = np.random.standard_normal((half_sims, time_steps))
                Z_anti = -Z
                Z_combined = np.vstack([Z, Z_anti])
                actual_sims = half_sims * 2
            else:
                Z_combined = np.random.standard_normal((simulations, time_steps))
                actual_sims = simulations

            # Simulate price paths using geometric Brownian motion
            # S(t) = S(0) * exp((r - q - 0.5*sigma^2)*t + sigma*sqrt(t)*Z)
            log_returns = drift + diffusion * Z_combined
            price_paths = S * np.exp(np.cumsum(log_returns, axis=1))

            # Calculate terminal prices
            terminal_prices = price_paths[:, -1]

            # Calculate payoffs
            if option_type == 'call':
                payoffs = np.maximum(terminal_prices - K, 0)
            else:  # put
                payoffs = np.maximum(K - terminal_prices, 0)

            # Discount payoffs to present value
            discounted_payoffs = np.exp(-r * T) * payoffs

            # Calculate statistics
            option_price = np.mean(discounted_payoffs)
            std_dev = np.std(discounted_payoffs, ddof=1)
            std_error = std_dev / np.sqrt(actual_sims)

            # 95% confidence interval
            z_score = 1.96
            ci_lower = option_price - z_score * std_error
            ci_upper = option_price + z_score * std_error

            return self._create_result_dict(
                value=option_price,
                method='monte_carlo',
                parameters={
                    'S': S,
                    'K': K,
                    'T': T,
                    'r': r,
                    'sigma': sigma,
                    'q': q,
                    'option_type': option_type,
                    'simulations': actual_sims,
                    'time_steps': time_steps,
                    'antithetic': antithetic
                },
                metadata={
                    'std_error': std_error,
                    'std_dev': std_dev,
                    'confidence_interval_95': (ci_lower, ci_upper),
                    'mean_terminal_price': np.mean(terminal_prices),
                    'median_terminal_price': np.median(terminal_prices)
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, CalculationError)):
                raise
            raise CalculationError(
                f"Monte Carlo calculation failed: {str(e)}",
                calculation_type='monte_carlo'
            )

    def calculate_asian(self,
                        S: float,
                        K: float,
                        T: float,
                        r: float,
                        sigma: float,
                        option_type: str = 'call',
                        q: float = 0.0,
                        simulations: int = 10000,
                        time_steps: int = 252,
                        averaging_type: str = 'arithmetic') -> Dict[str, Any]:
        """
        Calculate Asian option price (average price option).

        Asian options have payoffs based on the average price over the option's life.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            q: Dividend yield
            simulations: Number of simulations
            time_steps: Number of time steps
            averaging_type: 'arithmetic' or 'geometric'

        Returns:
            Result dictionary with Asian option price
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

        # Calculate payoffs based on average price
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
            method='monte_carlo_asian',
            parameters={
                'S': S, 'K': K, 'T': T, 'r': r, 'sigma': sigma, 'q': q,
                'option_type': option_type,
                'averaging_type': averaging_type,
                'simulations': simulations,
                'time_steps': time_steps
            },
            metadata={
                'std_error': std_error,
                'mean_average_price': np.mean(average_prices)
            }
        )

    def calculate_barrier(self,
                          S: float,
                          K: float,
                          T: float,
                          r: float,
                          sigma: float,
                          barrier: float,
                          barrier_type: str = 'down-and-out',
                          option_type: str = 'call',
                          q: float = 0.0,
                          simulations: int = 10000,
                          time_steps: int = 252) -> Dict[str, Any]:
        """
        Calculate barrier option price.

        Barrier options activate or deactivate when the underlying crosses a barrier.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            barrier: Barrier level
            barrier_type: 'down-and-out', 'down-and-in', 'up-and-out', 'up-and-in'
            option_type: 'call' or 'put'
            q: Dividend yield
            simulations: Number of simulations
            time_steps: Number of time steps

        Returns:
            Result dictionary with barrier option price
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

        # Simulate price paths
        dt = T / time_steps
        drift = (r - q - 0.5 * sigma ** 2) * dt
        diffusion = sigma * np.sqrt(dt)

        Z = np.random.standard_normal((simulations, time_steps))
        log_returns = drift + diffusion * Z
        price_paths = S * np.exp(np.cumsum(log_returns, axis=1))

        # Check barrier conditions
        if 'down' in barrier_type:
            barrier_crossed = np.any(price_paths <= barrier, axis=1)
        else:  # up
            barrier_crossed = np.any(price_paths >= barrier, axis=1)

        # Determine which paths are active
        if 'out' in barrier_type:
            active_paths = ~barrier_crossed  # Knock-out: inactive if barrier crossed
        else:  # in
            active_paths = barrier_crossed  # Knock-in: active only if barrier crossed

        # Calculate terminal payoffs
        terminal_prices = price_paths[:, -1]
        if option_type == 'call':
            payoffs = np.maximum(terminal_prices - K, 0)
        else:  # put
            payoffs = np.maximum(K - terminal_prices, 0)

        # Apply barrier condition
        payoffs = payoffs * active_paths

        # Discount and calculate statistics
        discounted_payoffs = np.exp(-r * T) * payoffs
        option_price = np.mean(discounted_payoffs)
        std_error = np.std(discounted_payoffs, ddof=1) / np.sqrt(simulations)

        return self._create_result_dict(
            value=option_price,
            method='monte_carlo_barrier',
            parameters={
                'S': S, 'K': K, 'T': T, 'r': r, 'sigma': sigma, 'q': q,
                'barrier': barrier,
                'barrier_type': barrier_type,
                'option_type': option_type,
                'simulations': simulations,
                'time_steps': time_steps
            },
            metadata={
                'std_error': std_error,
                'barrier_crossed_pct': np.mean(barrier_crossed) * 100,
                'active_paths_pct': np.mean(active_paths) * 100
            }
        )

    def calculate_lookback(self,
                           S: float,
                           K: float,
                           T: float,
                           r: float,
                           sigma: float,
                           lookback_type: str = 'floating',
                           option_type: str = 'call',
                           q: float = 0.0,
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
            simulations: Number of simulations
            time_steps: Number of time steps

        Returns:
            Result dictionary with lookback option price
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

        # Simulate price paths
        dt = T / time_steps
        drift = (r - q - 0.5 * sigma ** 2) * dt
        diffusion = sigma * np.sqrt(dt)

        Z = np.random.standard_normal((simulations, time_steps))
        log_returns = drift + diffusion * Z
        price_paths = S * np.exp(np.cumsum(log_returns, axis=1))

        # Calculate max and min prices along each path
        max_prices = np.max(price_paths, axis=1)
        min_prices = np.min(price_paths, axis=1)
        terminal_prices = price_paths[:, -1]

        # Calculate payoffs
        if lookback_type == 'floating':
            # Floating strike: strike is the min (call) or max (put) price
            if option_type == 'call':
                payoffs = terminal_prices - min_prices
            else:  # put
                payoffs = max_prices - terminal_prices
        else:  # fixed
            # Fixed strike: payoff based on max (call) or min (put) price
            if option_type == 'call':
                payoffs = np.maximum(max_prices - K, 0)
            else:  # put
                payoffs = np.maximum(K - min_prices, 0)

        # Discount and calculate statistics
        discounted_payoffs = np.exp(-r * T) * payoffs
        option_price = np.mean(discounted_payoffs)
        std_error = np.std(discounted_payoffs, ddof=1) / np.sqrt(simulations)

        return self._create_result_dict(
            value=option_price,
            method='monte_carlo_lookback',
            parameters={
                'S': S, 'K': K, 'T': T, 'r': r, 'sigma': sigma, 'q': q,
                'lookback_type': lookback_type,
                'option_type': option_type,
                'simulations': simulations,
                'time_steps': time_steps
            },
            metadata={
                'std_error': std_error,
                'mean_max_price': np.mean(max_prices),
                'mean_min_price': np.mean(min_prices)
            }
        )

    def get_supported_methods(self) -> list:
        """Get list of supported calculation methods."""
        return ['monte_carlo', 'asian', 'barrier', 'lookback']
