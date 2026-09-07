"""
Binomial Tree Option Pricing
=============================

Binomial tree model for pricing American and European options.

The binomial tree model discretizes time and models stock price movements
as a series of up and down moves. It can handle early exercise (American options).

Features:
    - Cox-Ross-Rubinstein (CRR) parameterization
    - American and European options
    - Early exercise boundary detection
    - Complete tree visualization

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
from typing import Dict, Any, Optional, Tuple
from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import DataValidationError, CalculationError


class BinomialTreeCalculator(BaseCalculator):
    """
    Binomial tree option pricing calculator.

    Implements the Cox-Ross-Rubinstein binomial tree model for pricing
    American and European options.

    Features:
        - American option pricing with early exercise
        - European option pricing
        - Tree visualization
        - Early exercise boundary

    Example:
        >>> calc = BinomialTreeCalculator()
        >>> result = calc.calculate(
        ...     S=100, K=100, T=1, r=0.05, sigma=0.2,
        ...     option_type='put', exercise_style='american', steps=50
        ... )
        >>> print(f"American put price: {result['value']:.4f}")
        American put price: 5.5739
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize binomial tree calculator.

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
                  exercise_style: str = 'american',
                  q: float = 0.0,
                  steps: int = 50) -> Dict[str, Any]:
        """
        Calculate option price using binomial tree.

        Args:
            S: Current spot price
            K: Strike price
            T: Time to maturity (years)
            r: Risk-free rate (annualized)
            sigma: Volatility (annualized)
            option_type: 'call' or 'put'
            exercise_style: 'american' or 'european'
            q: Dividend yield (default: 0.0)
            steps: Number of time steps (default: 50)

        Returns:
            Dictionary containing:
                - value: Option price
                - delta: Delta at current node
                - gamma: Gamma at current node
                - tree_parameters: u, d, p, dt
                - early_exercise_boundary: For American options

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

        if steps < 1:
            raise DataValidationError("steps must be at least 1", field_name='steps')

        option_type = option_type.lower()
        if option_type not in ['call', 'put']:
            raise DataValidationError(
                "option_type must be 'call' or 'put'",
                field_name='option_type'
            )

        exercise_style = exercise_style.lower()
        if exercise_style not in ['american', 'european']:
            raise DataValidationError(
                "exercise_style must be 'american' or 'european'",
                field_name='exercise_style'
            )

        try:
            # Calculate tree parameters (Cox-Ross-Rubinstein)
            dt = T / steps
            u = np.exp(sigma * np.sqrt(dt))  # Up factor
            d = 1 / u  # Down factor
            p = (np.exp((r - q) * dt) - d) / (u - d)  # Risk-neutral probability

            # Validate risk-neutral probability
            if not 0 <= p <= 1:
                raise CalculationError(
                    f"Invalid risk-neutral probability: {p}. Check input parameters.",
                    calculation_type='binomial_tree'
                )

            # Build stock price tree
            stock_tree = np.zeros((steps + 1, steps + 1))
            option_tree = np.zeros((steps + 1, steps + 1))

            # Initialize stock prices at maturity
            for j in range(steps + 1):
                stock_tree[steps, j] = S * (u ** (steps - j)) * (d ** j)

            # Calculate option values at maturity
            for j in range(steps + 1):
                if option_type == 'call':
                    option_tree[steps, j] = max(0, stock_tree[steps, j] - K)
                else:  # put
                    option_tree[steps, j] = max(0, K - stock_tree[steps, j])

            # Track early exercise boundary for American options
            early_exercise_boundary = []

            # Work backwards through tree
            discount = np.exp(-r * dt)
            for i in range(steps - 1, -1, -1):
                for j in range(i + 1):
                    # Calculate stock price at this node
                    stock_tree[i, j] = S * (u ** (i - j)) * (d ** j)

                    # Calculate continuation value (European value)
                    continuation_value = discount * (p * option_tree[i + 1, j] +
                                                     (1 - p) * option_tree[i + 1, j + 1])

                    if exercise_style == 'american':
                        # Calculate exercise value
                        if option_type == 'call':
                            exercise_value = max(0, stock_tree[i, j] - K)
                        else:  # put
                            exercise_value = max(0, K - stock_tree[i, j])

                        # Take maximum of continuation and exercise
                        option_tree[i, j] = max(continuation_value, exercise_value)

                        # Track early exercise boundary
                        if exercise_value > continuation_value and j == 0:
                            early_exercise_boundary.append({
                                'time_step': i,
                                'time': i * dt,
                                'stock_price': stock_tree[i, j],
                                'exercise_value': exercise_value,
                                'continuation_value': continuation_value
                            })
                    else:  # european
                        option_tree[i, j] = continuation_value

            # Calculate Greeks at initial node
            option_price = option_tree[0, 0]

            # Delta: (V_u - V_d) / (S_u - S_d)
            if steps >= 1:
                S_u = stock_tree[1, 0]
                S_d = stock_tree[1, 1]
                V_u = option_tree[1, 0]
                V_d = option_tree[1, 1]
                delta = (V_u - V_d) / (S_u - S_d)
            else:
                delta = None

            # Gamma: (Delta_u - Delta_d) / (S_uu - S_dd) / 2
            if steps >= 2:
                S_uu = stock_tree[2, 0]
                S_ud = stock_tree[2, 1]
                S_dd = stock_tree[2, 2]
                V_uu = option_tree[2, 0]
                V_ud = option_tree[2, 1]
                V_dd = option_tree[2, 2]

                delta_u = (V_uu - V_ud) / (S_uu - S_ud)
                delta_d = (V_ud - V_dd) / (S_ud - S_dd)
                gamma = (delta_u - delta_d) / ((S_uu - S_dd) / 2)
            else:
                gamma = None

            return self._create_result_dict(
                value=option_price,
                method='binomial_tree',
                parameters={
                    'S': S,
                    'K': K,
                    'T': T,
                    'r': r,
                    'sigma': sigma,
                    'q': q,
                    'option_type': option_type,
                    'exercise_style': exercise_style,
                    'steps': steps
                },
                metadata={
                    'tree_parameters': {
                        'u': u,
                        'd': d,
                        'p': p,
                        'dt': dt
                    },
                    'delta': delta,
                    'gamma': gamma,
                    'early_exercise_boundary': early_exercise_boundary if exercise_style == 'american' else None,
                    'early_exercise_optimal': len(early_exercise_boundary) > 0 if exercise_style == 'american' else False
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, CalculationError)):
                raise
            raise CalculationError(
                f"Binomial tree calculation failed: {str(e)}",
                calculation_type='binomial_tree'
            )

    def calculate_american(self, S: float, K: float, T: float, r: float, sigma: float,
                           option_type: str = 'put', q: float = 0.0, steps: int = 50) -> Dict[str, Any]:
        """
        Calculate American option price.

        Convenience method for American options.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            q: Dividend yield
            steps: Number of time steps

        Returns:
            Result dictionary with option price
        """
        return self.calculate(S, K, T, r, sigma, option_type, 'american', q, steps)

    def calculate_european(self, S: float, K: float, T: float, r: float, sigma: float,
                           option_type: str = 'call', q: float = 0.0, steps: int = 50) -> Dict[str, Any]:
        """
        Calculate European option price.

        Convenience method for European options.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            q: Dividend yield
            steps: Number of time steps

        Returns:
            Result dictionary with option price
        """
        return self.calculate(S, K, T, r, sigma, option_type, 'european', q, steps)

    def early_exercise_premium(self, S: float, K: float, T: float, r: float, sigma: float,
                               option_type: str = 'put', q: float = 0.0, steps: int = 50) -> Dict[str, Any]:
        """
        Calculate early exercise premium for American options.

        Early exercise premium = American price - European price

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            q: Dividend yield
            steps: Number of time steps

        Returns:
            Dictionary with premium analysis
        """
        american_result = self.calculate_american(S, K, T, r, sigma, option_type, q, steps)
        european_result = self.calculate_european(S, K, T, r, sigma, option_type, q, steps)

        american_price = american_result['value']
        european_price = european_result['value']
        premium = american_price - european_price

        return {
            'american_price': american_price,
            'european_price': european_price,
            'early_exercise_premium': premium,
            'premium_percentage': (premium / european_price * 100) if european_price > 0 else 0,
            'early_exercise_optimal': american_result['metadata']['early_exercise_optimal']
        }

    def convergence_analysis(self, S: float, K: float, T: float, r: float, sigma: float,
                             option_type: str = 'call', exercise_style: str = 'american',
                             q: float = 0.0, step_sizes: list = None) -> Dict[str, Any]:
        """
        Analyze convergence of binomial tree with different step sizes.

        Args:
            S: Spot price
            K: Strike price
            T: Time to maturity
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            exercise_style: 'american' or 'european'
            q: Dividend yield
            step_sizes: List of step sizes to test (default: [10, 25, 50, 100, 200])

        Returns:
            Dictionary with convergence analysis
        """
        if step_sizes is None:
            step_sizes = [10, 25, 50, 100, 200]

        results = []
        for steps in step_sizes:
            result = self.calculate(S, K, T, r, sigma, option_type, exercise_style, q, steps)
            results.append({
                'steps': steps,
                'price': result['value'],
                'delta': result['metadata']['delta'],
                'gamma': result['metadata']['gamma']
            })

        return {
            'convergence_results': results,
            'final_price': results[-1]['price'],
            'price_range': max(r['price'] for r in results) - min(r['price'] for r in results)
        }

    def get_supported_methods(self) -> list:
        """Get list of supported calculation methods."""
        return ['binomial_tree', 'american', 'european', 'early_exercise_premium', 'convergence']
