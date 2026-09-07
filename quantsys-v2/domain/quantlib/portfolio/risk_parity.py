"""
Risk Parity Portfolio Optimization
===================================

Implementation of risk parity (equal risk contribution) portfolio optimization.

Risk parity allocates capital such that each asset contributes equally to
portfolio risk, rather than equal capital allocation.

References:
    - Maillard, S., Roncalli, T., & Teïletche, J. (2010). The Properties of Equally Weighted Risk Contribution Portfolios.

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Union, List, Tuple
from scipy.optimize import minimize

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    DataValidationError,
    CalculationError,
    ConfigurationError,
    ConvergenceError
)


class RiskParityOptimizer(BaseCalculator):
    """
    Risk Parity Portfolio Optimizer

    Optimizes portfolio to achieve equal risk contribution from each asset.

    Mathematical formulation:
        Risk contribution of asset i: RC_i = w_i * (∂σ_p/∂w_i) = w_i * (Σw)_i / σ_p

        Objective: Minimize sum of squared deviations from target risk contributions
            min: Σ(RC_i - target_i)²

    For equal risk parity: target_i = 1/n for all i

    Example:
        optimizer = RiskParityOptimizer()

        # Equal risk contribution
        result = optimizer.optimize(cov_matrix=Sigma)
        print(f"Weights: {result['value']['weights']}")
        print(f"Risk contributions: {result['value']['risk_contributions']}")

        # Custom target risk contributions
        result = optimizer.optimize(
            cov_matrix=Sigma,
            target_risk=np.array([0.4, 0.3, 0.3])
        )
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize risk parity optimizer.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate (not used but kept for consistency)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def optimize(self,
                 cov_matrix: Union[np.ndarray, pd.DataFrame],
                 target_risk: Optional[Union[np.ndarray, List]] = None,
                 target_volatility: Optional[float] = None,
                 lower_bound: Union[float, np.ndarray] = 0.0,
                 upper_bound: Union[float, np.ndarray] = 1.0) -> Dict[str, Any]:
        """
        Optimize portfolio for risk parity.

        Args:
            cov_matrix: Covariance matrix of returns (n, n)
            target_risk: Target risk contribution for each asset (n,)
                        If None, uses equal risk contribution (1/n for each)
            target_volatility: Target portfolio volatility (applies leverage if specified)
            lower_bound: Lower bound for weights (scalar or array)
            upper_bound: Upper bound for weights (scalar or array)

        Returns:
            Dictionary containing:
                - weights: Optimal portfolio weights
                - risk_contributions: Risk contribution of each asset
                - marginal_risk_contributions: Marginal risk contribution (MRC)
                - portfolio_volatility: Portfolio standard deviation
                - leverage: Leverage ratio (if target_volatility specified)

        Raises:
            DataValidationError: If input data is invalid
            ConfigurationError: If parameters are invalid
            ConvergenceError: If optimization fails to converge
        """
        # Validate covariance matrix
        Sigma = self._validate_covariance_matrix(cov_matrix)
        n_assets = Sigma.shape[0]

        # Validate target risk contributions
        if target_risk is None:
            # Equal risk contribution
            target_risk_contrib = np.ones(n_assets) / n_assets
        else:
            target_risk_contrib = self._validate_target_risk(target_risk, n_assets)

        # Validate bounds
        lower_bound, upper_bound = self._validate_bounds(lower_bound, upper_bound, n_assets)

        # Optimize for risk parity
        try:
            weights = self._optimize_risk_parity(Sigma, target_risk_contrib, lower_bound, upper_bound)
        except Exception as e:
            if isinstance(e, (DataValidationError, ConfigurationError, ConvergenceError)):
                raise
            raise ConvergenceError(f"Risk parity optimization failed: {str(e)}")

        # Calculate risk contributions
        portfolio_volatility = np.sqrt(np.dot(weights, np.dot(Sigma, weights)))
        mrc = np.dot(Sigma, weights) / portfolio_volatility  # Marginal risk contribution
        risk_contributions = weights * mrc / portfolio_volatility  # Percentage risk contribution

        # Apply leverage if target volatility specified
        leverage = 1.0
        if target_volatility is not None:
            target_volatility = self._validate_positive(target_volatility, 'target_volatility')
            leverage = target_volatility / portfolio_volatility
            weights = weights * leverage
            portfolio_volatility = target_volatility

        result_value = {
            'weights': weights,
            'risk_contributions': risk_contributions,
            'marginal_risk_contributions': mrc,
            'portfolio_volatility': portfolio_volatility,
            'leverage': leverage
        }

        parameters = {
            'n_assets': n_assets,
            'target_volatility': target_volatility,
            'equal_risk': target_risk is None
        }

        metadata = {
            'weights_sum': np.sum(weights),
            'risk_contrib_sum': np.sum(risk_contributions),
            'risk_contrib_std': np.std(risk_contributions),
            'max_deviation': np.max(np.abs(risk_contributions - target_risk_contrib))
        }

        return self._create_result_dict(
            value=result_value,
            method='risk_parity',
            parameters=parameters,
            metadata=metadata
        )

    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        """Alias for optimize method to satisfy BaseCalculator interface."""
        return self.optimize(*args, **kwargs)

    def _validate_covariance_matrix(self, cov: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Validate covariance matrix."""
        if isinstance(cov, pd.DataFrame):
            cov = cov.values

        cov = np.asarray(cov, dtype=float)

        if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
            raise DataValidationError(
                f"cov_matrix must be square, got shape {cov.shape}",
                field_name='cov_matrix'
            )

        if cov.shape[0] < 2:
            raise DataValidationError(
                f"Need at least 2 assets, got {cov.shape[0]}",
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
            n = cov.shape[0]
            cov = cov + np.eye(n) * 1e-8

        return cov

    def _validate_target_risk(self, target: Union[np.ndarray, List], n_assets: int) -> np.ndarray:
        """Validate target risk contributions."""
        target_risk = self._validate_numeric_input(target, 'target_risk')

        if isinstance(target_risk, (int, float)):
            raise DataValidationError(
                "target_risk must be an array, not a scalar",
                field_name='target_risk'
            )

        if isinstance(target_risk, pd.Series):
            target_risk = target_risk.values

        target_risk = np.asarray(target_risk, dtype=float)

        if target_risk.shape != (n_assets,):
            raise DataValidationError(
                f"target_risk must have shape ({n_assets},), got {target_risk.shape}",
                field_name='target_risk'
            )

        # Check non-negative
        if np.any(target_risk < 0):
            raise DataValidationError(
                "target_risk must be non-negative",
                field_name='target_risk'
            )

        # Normalize to sum to 1
        risk_sum = np.sum(target_risk)
        if risk_sum <= 0:
            raise DataValidationError(
                "target_risk must sum to positive value",
                field_name='target_risk'
            )

        target_risk = target_risk / risk_sum

        return target_risk

    def _validate_bounds(self,
                        lower: Union[float, np.ndarray],
                        upper: Union[float, np.ndarray],
                        n_assets: int) -> Tuple[np.ndarray, np.ndarray]:
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
        if np.any(lower_bound < 0):
            raise ConfigurationError(
                "lower_bound cannot be negative for risk parity",
                parameter='lower_bound'
            )

        if np.any(lower_bound > upper_bound):
            raise ConfigurationError(
                "lower_bound must be <= upper_bound for all assets",
                parameter='bounds'
            )

        return lower_bound, upper_bound

    def _optimize_risk_parity(self,
                             Sigma: np.ndarray,
                             target_risk: np.ndarray,
                             lower_bound: np.ndarray,
                             upper_bound: np.ndarray) -> np.ndarray:
        """
        Optimize for risk parity portfolio.

        Minimizes the sum of squared deviations from target risk contributions.
        """
        n_assets = Sigma.shape[0]

        # Objective: minimize sum of squared deviations from target risk
        def objective(w):
            # Portfolio volatility
            portfolio_var = np.dot(w, np.dot(Sigma, w))
            portfolio_vol = np.sqrt(portfolio_var)

            if portfolio_vol < 1e-10:
                return 1e10  # Penalize zero volatility

            # Marginal risk contributions
            mrc = np.dot(Sigma, w)

            # Risk contributions (as percentage)
            risk_contrib = w * mrc / portfolio_var

            # Sum of squared deviations from target
            deviations = risk_contrib - target_risk
            return np.sum(deviations ** 2)

        # Gradient (numerical approximation is used by scipy)
        # We could provide analytical gradient but numerical is sufficient

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
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000, 'ftol': 1e-9}
        )

        if not result.success:
            raise ConvergenceError(f"Risk parity optimization failed: {result.message}")

        return result.x

    def calculate_risk_decomposition(self,
                                    weights: Union[np.ndarray, List],
                                    cov_matrix: Union[np.ndarray, pd.DataFrame]) -> Dict[str, Any]:
        """
        Calculate risk decomposition for a given portfolio.

        Args:
            weights: Portfolio weights (n,)
            cov_matrix: Covariance matrix (n, n)

        Returns:
            Dictionary containing risk decomposition metrics
        """
        # Validate inputs
        w = self._validate_numeric_input(weights, 'weights')
        if isinstance(w, pd.Series):
            w = w.values
        w = np.asarray(w, dtype=float)

        Sigma = self._validate_covariance_matrix(cov_matrix)

        if len(w) != Sigma.shape[0]:
            raise DataValidationError(
                f"weights length {len(w)} does not match cov_matrix dimension {Sigma.shape[0]}",
                field_name='weights'
            )

        # Calculate risk metrics
        portfolio_var = np.dot(w, np.dot(Sigma, w))
        portfolio_vol = np.sqrt(portfolio_var)

        # Marginal risk contributions
        mrc = np.dot(Sigma, w) / portfolio_vol

        # Component risk contributions (absolute)
        crc = w * mrc

        # Percentage risk contributions
        prc = crc / portfolio_vol

        result = {
            'portfolio_volatility': portfolio_vol,
            'marginal_risk_contributions': mrc,
            'component_risk_contributions': crc,
            'percentage_risk_contributions': prc,
            'risk_contribution_sum': np.sum(prc)
        }

        return self._create_result_dict(
            value=result,
            method='risk_decomposition',
            parameters={'n_assets': len(w)},
            metadata={'weights_sum': np.sum(w)}
        )
