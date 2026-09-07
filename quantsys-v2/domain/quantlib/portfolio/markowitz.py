"""
Markowitz Mean-Variance Optimization
=====================================

Implementation of Markowitz portfolio optimization using mean-variance framework.

Optimization objectives:
    - Minimum variance portfolio
    - Maximum Sharpe ratio portfolio
    - Target return portfolio

References:
    - Markowitz, H. (1952). Portfolio Selection. Journal of Finance.

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Union, List, Tuple
from scipy.optimize import minimize
from scipy.linalg import sqrtm

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    DataValidationError,
    CalculationError,
    ConfigurationError,
    ConvergenceError
)


class MarkowitzOptimizer(BaseCalculator):
    """
    Markowitz Mean-Variance Portfolio Optimizer

    Implements classic Markowitz portfolio optimization with multiple objectives:
    - Minimize portfolio variance
    - Maximize Sharpe ratio
    - Achieve target return with minimum variance

    Mathematical formulation:
        min: w^T Σ w  (variance)
        s.t.: w^T μ = target_return (for target return objective)
              w^T 1 = 1 (weights sum to 1)
              w_i >= lower_bound (no short selling constraint)
              w_i <= upper_bound (position limits)

    Example:
        optimizer = MarkowitzOptimizer()
        result = optimizer.optimize(
            expected_returns=mu,
            cov_matrix=Sigma,
            objective='max_sharpe',
            risk_free_rate=0.02
        )
        print(f"Optimal weights: {result['value']['weights']}")
        print(f"Expected return: {result['value']['expected_return']}")
        print(f"Portfolio risk: {result['value']['risk']}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Markowitz optimizer.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Default risk-free rate for Sharpe ratio calculation
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def get_supported_methods(self) -> List[str]:
        """Get list of supported optimization objectives."""
        return ['min_variance', 'max_sharpe', 'target_return']

    def optimize(self,
                 expected_returns: Union[np.ndarray, pd.Series, List],
                 cov_matrix: Union[np.ndarray, pd.DataFrame],
                 objective: str = 'max_sharpe',
                 target_return: Optional[float] = None,
                 risk_free_rate: Optional[float] = None,
                 lower_bound: Union[float, np.ndarray] = 0.0,
                 upper_bound: Union[float, np.ndarray] = 1.0,
                 allow_short: bool = False) -> Dict[str, Any]:
        """
        Optimize portfolio weights using Markowitz framework.

        Args:
            expected_returns: Expected returns for each asset (n,)
            cov_matrix: Covariance matrix of returns (n, n)
            objective: Optimization objective ('min_variance', 'max_sharpe', 'target_return')
            target_return: Target return for 'target_return' objective
            risk_free_rate: Risk-free rate for Sharpe ratio (uses default if None)
            lower_bound: Lower bound for weights (scalar or array)
            upper_bound: Upper bound for weights (scalar or array)
            allow_short: Allow short selling (negative weights)

        Returns:
            Dictionary containing:
                - weights: Optimal portfolio weights
                - expected_return: Expected portfolio return
                - risk: Portfolio standard deviation
                - sharpe_ratio: Sharpe ratio
                - objective_value: Value of optimization objective

        Raises:
            DataValidationError: If input data is invalid
            ConfigurationError: If parameters are invalid
            ConvergenceError: If optimization fails to converge
        """
        # Validate objective
        objective = self.validate_method(objective)

        # Validate and convert inputs
        mu = self._validate_expected_returns(expected_returns)
        Sigma = self._validate_covariance_matrix(cov_matrix, len(mu))

        # Validate target return for target_return objective
        if objective == 'target_return':
            if target_return is None:
                raise ConfigurationError(
                    "target_return must be specified for 'target_return' objective",
                    parameter='target_return'
                )
            target_return = self._validate_numeric_input(target_return, 'target_return')

        # Set risk-free rate
        rf = risk_free_rate if risk_free_rate is not None else self.risk_free_rate

        # Validate bounds
        lower_bound, upper_bound = self._validate_bounds(
            lower_bound, upper_bound, len(mu), allow_short
        )

        # Perform optimization
        try:
            if objective == 'min_variance':
                weights = self._optimize_min_variance(Sigma, lower_bound, upper_bound)
            elif objective == 'max_sharpe':
                weights = self._optimize_max_sharpe(mu, Sigma, rf, lower_bound, upper_bound)
            elif objective == 'target_return':
                weights = self._optimize_target_return(
                    mu, Sigma, target_return, lower_bound, upper_bound
                )
            else:
                raise ConfigurationError(f"Unknown objective: {objective}", parameter='objective')

        except Exception as e:
            if isinstance(e, (DataValidationError, ConfigurationError, ConvergenceError)):
                raise
            raise ConvergenceError(f"Optimization failed: {str(e)}")

        # Calculate portfolio metrics
        portfolio_return = np.dot(weights, mu)
        portfolio_variance = np.dot(weights, np.dot(Sigma, weights))
        portfolio_risk = np.sqrt(portfolio_variance)
        sharpe_ratio = (portfolio_return - rf) / portfolio_risk if portfolio_risk > 0 else 0.0

        # Calculate objective value
        if objective == 'min_variance':
            objective_value = portfolio_variance
        elif objective == 'max_sharpe':
            objective_value = sharpe_ratio
        else:  # target_return
            objective_value = portfolio_variance

        result_value = {
            'weights': weights,
            'expected_return': portfolio_return,
            'risk': portfolio_risk,
            'variance': portfolio_variance,
            'sharpe_ratio': sharpe_ratio,
            'objective_value': objective_value
        }

        parameters = {
            'objective': objective,
            'target_return': target_return,
            'risk_free_rate': rf,
            'allow_short': allow_short,
            'n_assets': len(mu)
        }

        metadata = {
            'weights_sum': np.sum(weights),
            'min_weight': np.min(weights),
            'max_weight': np.max(weights),
            'n_nonzero': np.sum(np.abs(weights) > 1e-6)
        }

        return self._create_result_dict(
            value=result_value,
            method=f'markowitz_{objective}',
            parameters=parameters,
            metadata=metadata
        )

    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        """Alias for optimize method to satisfy BaseCalculator interface."""
        return self.optimize(*args, **kwargs)

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
        """Validate and convert covariance matrix."""
        if isinstance(cov, pd.DataFrame):
            cov = cov.values

        cov = np.asarray(cov, dtype=float)

        if cov.ndim != 2:
            raise DataValidationError(
                f"cov_matrix must be 2-dimensional, got shape {cov.shape}",
                field_name='cov_matrix'
            )

        if cov.shape[0] != cov.shape[1]:
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

        # Check positive semi-definite
        eigenvalues = np.linalg.eigvalsh(cov)
        if np.any(eigenvalues < -1e-8):
            raise DataValidationError(
                "cov_matrix must be positive semi-definite",
                field_name='cov_matrix'
            )

        # Add small regularization if needed
        if np.min(eigenvalues) < 1e-10:
            cov = cov + np.eye(n_assets) * 1e-8

        return cov

    def _validate_bounds(self,
                        lower: Union[float, np.ndarray],
                        upper: Union[float, np.ndarray],
                        n_assets: int,
                        allow_short: bool) -> Tuple[np.ndarray, np.ndarray]:
        """Validate and convert bounds to arrays."""
        # Convert to arrays
        if isinstance(lower, (int, float)):
            lower_bound = np.full(n_assets, lower, dtype=float)
        else:
            lower_bound = np.asarray(lower, dtype=float)

        if isinstance(upper, (int, float)):
            upper_bound = np.full(n_assets, upper, dtype=float)
        else:
            upper_bound = np.asarray(upper, dtype=float)

        # Validate shapes
        if lower_bound.shape != (n_assets,):
            raise DataValidationError(
                f"lower_bound must have shape ({n_assets},), got {lower_bound.shape}",
                field_name='lower_bound'
            )

        if upper_bound.shape != (n_assets,):
            raise DataValidationError(
                f"upper_bound must have shape ({n_assets},), got {upper_bound.shape}",
                field_name='upper_bound'
            )

        # Validate bounds
        if not allow_short and np.any(lower_bound < 0):
            raise ConfigurationError(
                "lower_bound cannot be negative when allow_short=False",
                parameter='lower_bound'
            )

        if np.any(lower_bound > upper_bound):
            raise ConfigurationError(
                "lower_bound must be <= upper_bound for all assets",
                parameter='bounds'
            )

        return lower_bound, upper_bound

    def _optimize_min_variance(self,
                               Sigma: np.ndarray,
                               lower_bound: np.ndarray,
                               upper_bound: np.ndarray) -> np.ndarray:
        """Optimize for minimum variance portfolio."""
        n_assets = Sigma.shape[0]

        # Objective: minimize variance = w^T Σ w
        def objective(w):
            return np.dot(w, np.dot(Sigma, w))

        # Gradient
        def gradient(w):
            return 2 * np.dot(Sigma, w)

        # Constraints: weights sum to 1
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}
        ]

        # Bounds
        bounds = [(lower_bound[i], upper_bound[i]) for i in range(n_assets)]

        # Initial guess: equal weights
        w0 = np.ones(n_assets) / n_assets

        # Optimize
        result = minimize(
            objective,
            w0,
            method='SLSQP',
            jac=gradient,
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000, 'ftol': 1e-9}
        )

        if not result.success:
            raise ConvergenceError(f"Optimization failed: {result.message}")

        return result.x

    def _optimize_max_sharpe(self,
                            mu: np.ndarray,
                            Sigma: np.ndarray,
                            rf: float,
                            lower_bound: np.ndarray,
                            upper_bound: np.ndarray) -> np.ndarray:
        """Optimize for maximum Sharpe ratio portfolio."""
        n_assets = len(mu)

        # Objective: minimize negative Sharpe ratio
        def objective(w):
            portfolio_return = np.dot(w, mu)
            portfolio_variance = np.dot(w, np.dot(Sigma, w))
            portfolio_risk = np.sqrt(portfolio_variance)

            if portfolio_risk < 1e-10:
                return 1e10  # Penalize zero risk

            sharpe = (portfolio_return - rf) / portfolio_risk
            return -sharpe  # Minimize negative Sharpe

        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}
        ]

        # Bounds
        bounds = [(lower_bound[i], upper_bound[i]) for i in range(n_assets)]

        # Initial guess: equal weights
        w0 = np.ones(n_assets) / n_assets

        # Optimize
        result = minimize(
            objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000, 'ftol': 1e-9}
        )

        if not result.success:
            raise ConvergenceError(f"Optimization failed: {result.message}")

        return result.x

    def _optimize_target_return(self,
                                mu: np.ndarray,
                                Sigma: np.ndarray,
                                target_return: float,
                                lower_bound: np.ndarray,
                                upper_bound: np.ndarray) -> np.ndarray:
        """Optimize for target return with minimum variance."""
        n_assets = len(mu)

        # Check if target return is achievable
        max_return = np.max(mu)
        min_return = np.min(mu)

        if target_return > max_return:
            raise ConfigurationError(
                f"target_return {target_return} exceeds maximum achievable return {max_return}",
                parameter='target_return'
            )

        if target_return < min_return:
            raise ConfigurationError(
                f"target_return {target_return} is below minimum return {min_return}",
                parameter='target_return'
            )

        # Objective: minimize variance
        def objective(w):
            return np.dot(w, np.dot(Sigma, w))

        # Gradient
        def gradient(w):
            return 2 * np.dot(Sigma, w)

        # Constraints: weights sum to 1, return equals target
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0},
            {'type': 'eq', 'fun': lambda w: np.dot(w, mu) - target_return}
        ]

        # Bounds
        bounds = [(lower_bound[i], upper_bound[i]) for i in range(n_assets)]

        # Initial guess: equal weights
        w0 = np.ones(n_assets) / n_assets

        # Optimize
        result = minimize(
            objective,
            w0,
            method='SLSQP',
            jac=gradient,
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000, 'ftol': 1e-9}
        )

        if not result.success:
            raise ConvergenceError(f"Optimization failed: {result.message}")

        return result.x
