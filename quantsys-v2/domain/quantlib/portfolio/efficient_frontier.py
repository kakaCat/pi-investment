"""
Efficient Frontier Calculator
==============================

Calculates and analyzes the efficient frontier for portfolio optimization.

The efficient frontier represents the set of optimal portfolios that offer
the highest expected return for a given level of risk.

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Union, List, Tuple

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    DataValidationError,
    CalculationError,
    ConfigurationError
)


class EfficientFrontierCalculator(BaseCalculator):
    """
    Efficient Frontier Calculator

    Calculates the efficient frontier curve and identifies key portfolios:
    - Minimum variance portfolio
    - Maximum Sharpe ratio portfolio
    - Capital Market Line (CML)

    Example:
        calculator = EfficientFrontierCalculator()
        result = calculator.calculate(
            expected_returns=mu,
            cov_matrix=Sigma,
            risk_free_rate=0.02,
            n_points=50
        )

        # Access frontier points
        frontier = result['value']['frontier']
        for point in frontier:
            print(f"Return: {point['return']:.4f}, Risk: {point['risk']:.4f}")

        # Get optimal portfolios
        min_var = result['value']['min_variance_portfolio']
        max_sharpe = result['value']['max_sharpe_portfolio']
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize efficient frontier calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Default risk-free rate
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  expected_returns: Union[np.ndarray, pd.Series, List],
                  cov_matrix: Union[np.ndarray, pd.DataFrame],
                  risk_free_rate: Optional[float] = None,
                  n_points: int = 50,
                  lower_bound: Union[float, np.ndarray] = 0.0,
                  upper_bound: Union[float, np.ndarray] = 1.0,
                  allow_short: bool = False) -> Dict[str, Any]:
        """
        Calculate efficient frontier and optimal portfolios.

        Args:
            expected_returns: Expected returns for each asset (n,)
            cov_matrix: Covariance matrix of returns (n, n)
            risk_free_rate: Risk-free rate for Sharpe ratio and CML
            n_points: Number of points to calculate on the frontier
            lower_bound: Lower bound for weights (scalar or array)
            upper_bound: Upper bound for weights (scalar or array)
            allow_short: Allow short selling (negative weights)

        Returns:
            Dictionary containing:
                - frontier: List of frontier points with returns, risks, and weights
                - min_variance_portfolio: Minimum variance portfolio
                - max_sharpe_portfolio: Maximum Sharpe ratio portfolio
                - cml_slope: Slope of Capital Market Line
                - cml_intercept: Intercept of Capital Market Line

        Raises:
            DataValidationError: If input data is invalid
            ConfigurationError: If parameters are invalid
        """
        # Import here to avoid circular dependency
        from .markowitz import MarkowitzOptimizer

        # Validate inputs
        mu = self._validate_expected_returns(expected_returns)
        Sigma = self._validate_covariance_matrix(cov_matrix, len(mu))

        if n_points < 2:
            raise ConfigurationError(
                f"n_points must be at least 2, got {n_points}",
                parameter='n_points'
            )

        rf = risk_free_rate if risk_free_rate is not None else self.risk_free_rate

        # Create optimizer
        optimizer = MarkowitzOptimizer(precision=self.precision, risk_free_rate=rf)

        # Step 1: Find minimum variance portfolio
        min_var_result = optimizer.optimize(
            expected_returns=mu,
            cov_matrix=Sigma,
            objective='min_variance',
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            allow_short=allow_short
        )

        min_var_portfolio = {
            'weights': min_var_result['value']['weights'],
            'return': min_var_result['value']['expected_return'],
            'risk': min_var_result['value']['risk'],
            'sharpe_ratio': min_var_result['value']['sharpe_ratio']
        }

        # Step 2: Find maximum Sharpe ratio portfolio
        max_sharpe_result = optimizer.optimize(
            expected_returns=mu,
            cov_matrix=Sigma,
            objective='max_sharpe',
            risk_free_rate=rf,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            allow_short=allow_short
        )

        max_sharpe_portfolio = {
            'weights': max_sharpe_result['value']['weights'],
            'return': max_sharpe_result['value']['expected_return'],
            'risk': max_sharpe_result['value']['risk'],
            'sharpe_ratio': max_sharpe_result['value']['sharpe_ratio']
        }

        # Step 3: Calculate frontier points
        # Generate target returns from min variance return to max return
        min_return = min_var_portfolio['return']
        max_return = np.max(mu)

        # Ensure we have a valid range
        if max_return <= min_return:
            max_return = min_return * 1.5

        target_returns = np.linspace(min_return, max_return, n_points)

        frontier = []
        for target_ret in target_returns:
            try:
                result = optimizer.optimize(
                    expected_returns=mu,
                    cov_matrix=Sigma,
                    objective='target_return',
                    target_return=target_ret,
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    allow_short=allow_short
                )

                frontier.append({
                    'return': result['value']['expected_return'],
                    'risk': result['value']['risk'],
                    'weights': result['value']['weights'],
                    'sharpe_ratio': result['value']['sharpe_ratio']
                })
            except Exception as e:
                # Skip points that fail to optimize
                self.logger.warning(f"Failed to optimize for target return {target_ret}: {str(e)}")
                continue

        if len(frontier) == 0:
            raise CalculationError(
                "Failed to calculate any frontier points",
                calculation_type='efficient_frontier'
            )

        # Step 4: Calculate Capital Market Line (CML)
        # CML: E[R] = R_f + (E[R_m] - R_f) / σ_m * σ
        # Slope = Sharpe ratio of tangency portfolio (max Sharpe portfolio)
        cml_slope = max_sharpe_portfolio['sharpe_ratio']
        cml_intercept = rf

        result_value = {
            'frontier': frontier,
            'min_variance_portfolio': min_var_portfolio,
            'max_sharpe_portfolio': max_sharpe_portfolio,
            'cml_slope': cml_slope,
            'cml_intercept': cml_intercept
        }

        parameters = {
            'n_points': len(frontier),
            'risk_free_rate': rf,
            'allow_short': allow_short,
            'n_assets': len(mu)
        }

        metadata = {
            'min_return': min_return,
            'max_return': max_return,
            'min_risk': min_var_portfolio['risk'],
            'max_sharpe_value': max_sharpe_portfolio['sharpe_ratio']
        }

        return self._create_result_dict(
            value=result_value,
            method='efficient_frontier',
            parameters=parameters,
            metadata=metadata
        )

    def calculate_cml_portfolio(self,
                               expected_returns: Union[np.ndarray, pd.Series, List],
                               cov_matrix: Union[np.ndarray, pd.DataFrame],
                               target_risk: float,
                               risk_free_rate: Optional[float] = None) -> Dict[str, Any]:
        """
        Calculate portfolio on the Capital Market Line for a given target risk.

        The CML represents portfolios that combine the risk-free asset with
        the tangency portfolio (maximum Sharpe ratio portfolio).

        Args:
            expected_returns: Expected returns for each asset (n,)
            cov_matrix: Covariance matrix of returns (n, n)
            target_risk: Target portfolio risk (standard deviation)
            risk_free_rate: Risk-free rate

        Returns:
            Dictionary containing portfolio weights and metrics
        """
        from .markowitz import MarkowitzOptimizer

        # Validate inputs
        mu = self._validate_expected_returns(expected_returns)
        Sigma = self._validate_covariance_matrix(cov_matrix, len(mu))
        target_risk = self._validate_positive(target_risk, 'target_risk')

        rf = risk_free_rate if risk_free_rate is not None else self.risk_free_rate

        # Find tangency portfolio (max Sharpe)
        optimizer = MarkowitzOptimizer(precision=self.precision, risk_free_rate=rf)
        tangency_result = optimizer.optimize(
            expected_returns=mu,
            cov_matrix=Sigma,
            objective='max_sharpe',
            risk_free_rate=rf
        )

        tangency_weights = tangency_result['value']['weights']
        tangency_return = tangency_result['value']['expected_return']
        tangency_risk = tangency_result['value']['risk']

        # Calculate allocation to tangency portfolio
        # σ_target = α * σ_tangency
        # α = σ_target / σ_tangency
        alpha = target_risk / tangency_risk

        # Portfolio weights: α * tangency + (1-α) * risk_free
        portfolio_weights = alpha * tangency_weights
        risk_free_weight = 1 - alpha

        # Portfolio return: α * R_tangency + (1-α) * R_f
        portfolio_return = alpha * tangency_return + (1 - alpha) * rf

        # Sharpe ratio (same as tangency portfolio)
        sharpe_ratio = (portfolio_return - rf) / target_risk if target_risk > 0 else 0.0

        result_value = {
            'weights': portfolio_weights,
            'risk_free_weight': risk_free_weight,
            'expected_return': portfolio_return,
            'risk': target_risk,
            'sharpe_ratio': sharpe_ratio,
            'leverage': alpha
        }

        parameters = {
            'target_risk': target_risk,
            'risk_free_rate': rf,
            'tangency_risk': tangency_risk,
            'tangency_return': tangency_return
        }

        metadata = {
            'on_cml': True,
            'leveraged': alpha > 1.0,
            'conservative': alpha < 1.0
        }

        return self._create_result_dict(
            value=result_value,
            method='cml_portfolio',
            parameters=parameters,
            metadata=metadata
        )

    def _validate_expected_returns(self, returns: Union[np.ndarray, pd.Series, List]) -> np.ndarray:
        """Validate and convert expected returns to numpy array."""
        mu = self._validate_numeric_input(returns, 'expected_returns')

        if isinstance(mu, (int, float)):
            raise DataValidationError(
                "expected_returns must be an array, not a scalar",
                field_name='expected_returns'
            )

        if isinstance(mu, pd.Series):
            mu = mu.values

        mu = np.asarray(mu, dtype=float)

        if mu.ndim != 1:
            raise DataValidationError(
                f"expected_returns must be 1-dimensional, got shape {mu.shape}",
                field_name='expected_returns'
            )

        if len(mu) < 2:
            raise DataValidationError(
                f"Need at least 2 assets, got {len(mu)}",
                field_name='expected_returns'
            )

        return mu

    def _validate_covariance_matrix(self, cov: Union[np.ndarray, pd.DataFrame], n_assets: int) -> np.ndarray:
        """Validate covariance matrix."""
        if isinstance(cov, pd.DataFrame):
            cov = cov.values

        cov = np.asarray(cov, dtype=float)

        if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
            raise DataValidationError(
                f"cov_matrix must be square, got shape {cov.shape}",
                field_name='cov_matrix'
            )

        if cov.shape[0] != n_assets:
            raise DataValidationError(
                f"cov_matrix dimension {cov.shape[0]} does not match number of assets {n_assets}",
                field_name='cov_matrix'
            )

        # Check symmetry
        if not np.allclose(cov, cov.T):
            raise DataValidationError(
                "cov_matrix must be symmetric",
                field_name='cov_matrix'
            )

        # Check positive definite
        eigenvalues = np.linalg.eigvalsh(cov)
        if np.any(eigenvalues < -1e-8):
            raise DataValidationError(
                "cov_matrix must be positive semi-definite",
                field_name='cov_matrix'
            )

        # Add regularization if needed
        if np.min(eigenvalues) < 1e-10:
            cov = cov + np.eye(n_assets) * 1e-8

        return cov
