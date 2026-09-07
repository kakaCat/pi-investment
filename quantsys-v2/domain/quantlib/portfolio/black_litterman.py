"""
Black-Litterman Portfolio Optimization
=======================================

Implementation of Black-Litterman model for portfolio optimization with subjective views.

The Black-Litterman model combines market equilibrium with investor views using
Bayesian updating to produce posterior expected returns.

References:
    - Black, F., & Litterman, R. (1992). Global Portfolio Optimization.
    - He, G., & Litterman, R. (1999). The Intuition Behind Black-Litterman Model Portfolios.

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


class BlackLittermanOptimizer(BaseCalculator):
    """
    Black-Litterman Portfolio Optimizer

    Combines market equilibrium returns with subjective views using Bayesian updating.

    Model:
        Posterior returns: E[R] = [(τΣ)^-1 + P^T Ω^-1 P]^-1 [(τΣ)^-1 Π + P^T Ω^-1 Q]

    Where:
        - Π: Market equilibrium returns (implied from market weights)
        - Σ: Covariance matrix of returns
        - P: View picking matrix (links views to assets)
        - Q: View expected returns
        - Ω: Uncertainty in views (diagonal matrix)
        - τ: Scaling factor for uncertainty in equilibrium (typically 0.01-0.05)

    Example:
        optimizer = BlackLittermanOptimizer()

        # Define views
        views = [
            {'assets': [0, 1], 'return': 0.05, 'confidence': 0.5},  # Relative view
            {'assets': [2], 'return': 0.03, 'confidence': 0.8}      # Absolute view
        ]

        result = optimizer.optimize(
            market_weights=w_mkt,
            cov_matrix=Sigma,
            views=views,
            risk_aversion=2.5
        )
        print(f"Posterior returns: {result['value']['posterior_returns']}")
        print(f"Optimal weights: {result['value']['weights']}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Black-Litterman optimizer.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate for calculations
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def optimize(self,
                 market_weights: Union[np.ndarray, pd.Series, List],
                 cov_matrix: Union[np.ndarray, pd.DataFrame],
                 views: Optional[List[Dict[str, Any]]] = None,
                 risk_aversion: float = 2.5,
                 tau: float = 0.025,
                 risk_free_rate: Optional[float] = None) -> Dict[str, Any]:
        """
        Optimize portfolio using Black-Litterman model.

        Args:
            market_weights: Market capitalization weights (n,)
            cov_matrix: Covariance matrix of returns (n, n)
            views: List of view dictionaries with keys:
                   - 'assets': List of asset indices (relative view) or single index (absolute)
                   - 'return': Expected return for the view
                   - 'confidence': Confidence level (0-1), higher = more confident
            risk_aversion: Market risk aversion parameter (typically 2-4)
            tau: Uncertainty scaling factor (typically 0.01-0.05)
            risk_free_rate: Risk-free rate (uses default if None)

        Returns:
            Dictionary containing:
                - posterior_returns: Posterior expected returns
                - posterior_cov: Posterior covariance matrix
                - weights: Optimal portfolio weights
                - equilibrium_returns: Market equilibrium returns (prior)
                - expected_return: Expected portfolio return
                - risk: Portfolio standard deviation

        Raises:
            DataValidationError: If input data is invalid
            ConfigurationError: If parameters are invalid
        """
        # Validate inputs
        w_mkt = self._validate_weights(market_weights)
        Sigma = self._validate_covariance_matrix(cov_matrix, len(w_mkt))

        # Validate parameters
        risk_aversion = self._validate_positive(risk_aversion, 'risk_aversion')
        tau = self._validate_positive(tau, 'tau')

        if tau > 0.1:
            self.logger.warning(f"tau={tau} is unusually large (typically 0.01-0.05)")

        rf = risk_free_rate if risk_free_rate is not None else self.risk_free_rate

        # Step 1: Calculate market equilibrium returns (reverse optimization)
        Pi = self._calculate_equilibrium_returns(w_mkt, Sigma, risk_aversion, rf)

        # Step 2: Process views
        if views is None or len(views) == 0:
            # No views: use equilibrium returns
            posterior_returns = Pi
            posterior_cov = Sigma
            P = None
            Q = None
            Omega = None
        else:
            # Validate and construct view matrices
            P, Q, Omega = self._construct_view_matrices(views, len(w_mkt), Sigma, tau)

            # Step 3: Bayesian update to get posterior returns
            posterior_returns, posterior_cov = self._bayesian_update(
                Pi, Sigma, P, Q, Omega, tau
            )

        # Step 4: Optimize portfolio with posterior returns
        weights = self._optimize_portfolio(posterior_returns, posterior_cov, risk_aversion)

        # Calculate portfolio metrics
        portfolio_return = np.dot(weights, posterior_returns)
        portfolio_variance = np.dot(weights, np.dot(posterior_cov, weights))
        portfolio_risk = np.sqrt(portfolio_variance)

        result_value = {
            'posterior_returns': posterior_returns,
            'posterior_cov': posterior_cov,
            'weights': weights,
            'equilibrium_returns': Pi,
            'expected_return': portfolio_return,
            'risk': portfolio_risk,
            'variance': portfolio_variance
        }

        parameters = {
            'risk_aversion': risk_aversion,
            'tau': tau,
            'risk_free_rate': rf,
            'n_views': len(views) if views else 0,
            'n_assets': len(w_mkt)
        }

        metadata = {
            'weights_sum': np.sum(weights),
            'weight_change': np.linalg.norm(weights - w_mkt),
            'return_change': portfolio_return - np.dot(w_mkt, Pi)
        }

        return self._create_result_dict(
            value=result_value,
            method='black_litterman',
            parameters=parameters,
            metadata=metadata
        )

    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        """Alias for optimize method to satisfy BaseCalculator interface."""
        return self.optimize(*args, **kwargs)

    def _validate_weights(self, weights: Union[np.ndarray, pd.Series, List]) -> np.ndarray:
        """Validate and normalize portfolio weights."""
        w = self._validate_numeric_input(weights, 'market_weights')

        if isinstance(w, (int, float)):
            raise DataValidationError(
                "market_weights must be an array, not a scalar",
                field_name='market_weights'
            )

        if isinstance(w, pd.Series):
            w = w.values

        w = np.asarray(w, dtype=float)

        if w.ndim != 1:
            raise DataValidationError(
                f"market_weights must be 1-dimensional, got shape {w.shape}",
                field_name='market_weights'
            )

        if len(w) < 2:
            raise DataValidationError(
                f"Need at least 2 assets, got {len(w)}",
                field_name='market_weights'
            )

        # Check non-negative
        if np.any(w < 0):
            raise DataValidationError(
                "market_weights must be non-negative",
                field_name='market_weights'
            )

        # Normalize to sum to 1
        weight_sum = np.sum(w)
        if weight_sum <= 0:
            raise DataValidationError(
                "market_weights must sum to positive value",
                field_name='market_weights'
            )

        w = w / weight_sum

        return w

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

    def _calculate_equilibrium_returns(self,
                                      w_mkt: np.ndarray,
                                      Sigma: np.ndarray,
                                      risk_aversion: float,
                                      rf: float) -> np.ndarray:
        """
        Calculate market equilibrium returns using reverse optimization.

        Formula: Π = λ * Σ * w_mkt

        Where λ is the risk aversion parameter.
        """
        Pi = risk_aversion * np.dot(Sigma, w_mkt)
        return Pi

    def _construct_view_matrices(self,
                                 views: List[Dict[str, Any]],
                                 n_assets: int,
                                 Sigma: np.ndarray,
                                 tau: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Construct view matrices P, Q, and Ω from view list.

        View format:
            - Absolute view: {'assets': [i], 'return': r, 'confidence': c}
              Interpretation: Asset i will return r

            - Relative view: {'assets': [i, j], 'return': r, 'confidence': c}
              Interpretation: Asset i will outperform asset j by r

        Returns:
            P: View picking matrix (k x n)
            Q: View returns vector (k,)
            Omega: View uncertainty matrix (k x k, diagonal)
        """
        k = len(views)
        P = np.zeros((k, n_assets))
        Q = np.zeros(k)
        Omega = np.zeros((k, k))

        for i, view in enumerate(views):
            # Validate view structure
            if 'assets' not in view or 'return' not in view:
                raise ConfigurationError(
                    f"View {i} must have 'assets' and 'return' keys",
                    parameter='views'
                )

            assets = view['assets']
            expected_return = view['return']
            confidence = view.get('confidence', 0.5)

            # Validate confidence
            if not 0 < confidence <= 1:
                raise ConfigurationError(
                    f"View {i} confidence must be in (0, 1], got {confidence}",
                    parameter='views'
                )

            # Validate assets
            if not isinstance(assets, (list, tuple)):
                assets = [assets]

            for asset_idx in assets:
                if not 0 <= asset_idx < n_assets:
                    raise ConfigurationError(
                        f"View {i} asset index {asset_idx} out of range [0, {n_assets})",
                        parameter='views'
                    )

            # Construct P matrix row
            if len(assets) == 1:
                # Absolute view: asset i will return r
                P[i, assets[0]] = 1.0
            elif len(assets) == 2:
                # Relative view: asset i outperforms asset j by r
                P[i, assets[0]] = 1.0
                P[i, assets[1]] = -1.0
            else:
                raise ConfigurationError(
                    f"View {i} must specify 1 or 2 assets, got {len(assets)}",
                    parameter='views'
                )

            # Set Q (expected return)
            Q[i] = expected_return

            # Calculate Omega (view uncertainty)
            # Higher confidence = lower uncertainty
            # Omega_i = (1/confidence - 1) * P_i * (τ * Σ) * P_i^T
            view_variance = np.dot(P[i], np.dot(tau * Sigma, P[i]))
            Omega[i, i] = view_variance / confidence

        return P, Q, Omega

    def _bayesian_update(self,
                        Pi: np.ndarray,
                        Sigma: np.ndarray,
                        P: np.ndarray,
                        Q: np.ndarray,
                        Omega: np.ndarray,
                        tau: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Perform Bayesian update to combine prior and views.

        Formula:
            Posterior mean: μ = [(τΣ)^-1 + P^T Ω^-1 P]^-1 [(τΣ)^-1 Π + P^T Ω^-1 Q]
            Posterior cov:  M = [(τΣ)^-1 + P^T Ω^-1 P]^-1

        Returns:
            posterior_returns: Posterior expected returns
            posterior_cov: Posterior covariance matrix
        """
        n = len(Pi)

        # Prior precision matrix
        tau_Sigma = tau * Sigma
        tau_Sigma_inv = np.linalg.inv(tau_Sigma)

        # View precision matrix
        Omega_inv = np.linalg.inv(Omega)

        # Posterior precision matrix
        M_inv = tau_Sigma_inv + np.dot(P.T, np.dot(Omega_inv, P))

        # Posterior covariance
        M = np.linalg.inv(M_inv)

        # Posterior mean
        posterior_returns = np.dot(M, np.dot(tau_Sigma_inv, Pi) + np.dot(P.T, np.dot(Omega_inv, Q)))

        # Full posterior covariance (including estimation uncertainty)
        posterior_cov = Sigma + M

        return posterior_returns, posterior_cov

    def _optimize_portfolio(self,
                           expected_returns: np.ndarray,
                           cov_matrix: np.ndarray,
                           risk_aversion: float) -> np.ndarray:
        """
        Optimize portfolio weights given expected returns and covariance.

        Uses mean-variance optimization:
            w* = (1/λ) * Σ^-1 * μ

        Then normalize to sum to 1.
        """
        try:
            Sigma_inv = np.linalg.inv(cov_matrix)
            weights = np.dot(Sigma_inv, expected_returns) / risk_aversion

            # Normalize to sum to 1
            weights = weights / np.sum(weights)

            return weights
        except np.linalg.LinAlgError:
            raise CalculationError(
                "Failed to invert covariance matrix",
                calculation_type='portfolio'
            )
