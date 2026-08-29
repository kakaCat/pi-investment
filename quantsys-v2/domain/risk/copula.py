"""
Copula Calculator
=================

Implements copula models for modeling multivariate dependence structures
and joint tail risk in portfolios.

Copulas separate marginal distributions from dependence structure,
allowing flexible modeling of joint distributions.

Supported copulas:
- Gaussian Copula: Symmetric tail dependence
- t-Copula: Symmetric tail dependence with heavier tails
- Clayton Copula: Lower tail dependence
- Gumbel Copula: Upper tail dependence

Author: QuantSys V2 Advanced Risk Module
Date: 2026-05-24
"""
import structlog
logger = structlog.get_logger(__name__)

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional, Tuple
from scipy import stats, optimize
from scipy.special import gamma
import warnings

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    InsufficientDataError,
    DataValidationError,
    ConfigurationError,
    ConvergenceError,
    ModelFitError
)


class CopulaCalculator(BaseCalculator):
    """
    Copula Calculator

    Models multivariate dependence structures using copulas.
    Copulas allow modeling of joint distributions while separating
    marginal behavior from dependence structure.

    Key Features:
        - Multiple copula families (Gaussian, t, Clayton, Gumbel)
        - Tail dependence analysis
        - Joint VaR calculation
        - Scenario simulation
        - Correlation vs tail dependence comparison

    Copula Types:
        - Gaussian: C(u,v) = Φ_ρ(Φ^(-1)(u), Φ^(-1)(v))
          * Symmetric tail dependence
          * No tail dependence (λ_L = λ_U = 0)

        - t-Copula: Similar to Gaussian but with heavier tails
          * Symmetric tail dependence
          * λ_L = λ_U = 2t_{ν+1}(-√((ν+1)(1-ρ)/(1+ρ)))

        - Clayton: C(u,v) = (u^(-θ) + v^(-θ) - 1)^(-1/θ)
          * Lower tail dependence
          * λ_L = 2^(-1/θ), λ_U = 0

        - Gumbel: C(u,v) = exp(-[(-ln u)^θ + (-ln v)^θ]^(1/θ))
          * Upper tail dependence
          * λ_U = 2 - 2^(1/θ), λ_L = 0

    Example:
        calculator = CopulaCalculator()
        result = calculator.calculate(
            returns=returns_df,
            copula_type='t',
            marginal_dist='empirical',
            n_simulations=10000
        )
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Copula calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  returns: Union[pd.DataFrame, np.ndarray],
                  copula_type: str = 'gaussian',
                  marginal_dist: str = 'empirical',
                  n_simulations: int = 10000,
                  confidence_level: float = 0.95,
                  asset_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Calculate copula model and joint risk metrics.

        Args:
            returns: Historical returns (observations x assets)
            copula_type: Type of copula ('gaussian', 't', 'clayton', 'gumbel')
            marginal_dist: Marginal distribution ('empirical', 'normal', 't')
            n_simulations: Number of simulations for joint VaR
            confidence_level: Confidence level for VaR
            asset_names: Optional asset names

        Returns:
            Dictionary with copula parameters and joint risk metrics

        Raises:
            InsufficientDataError: If not enough data
            ConfigurationError: If invalid parameters
            ModelFitError: If copula fitting fails
        """
        # Validate inputs
        if isinstance(returns, pd.DataFrame):
            asset_names = asset_names or returns.columns.tolist()
            returns_matrix = returns.values
        else:
            returns_matrix = np.array(returns)
            if returns_matrix.ndim == 1:
                raise DataValidationError("Returns must be multivariate (at least 2 assets)")
            asset_names = asset_names or [f'Asset_{i+1}' for i in range(returns_matrix.shape[1])]

        n_obs, n_assets = returns_matrix.shape

        if n_assets < 2:
            raise DataValidationError("Copula requires at least 2 assets")

        if n_obs < 100:
            raise InsufficientDataError(
                required=100,
                provided=n_obs,
                calculation='Copula modeling'
            )

        # Validate method
        copula_type = copula_type.lower()
        if copula_type not in ['gaussian', 't', 'clayton', 'gumbel']:
            raise ConfigurationError(
                f"Unknown copula type: {copula_type}",
                parameter='copula_type'
            )

        try:
            # Transform to uniform marginals (pseudo-observations)
            uniform_data = self._transform_to_uniform(returns_matrix, marginal_dist)

            # Fit copula
            if copula_type == 'gaussian':
                copula_params = self._fit_gaussian_copula(uniform_data)
            elif copula_type == 't':
                copula_params = self._fit_t_copula(uniform_data)
            elif copula_type == 'clayton':
                copula_params = self._fit_clayton_copula(uniform_data)
            elif copula_type == 'gumbel':
                copula_params = self._fit_gumbel_copula(uniform_data)

            # Calculate tail dependence
            tail_dependence = self._calculate_tail_dependence(copula_type, copula_params)

            # Simulate from copula
            simulated_uniform = self._simulate_copula(
                copula_type,
                copula_params,
                n_simulations,
                n_assets
            )

            # Transform back to returns
            simulated_returns = self._transform_from_uniform(
                simulated_uniform,
                returns_matrix,
                marginal_dist
            )

            # Calculate joint VaR
            joint_var = self._calculate_joint_var(
                simulated_returns,
                confidence_level
            )

            # Calculate correlation matrix for comparison
            correlation_matrix = np.corrcoef(returns_matrix.T)

            return self._create_result_dict(
                value={
                    'copula_type': copula_type,
                    'copula_parameters': copula_params,
                    'correlation_matrix': correlation_matrix.tolist(),
                    'tail_dependence': tail_dependence,
                    'joint_var': joint_var,
                    'simulated_returns': {
                        'mean': np.mean(simulated_returns, axis=0).tolist(),
                        'std': np.std(simulated_returns, axis=0, ddof=1).tolist(),
                        'n_simulations': n_simulations
                    }
                },
                method=f'copula_{copula_type}',
                parameters={
                    'n_observations': n_obs,
                    'n_assets': n_assets,
                    'marginal_dist': marginal_dist,
                    'confidence_level': confidence_level
                },
                metadata={
                    'asset_names': asset_names,
                    'interpretation': 'Copula captures dependence structure beyond correlation'
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, ConfigurationError, InsufficientDataError)):
                raise
            raise ModelFitError(str(e), model_type=f'{copula_type} copula')

    def _transform_to_uniform(self,
                             returns: np.ndarray,
                             marginal_dist: str) -> np.ndarray:
        """
        Transform returns to uniform [0,1] marginals.

        Args:
            returns: Returns matrix
            marginal_dist: Marginal distribution type

        Returns:
            Uniform pseudo-observations
        """
        n_obs, n_assets = returns.shape
        uniform_data = np.zeros_like(returns)

        for i in range(n_assets):
            asset_returns = returns[:, i]

            if marginal_dist == 'empirical':
                # Empirical CDF (rank-based)
                ranks = stats.rankdata(asset_returns)
                uniform_data[:, i] = ranks / (n_obs + 1)

            elif marginal_dist == 'normal':
                # Fit normal distribution
                mu, sigma = np.mean(asset_returns), np.std(asset_returns, ddof=1)
                uniform_data[:, i] = stats.norm.cdf(asset_returns, mu, sigma)

            elif marginal_dist == 't':
                # Fit t-distribution
                params = stats.t.fit(asset_returns)
                uniform_data[:, i] = stats.t.cdf(asset_returns, *params)

            else:
                raise ConfigurationError(
                    f"Unknown marginal distribution: {marginal_dist}",
                    parameter='marginal_dist'
                )

        # Ensure values are in (0, 1) to avoid numerical issues
        uniform_data = np.clip(uniform_data, 1e-10, 1 - 1e-10)

        return uniform_data

    def _transform_from_uniform(self,
                               uniform_data: np.ndarray,
                               original_returns: np.ndarray,
                               marginal_dist: str) -> np.ndarray:
        """
        Transform uniform data back to returns scale.

        Args:
            uniform_data: Uniform [0,1] data
            original_returns: Original returns for fitting marginals
            marginal_dist: Marginal distribution type

        Returns:
            Simulated returns
        """
        n_sim, n_assets = uniform_data.shape
        simulated_returns = np.zeros_like(uniform_data)

        for i in range(n_assets):
            asset_returns = original_returns[:, i]

            if marginal_dist == 'empirical':
                # Use empirical quantiles
                simulated_returns[:, i] = np.quantile(
                    asset_returns,
                    uniform_data[:, i]
                )

            elif marginal_dist == 'normal':
                mu, sigma = np.mean(asset_returns), np.std(asset_returns, ddof=1)
                simulated_returns[:, i] = stats.norm.ppf(uniform_data[:, i], mu, sigma)

            elif marginal_dist == 't':
                params = stats.t.fit(asset_returns)
                simulated_returns[:, i] = stats.t.ppf(uniform_data[:, i], *params)

        return simulated_returns

    def _fit_gaussian_copula(self, uniform_data: np.ndarray) -> Dict[str, Any]:
        """
        Fit Gaussian copula.

        Returns:
            Dictionary with correlation matrix
        """
        # Transform to standard normal
        normal_data = stats.norm.ppf(uniform_data)

        # Calculate correlation matrix
        correlation = np.corrcoef(normal_data.T)

        return {
            'correlation_matrix': correlation.tolist(),
            'type': 'gaussian'
        }

    def _fit_t_copula(self, uniform_data: np.ndarray) -> Dict[str, Any]:
        """
        Fit t-copula.

        Returns:
            Dictionary with correlation matrix and degrees of freedom
        """
        # Transform to standard normal for initial correlation estimate
        normal_data = stats.norm.ppf(uniform_data)
        correlation = np.corrcoef(normal_data.T)

        # Estimate degrees of freedom using MLE
        def neg_log_likelihood(nu):
            """Negative log-likelihood for t-copula."""
            if nu <= 2:
                return 1e10

            # Transform to t-distribution
            t_data = stats.t.ppf(uniform_data, nu)

            # Calculate log-likelihood (simplified)
            try:
                log_lik = 0
                for i in range(len(uniform_data)):
                    # Multivariate t density (simplified for bivariate case)
                    log_lik += stats.multivariate_t.logpdf(
                        t_data[i],
                        loc=np.zeros(uniform_data.shape[1]),
                        shape=correlation,
                        df=nu
                    )
                return -log_lik
            except Exception:
                logger.debug("unexpected exception in module", exc_info=True)
                return 1e10

        # Optimize degrees of freedom
        result = optimize.minimize_scalar(
            neg_log_likelihood,
            bounds=(2.1, 30),
            method='bounded'
        )

        df = result.x if result.success else 5.0

        return {
            'correlation_matrix': correlation.tolist(),
            'degrees_of_freedom': float(df),
            'type': 't'
        }

    def _fit_clayton_copula(self, uniform_data: np.ndarray) -> Dict[str, Any]:
        """
        Fit Clayton copula (bivariate only for simplicity).

        Returns:
            Dictionary with theta parameter
        """
        if uniform_data.shape[1] > 2:
            self.logger.warning("Clayton copula fitting simplified for multivariate case")

        # Use Kendall's tau method for parameter estimation
        # For Clayton: tau = theta / (theta + 2)
        # So: theta = 2 * tau / (1 - tau)

        # Calculate average pairwise Kendall's tau
        n_assets = uniform_data.shape[1]
        taus = []

        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                tau, _ = stats.kendalltau(uniform_data[:, i], uniform_data[:, j])
                taus.append(tau)

        avg_tau = np.mean(taus)

        # Estimate theta
        if avg_tau >= 0.99:
            theta = 100.0
        elif avg_tau <= 0:
            theta = 0.01
        else:
            theta = 2 * avg_tau / (1 - avg_tau)

        return {
            'theta': float(max(0.01, theta)),
            'kendall_tau': float(avg_tau),
            'type': 'clayton'
        }

    def _fit_gumbel_copula(self, uniform_data: np.ndarray) -> Dict[str, Any]:
        """
        Fit Gumbel copula (bivariate only for simplicity).

        Returns:
            Dictionary with theta parameter
        """
        if uniform_data.shape[1] > 2:
            self.logger.warning("Gumbel copula fitting simplified for multivariate case")

        # Use Kendall's tau method
        # For Gumbel: tau = 1 - 1/theta
        # So: theta = 1 / (1 - tau)

        # Calculate average pairwise Kendall's tau
        n_assets = uniform_data.shape[1]
        taus = []

        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                tau, _ = stats.kendalltau(uniform_data[:, i], uniform_data[:, j])
                taus.append(tau)

        avg_tau = np.mean(taus)

        # Estimate theta
        if avg_tau >= 0.99:
            theta = 100.0
        elif avg_tau <= 0:
            theta = 1.01
        else:
            theta = 1.0 / (1.0 - avg_tau)

        return {
            'theta': float(max(1.01, theta)),
            'kendall_tau': float(avg_tau),
            'type': 'gumbel'
        }

    def _calculate_tail_dependence(self,
                                   copula_type: str,
                                   params: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate tail dependence coefficients.

        Returns:
            Dictionary with lower and upper tail dependence
        """
        if copula_type == 'gaussian':
            # Gaussian copula has no tail dependence
            return {
                'lower_tail': 0.0,
                'upper_tail': 0.0,
                'note': 'Gaussian copula has asymptotic tail independence'
            }

        elif copula_type == 't':
            # t-copula has symmetric tail dependence
            rho = params['correlation_matrix'][0][1] if len(params['correlation_matrix']) > 1 else 0
            nu = params['degrees_of_freedom']

            # λ = 2 * t_{ν+1}(-√((ν+1)(1-ρ)/(1+ρ)))
            if abs(rho) < 0.99:
                arg = -np.sqrt((nu + 1) * (1 - rho) / (1 + rho))
                tail_dep = 2 * stats.t.cdf(arg, nu + 1)
            else:
                tail_dep = 0.5

            return {
                'lower_tail': float(tail_dep),
                'upper_tail': float(tail_dep),
                'note': 't-copula has symmetric tail dependence'
            }

        elif copula_type == 'clayton':
            # Clayton has lower tail dependence only
            theta = params['theta']
            lower_tail = 2 ** (-1 / theta) if theta > 0 else 0

            return {
                'lower_tail': float(lower_tail),
                'upper_tail': 0.0,
                'note': 'Clayton copula has lower tail dependence only'
            }

        elif copula_type == 'gumbel':
            # Gumbel has upper tail dependence only
            theta = params['theta']
            upper_tail = 2 - 2 ** (1 / theta) if theta > 1 else 0

            return {
                'lower_tail': 0.0,
                'upper_tail': float(upper_tail),
                'note': 'Gumbel copula has upper tail dependence only'
            }

        return {'lower_tail': 0.0, 'upper_tail': 0.0}

    def _simulate_copula(self,
                        copula_type: str,
                        params: Dict[str, Any],
                        n_simulations: int,
                        n_assets: int) -> np.ndarray:
        """
        Simulate from fitted copula.

        Returns:
            Simulated uniform data (n_simulations x n_assets)
        """
        if copula_type == 'gaussian':
            correlation = np.array(params['correlation_matrix'])
            # Simulate from multivariate normal
            normal_sim = np.random.multivariate_normal(
                np.zeros(n_assets),
                correlation,
                n_simulations
            )
            # Transform to uniform
            uniform_sim = stats.norm.cdf(normal_sim)

        elif copula_type == 't':
            correlation = np.array(params['correlation_matrix'])
            df = params['degrees_of_freedom']

            # Simulate from multivariate t
            # Method: X = Z / sqrt(V/df) where Z ~ N(0, Σ), V ~ χ²(df)
            normal_sim = np.random.multivariate_normal(
                np.zeros(n_assets),
                correlation,
                n_simulations
            )
            chi2_sim = np.random.chisquare(df, n_simulations)
            t_sim = normal_sim / np.sqrt(chi2_sim / df)[:, np.newaxis]

            # Transform to uniform
            uniform_sim = stats.t.cdf(t_sim, df)

        elif copula_type == 'clayton':
            theta = params['theta']
            # Simplified bivariate Clayton simulation
            uniform_sim = np.zeros((n_simulations, n_assets))

            for i in range(n_simulations):
                # Generate using conditional sampling
                u1 = np.random.uniform(0, 1, n_assets)
                v = np.random.uniform(0, 1)

                # Clayton copula conditional: C(u2|u1) = u1^(-theta-1) * (u1^(-theta) + u2^(-theta) - 1)^(-1/theta-1)
                # Simplified: use Gaussian copula for multivariate case
                if n_assets == 2:
                    u2 = (u1[0] ** (-theta) * (v ** (-theta / (1 + theta)) - 1) + 1) ** (-1 / theta)
                    uniform_sim[i] = [u1[0], u2]
                else:
                    # Fall back to Gaussian for multivariate
                    correlation = np.eye(n_assets) + 0.5 * (1 - np.eye(n_assets))
                    normal_sim = np.random.multivariate_normal(np.zeros(n_assets), correlation)
                    uniform_sim[i] = stats.norm.cdf(normal_sim)

        elif copula_type == 'gumbel':
            theta = params['theta']
            # Simplified bivariate Gumbel simulation
            uniform_sim = np.zeros((n_simulations, n_assets))

            for i in range(n_simulations):
                if n_assets == 2:
                    # Use conditional sampling for bivariate Gumbel
                    u1 = np.random.uniform(0, 1)
                    v = np.random.uniform(0, 1)

                    # Gumbel copula simulation (simplified)
                    t = -np.log(u1)
                    s = -np.log(v)
                    w = (t ** theta + s ** theta) ** (1 / theta)
                    u2 = np.exp(-w)

                    uniform_sim[i] = [u1, u2]
                else:
                    # Fall back to Gaussian for multivariate
                    correlation = np.eye(n_assets) + 0.5 * (1 - np.eye(n_assets))
                    normal_sim = np.random.multivariate_normal(np.zeros(n_assets), correlation)
                    uniform_sim[i] = stats.norm.cdf(normal_sim)

        return np.clip(uniform_sim, 1e-10, 1 - 1e-10)

    def _calculate_joint_var(self,
                            simulated_returns: np.ndarray,
                            confidence_level: float) -> Dict[str, float]:
        """
        Calculate joint VaR from simulated returns.

        Args:
            simulated_returns: Simulated returns (n_simulations x n_assets)
            confidence_level: Confidence level

        Returns:
            Dictionary with joint VaR metrics
        """
        # Calculate portfolio returns (equal weights for simplicity)
        n_assets = simulated_returns.shape[1]
        weights = np.ones(n_assets) / n_assets
        portfolio_returns = simulated_returns @ weights

        # Calculate VaR and CVaR
        var = -np.quantile(portfolio_returns, 1 - confidence_level)
        cvar = -np.mean(portfolio_returns[portfolio_returns <= -var])

        # Calculate component VaR
        component_var = {}
        for i in range(n_assets):
            # Marginal contribution to VaR
            asset_contribution = simulated_returns[:, i] * weights[i]
            component_var[f'asset_{i+1}'] = float(-np.quantile(asset_contribution, 1 - confidence_level))

        return {
            'portfolio_var': float(var),
            'portfolio_cvar': float(cvar),
            'component_var': component_var
        }

    def get_supported_methods(self) -> List[str]:
        """Return list of supported copula types."""
        return ['gaussian', 't', 'clayton', 'gumbel']
