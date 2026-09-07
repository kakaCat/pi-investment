"""
Risk Aggregation Calculator
============================

Multi-asset portfolio risk aggregation with component, marginal, and
incremental risk decomposition, expected shortfall, and diversification
ratio analysis.

Author: QuantSys V2
Date: 2026-05-25
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional
from scipy import stats

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    DataValidationError,
    InsufficientDataError,
    ConfigurationError,
)


class RiskAggregationCalculator(BaseCalculator):
    """
    Multi-asset portfolio risk aggregation calculator.

    Aggregates individual position risks into portfolio-level metrics
    and decomposes total risk into component, marginal, and incremental
    contributions.

    Methods:
        - standard: Portfolio-level VaR
        - component: Component VaR (risk contribution per asset)
        - marginal: Marginal VaR (sensitivity of portfolio VaR to weight changes)
        - incremental: Incremental VaR (impact of adding/removing an asset)

    Example:
        calculator = RiskAggregationCalculator(precision=4)
        positions = {'AAPL': 0.4, 'GOOGL': 0.3, 'MSFT': 0.3}
        cov = np.array([[0.04, 0.01, 0.008],
                        [0.01, 0.03, 0.012],
                        [0.008, 0.012, 0.05]])
        result = calculator.calculate(positions, cov, method='component')
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize risk aggregation calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate for calculations
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  positions: Dict[str, float],
                  covariance_matrix: Union[pd.DataFrame, np.ndarray],
                  method: str = 'standard',
                  confidence_level: float = 0.95,
                  time_horizon: float = 1.0) -> Dict[str, Any]:
        """
        Calculate portfolio risk aggregation.

        Args:
            positions: Dictionary of {asset_id: weight} where weights sum to ~1.0
            covariance_matrix: Covariance matrix of asset returns (pd.DataFrame or np.ndarray)
            method: 'standard', 'component', 'marginal', or 'incremental'
            confidence_level: Confidence level for VaR (default: 0.95)
            time_horizon: Time horizon scaling factor (default: 1.0)

        Returns:
            Dictionary with aggregation results

        Raises:
            DataValidationError: If positions or covariance matrix are invalid
            ConfigurationError: If method is unsupported or confidence level invalid
            CalculationError: If computation fails
        """
        # Validate confidence level
        confidence_level = self._validate_probability(confidence_level, 'confidence_level')
        if confidence_level <= 0.5:
            raise ConfigurationError(
                "Confidence level should be > 0.5",
                parameter='confidence_level'
            )

        # Validate time horizon
        if time_horizon <= 0:
            raise DataValidationError(
                "Time horizon must be positive",
                field_name='time_horizon'
            )

        # Validate method
        method = self.validate_method(method)

        # Convert covariance matrix to numpy array
        if isinstance(covariance_matrix, pd.DataFrame):
            cov = covariance_matrix.values
            asset_ids = list(covariance_matrix.columns)
        else:
            cov = np.array(covariance_matrix)
            asset_ids = list(positions.keys())

        # Validate covariance matrix
        n_assets = len(positions)
        if cov.shape != (n_assets, n_assets):
            raise DataValidationError(
                f"Covariance matrix shape {cov.shape} must be ({n_assets}, {n_assets})",
                field_name='covariance_matrix'
            )

        # Validate positions sum
        weights = np.array([positions[aid] for aid in asset_ids])
        if abs(np.sum(weights) - 1.0) > 0.05:
            raise DataValidationError(
                f"Position weights sum to {np.sum(weights):.4f}, expected ~1.0",
                field_name='positions'
            )

        try:
            if method == 'standard':
                result = self._aggregate_var(positions, cov, confidence_level, time_horizon)
                return self._create_result_dict(
                    value=result,
                    method='risk_aggregation_standard',
                    parameters={
                        'confidence_level': confidence_level,
                        'time_horizon': time_horizon,
                        'n_assets': n_assets
                    }
                )

            elif method == 'component':
                result = self._component_var(positions, cov, confidence_level, time_horizon)
                return self._create_result_dict(
                    value=result,
                    method='risk_aggregation_component',
                    parameters={
                        'confidence_level': confidence_level,
                        'time_horizon': time_horizon,
                        'n_assets': n_assets
                    }
                )

            elif method == 'marginal':
                result = self._marginal_var(positions, cov, confidence_level, time_horizon)
                return self._create_result_dict(
                    value=result,
                    method='risk_aggregation_marginal',
                    parameters={
                        'confidence_level': confidence_level,
                        'time_horizon': time_horizon,
                        'n_assets': n_assets
                    }
                )

            elif method == 'incremental':
                result = self._incremental_var(positions, cov, confidence_level, time_horizon)
                return self._create_result_dict(
                    value=result,
                    method='risk_aggregation_incremental',
                    parameters={
                        'confidence_level': confidence_level,
                        'time_horizon': time_horizon,
                        'n_assets': n_assets
                    }
                )

        except Exception as e:
            if isinstance(e, (DataValidationError, ConfigurationError)):
                raise
            raise CalculationError(str(e), calculation_type='RiskAggregation')

    def _aggregate_var(self,
                       positions: Dict[str, float],
                       cov: np.ndarray,
                       cl: float,
                       horizon: float) -> float:
        """
        Calculate portfolio-level Value at Risk.

        Portfolio VaR = z_alpha * sqrt(w' * Sigma * w) * sqrt(horizon)

        Args:
            positions: Asset position weights
            cov: Covariance matrix
            cl: Confidence level
            horizon: Time horizon

        Returns:
            Portfolio VaR (positive value representing potential loss)
        """
        asset_ids = list(positions.keys())
        w = np.array([positions[aid] for aid in asset_ids])

        # Portfolio variance: w' * Sigma * w
        portfolio_variance = w.T @ cov @ w

        if portfolio_variance <= 0:
            raise CalculationError(
                "Portfolio variance is non-positive",
                calculation_type='portfolio_var'
            )

        portfolio_vol = np.sqrt(portfolio_variance)

        # Z-score for confidence level
        z_score = abs(stats.norm.ppf(1 - cl))

        # Portfolio VaR
        portfolio_var = z_score * portfolio_vol * np.sqrt(horizon)

        return float(portfolio_var)

    def _component_var(self,
                       positions: Dict[str, float],
                       cov: np.ndarray,
                       cl: float,
                       horizon: float) -> Dict[str, Any]:
        """
        Calculate Component VaR for each asset.

        CVaR_i = w_i * (Sigma * w)_i / sqrt(w' * Sigma * w) * PortfolioVaR
        The sum of all CVaR_i equals the portfolio VaR.

        Args:
            positions: Asset position weights
            cov: Covariance matrix
            cl: Confidence level
            horizon: Time horizon

        Returns:
            Dictionary with component VaR per asset and portfolio total
        """
        asset_ids = list(positions.keys())
        w = np.array([positions[aid] for aid in asset_ids])

        portfolio_variance = w.T @ cov @ w
        if portfolio_variance <= 0:
            raise CalculationError(
                "Portfolio variance is non-positive",
                calculation_type='component_var'
            )

        portfolio_vol = np.sqrt(portfolio_variance)
        z_score = abs(stats.norm.ppf(1 - cl))
        portfolio_var = z_score * portfolio_vol * np.sqrt(horizon)

        # Marginal contribution to variance: Sigma * w
        mcv = cov @ w  # (Sigma * w)_i

        # Component VaR
        component_var = {}
        for i, aid in enumerate(asset_ids):
            # CVaR_i = w_i * (Sigma*w)_i / sqrt(w'*Sigma*w) * PortfolioVaR
            cvar_i = w[i] * mcv[i] / portfolio_vol * z_score * np.sqrt(horizon)
            component_var[aid] = float(self._round_result(cvar_i))

        # Verify that components sum to portfolio VaR (within rounding tolerance)
        total_cvar = sum(component_var.values())

        return {
            'portfolio_var': float(self._round_result(portfolio_var)),
            'component_var': component_var,
            'component_var_pct': {
                aid: float(self._round_result(cvar / portfolio_var * 100))
                for aid, cvar in component_var.items()
            },
            'total_components': float(self._round_result(total_cvar)),
        }

    def _marginal_var(self,
                      positions: Dict[str, float],
                      cov: np.ndarray,
                      cl: float,
                      horizon: float) -> Dict[str, Any]:
        """
        Calculate Marginal VaR for each asset.

        MVaR_i = z_alpha * (Sigma * w)_i / sqrt(w' * Sigma * w) * sqrt(horizon)

        Marginal VaR measures the change in portfolio VaR for a small
        change in the weight of an asset.

        Args:
            positions: Asset position weights
            cov: Covariance matrix
            cl: Confidence level
            horizon: Time horizon

        Returns:
            Dictionary with marginal VaR per asset
        """
        asset_ids = list(positions.keys())
        w = np.array([positions[aid] for aid in asset_ids])

        portfolio_variance = w.T @ cov @ w
        if portfolio_variance <= 0:
            raise CalculationError(
                "Portfolio variance is non-positive",
                calculation_type='marginal_var'
            )

        portfolio_vol = np.sqrt(portfolio_variance)
        z_score = abs(stats.norm.ppf(1 - cl))

        # Marginal VaR
        marginal_var = {}
        mcv = cov @ w  # Sigma * w

        for i, aid in enumerate(asset_ids):
            mvar_i = z_score * mcv[i] / portfolio_vol * np.sqrt(horizon)
            marginal_var[aid] = float(self._round_result(mvar_i))

        return {
            'marginal_var': marginal_var,
            'portfolio_vol': float(self._round_result(portfolio_vol)),
        }

    def _incremental_var(self,
                         positions: Dict[str, float],
                         cov: np.ndarray,
                         cl: float,
                         horizon: float) -> Dict[str, Any]:
        """
        Calculate Incremental VaR for each asset.

        IVaR = PortfolioVaR(with asset) - PortfolioVaR(without asset)

        Args:
            positions: Asset position weights
            cov: Covariance matrix
            cl: Confidence level
            horizon: Time horizon

        Returns:
            Dictionary with incremental VaR per asset
        """
        asset_ids = list(positions.keys())
        w = np.array([positions[aid] for aid in asset_ids])

        # Full portfolio VaR
        base_var = self._aggregate_var(positions, cov, cl, horizon)

        incremental_var = {}
        for i, aid in enumerate(asset_ids):
            if len(asset_ids) <= 1:
                incremental_var[aid] = float(base_var)
                continue

            # Remove asset i: set weight to 0 and re-normalize
            w_reduced = np.delete(w, i)
            w_reduced = w_reduced / np.sum(w_reduced)

            # Remove row and column i from covariance matrix
            cov_reduced = np.delete(np.delete(cov, i, axis=0), i, axis=1)

            reduced_ids = [a for j, a in enumerate(asset_ids) if j != i]
            reduced_positions = {
                aid_j: float(w_reduced[j]) for j, aid_j in enumerate(reduced_ids)
            }

            var_without = self._aggregate_var(reduced_positions, cov_reduced, cl, horizon)
            incremental_var[aid] = float(self._round_result(base_var - var_without))

        return {
            'portfolio_var': float(self._round_result(base_var)),
            'incremental_var': incremental_var,
        }

    def calculate_expected_shortfall(self,
                                     returns: Union[List, np.ndarray, pd.Series],
                                     confidence_level: float = 0.975,
                                     method: str = 'historical') -> Dict[str, Any]:
        """
        Calculate Expected Shortfall (ES/CVaR) for the portfolio.

        Args:
            returns: Portfolio return series
            confidence_level: Confidence level (default: 0.975)
            method: 'historical' or 'parametric'

        Returns:
            Dictionary with ES value and metadata
        """
        returns = self._validate_returns(returns, 'returns')
        confidence_level = self._validate_probability(confidence_level, 'confidence_level')

        if len(returns) < 20:
            raise InsufficientDataError(
                required=20,
                provided=len(returns),
                calculation='expected_shortfall'
            )

        if method == 'historical':
            var_threshold = np.percentile(returns, (1 - confidence_level) * 100)
            tail_returns = returns[returns <= var_threshold]
            if len(tail_returns) == 0:
                es_value = float(var_threshold)
            else:
                es_value = float(np.mean(tail_returns))

        elif method == 'parametric':
            mean = np.mean(returns)
            std = np.std(returns, ddof=1)
            z_score = abs(stats.norm.ppf(1 - confidence_level))
            # ES for normal distribution: mean - std * phi(z) / (1-cl)
            es_value = float(mean - std * stats.norm.pdf(z_score) / (1 - confidence_level))
        else:
            raise ConfigurationError(
                f"Unsupported ES method: {method}",
                parameter='method'
            )

        return self._create_result_dict(
            value=abs(es_value),
            method=f'expected_shortfall_{method}',
            parameters={
                'confidence_level': confidence_level,
                'method': method,
                'n_observations': len(returns)
            },
            metadata={
                'interpretation': f'Expected loss in worst {((1 - confidence_level) * 100):.1f}% cases'
            }
        )

    def calculate_diversification_ratio(self,
                                        positions: Dict[str, float],
                                        covariance_matrix: Union[pd.DataFrame, np.ndarray]) -> Dict[str, Any]:
        """
        Calculate diversification ratio.

        DR = (sum w_i * sigma_i) / sigma_p

        A ratio > 1 indicates diversification benefit. Higher values
        indicate better diversification.

        Args:
            positions: Asset position weights
            covariance_matrix: Covariance matrix

        Returns:
            Dictionary with diversification ratio
        """
        if isinstance(covariance_matrix, pd.DataFrame):
            cov = covariance_matrix.values
            asset_ids = list(covariance_matrix.columns)
        else:
            cov = np.array(covariance_matrix)
            asset_ids = list(positions.keys())

        w = np.array([positions[aid] for aid in asset_ids])
        n = len(w)

        if n < 2:
            return self._create_result_dict(
                value=1.0,
                method='diversification_ratio',
                parameters={'n_assets': n},
                metadata={'interpretation': 'Single asset - no diversification benefit'}
            )

        # Individual asset volatilities
        individual_vols = np.sqrt(np.diag(cov))

        # Weighted sum of individual volatilities
        weighted_sum_vols = np.sum(w * individual_vols)

        # Portfolio volatility
        portfolio_vol = np.sqrt(w.T @ cov @ w)

        if portfolio_vol <= 0:
            return self._create_result_dict(
                value=1.0,
                method='diversification_ratio',
                parameters={'n_assets': n},
                metadata={'interpretation': 'Zero portfolio volatility'}
            )

        dr = weighted_sum_vols / portfolio_vol

        return self._create_result_dict(
            value=float(self._round_result(dr)),
            method='diversification_ratio',
            parameters={
                'n_assets': n,
                'weighted_sum_vols': float(self._round_result(weighted_sum_vols)),
                'portfolio_vol': float(self._round_result(portfolio_vol))
            },
            metadata={
                'interpretation': (
                    'High diversification' if dr > 1.5 else
                    'Moderate diversification' if dr > 1.2 else
                    'Low diversification'
                )
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Return list of supported aggregation methods."""
        return ['standard', 'component', 'marginal', 'incremental']
