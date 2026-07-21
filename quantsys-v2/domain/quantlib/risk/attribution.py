"""
Risk Attribution Calculator
============================

Calculates risk attribution and decomposition by factors, sectors,
or asset classes. Helps identify sources of portfolio risk.

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional, Tuple

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    InsufficientDataError,
    DataValidationError,
    ConfigurationError
)


class RiskAttributionCalculator(BaseCalculator):
    """
    Risk Attribution Calculator

    Decomposes portfolio risk into contributions from individual assets,
    factors, sectors, or other groupings. Useful for understanding
    risk concentration and diversification.

    Methods:
        - marginal_contribution: Marginal contribution to risk (MCR)
        - component_contribution: Component contribution to risk (CCR)
        - percentage_contribution: Percentage contribution to risk (PCR)
        - factor_attribution: Attribution by risk factors

    Example:
        calculator = RiskAttributionCalculator()
        result = calculator.calculate(returns_df, weights)
        print(result['value']['contributions'])
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Risk Attribution calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate (not used but kept for consistency)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  returns: Union[pd.DataFrame, np.ndarray],
                  weights: Union[List, np.ndarray, pd.Series],
                  asset_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Calculate comprehensive risk attribution.

        Args:
            returns: Returns matrix (observations x assets)
            weights: Portfolio weights (must sum to 1)
            asset_names: Optional names for assets

        Returns:
            Dictionary with risk attribution metrics

        Raises:
            InsufficientDataError: If not enough data points
            DataValidationError: If dimensions don't match
            CalculationError: If calculation fails
        """
        # Validate and prepare data
        if isinstance(returns, pd.DataFrame):
            asset_names = asset_names or returns.columns.tolist()
            returns_matrix = returns.values
        else:
            returns_matrix = np.array(returns)
            if returns_matrix.ndim == 1:
                returns_matrix = returns_matrix.reshape(-1, 1)
            asset_names = asset_names or [f'Asset_{i+1}' for i in range(returns_matrix.shape[1])]

        weights = self._validate_numeric_input(weights, 'weights')
        if isinstance(weights, pd.Series):
            weights = weights.values
        weights = np.array(weights).flatten()

        # Validate dimensions
        n_assets = returns_matrix.shape[1]
        if len(weights) != n_assets:
            raise DataValidationError(
                f"Number of weights ({len(weights)}) must match number of assets ({n_assets})"
            )

        if len(asset_names) != n_assets:
            raise DataValidationError(
                f"Number of asset names ({len(asset_names)}) must match number of assets ({n_assets})"
            )

        # Check weights sum to 1 (with tolerance)
        if not np.isclose(np.sum(weights), 1.0, atol=0.01):
            raise DataValidationError(
                f"Weights must sum to 1, got {np.sum(weights)}"
            )

        if returns_matrix.shape[0] < 10:
            raise InsufficientDataError(
                required=10,
                provided=returns_matrix.shape[0],
                calculation='Risk Attribution'
            )

        try:
            # Calculate covariance matrix
            cov_matrix = np.cov(returns_matrix, rowvar=False)

            # Portfolio variance
            portfolio_variance = weights @ cov_matrix @ weights
            portfolio_volatility = np.sqrt(portfolio_variance)

            # Marginal contribution to risk (MCR)
            marginal_contributions = (cov_matrix @ weights) / portfolio_volatility

            # Component contribution to risk (CCR)
            component_contributions = weights * marginal_contributions

            # Percentage contribution to risk (PCR)
            percentage_contributions = (component_contributions / portfolio_volatility) * 100

            # Individual asset volatilities
            asset_volatilities = np.sqrt(np.diag(cov_matrix))

            # Correlation with portfolio
            portfolio_returns = returns_matrix @ weights
            correlations = np.array([
                np.corrcoef(returns_matrix[:, i], portfolio_returns)[0, 1]
                for i in range(n_assets)
            ])

            # Create results dictionary
            contributions = {}
            for i, name in enumerate(asset_names):
                contributions[name] = {
                    'weight': float(weights[i]),
                    'volatility': float(asset_volatilities[i]),
                    'marginal_contribution': float(marginal_contributions[i]),
                    'component_contribution': float(component_contributions[i]),
                    'percentage_contribution': float(percentage_contributions[i]),
                    'correlation_with_portfolio': float(correlations[i])
                }

            result_value = {
                'portfolio_volatility': portfolio_volatility,
                'contributions': contributions,
                'total_percentage': float(np.sum(percentage_contributions))
            }

            return self._create_result_dict(
                value=result_value,
                method='risk_attribution',
                parameters={
                    'n_assets': n_assets,
                    'n_observations': returns_matrix.shape[0]
                },
                metadata={
                    'interpretation': 'Percentage contributions show each asset\'s contribution to total risk'
                }
            )

        except Exception as e:
            if isinstance(e, (InsufficientDataError, DataValidationError)):
                raise
            raise CalculationError(str(e), calculation_type='Risk Attribution')

    def calculate_factor_attribution(self,
                                     returns: Union[pd.DataFrame, np.ndarray],
                                     weights: Union[List, np.ndarray, pd.Series],
                                     factor_exposures: Union[pd.DataFrame, np.ndarray],
                                     factor_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Calculate risk attribution by factors.

        Args:
            returns: Asset returns matrix
            weights: Portfolio weights
            factor_exposures: Factor exposure matrix (assets x factors)
            factor_names: Optional names for factors

        Returns:
            Dictionary with factor risk attribution
        """
        # Validate inputs
        if isinstance(returns, pd.DataFrame):
            returns_matrix = returns.values
        else:
            returns_matrix = np.array(returns)

        weights = np.array(weights).flatten()

        if isinstance(factor_exposures, pd.DataFrame):
            factor_names = factor_names or factor_exposures.columns.tolist()
            exposures = factor_exposures.values
        else:
            exposures = np.array(factor_exposures)
            n_factors = exposures.shape[1]
            factor_names = factor_names or [f'Factor_{i+1}' for i in range(n_factors)]

        # Calculate covariance matrix
        cov_matrix = np.cov(returns_matrix, rowvar=False)

        # Portfolio factor exposures
        portfolio_exposures = exposures.T @ weights

        # Factor covariance matrix
        factor_cov = exposures.T @ cov_matrix @ exposures

        # Portfolio variance
        portfolio_variance = weights @ cov_matrix @ weights
        portfolio_volatility = np.sqrt(portfolio_variance)

        # Factor contributions to variance
        factor_contributions = np.diag(portfolio_exposures @ factor_cov @ portfolio_exposures.T)

        # Percentage contributions
        factor_percentages = (factor_contributions / portfolio_variance) * 100

        # Create results
        factor_results = {}
        for i, name in enumerate(factor_names):
            factor_results[name] = {
                'exposure': float(portfolio_exposures[i]),
                'variance_contribution': float(factor_contributions[i]),
                'percentage_contribution': float(factor_percentages[i])
            }

        return self._create_result_dict(
            value={
                'portfolio_volatility': portfolio_volatility,
                'factor_contributions': factor_results,
                'total_percentage': float(np.sum(factor_percentages))
            },
            method='factor_attribution',
            parameters={
                'n_factors': len(factor_names),
                'n_assets': len(weights)
            }
        )

    def calculate_group_attribution(self,
                                    returns: Union[pd.DataFrame, np.ndarray],
                                    weights: Union[List, np.ndarray, pd.Series],
                                    groups: Union[List[str], pd.Series],
                                    asset_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Calculate risk attribution by groups (e.g., sectors, asset classes).

        Args:
            returns: Asset returns matrix
            weights: Portfolio weights
            groups: Group assignment for each asset
            asset_names: Optional names for assets

        Returns:
            Dictionary with group risk attribution
        """
        # Validate inputs
        if isinstance(returns, pd.DataFrame):
            asset_names = asset_names or returns.columns.tolist()
            returns_matrix = returns.values
        else:
            returns_matrix = np.array(returns)
            asset_names = asset_names or [f'Asset_{i+1}' for i in range(returns_matrix.shape[1])]

        weights = np.array(weights).flatten()

        if isinstance(groups, pd.Series):
            groups = groups.tolist()

        if len(groups) != len(weights):
            raise DataValidationError(
                f"Number of groups ({len(groups)}) must match number of assets ({len(weights)})"
            )

        # Calculate individual asset contributions
        asset_attribution = self.calculate(returns_matrix, weights, asset_names)
        asset_contributions = asset_attribution['value']['contributions']

        # Aggregate by group
        unique_groups = sorted(set(groups))
        group_results = {}

        for group in unique_groups:
            # Find assets in this group
            group_indices = [i for i, g in enumerate(groups) if g == group]
            group_assets = [asset_names[i] for i in group_indices]

            # Sum contributions
            group_weight = sum(weights[i] for i in group_indices)
            group_pct_contribution = sum(
                asset_contributions[asset_names[i]]['percentage_contribution']
                for i in group_indices
            )

            group_results[group] = {
                'weight': float(group_weight),
                'percentage_contribution': float(group_pct_contribution),
                'n_assets': len(group_assets),
                'assets': group_assets
            }

        return self._create_result_dict(
            value={
                'portfolio_volatility': asset_attribution['value']['portfolio_volatility'],
                'group_contributions': group_results,
                'total_percentage': sum(g['percentage_contribution'] for g in group_results.values())
            },
            method='group_attribution',
            parameters={
                'n_groups': len(unique_groups),
                'n_assets': len(weights)
            }
        )

    def calculate_concentration_metrics(self,
                                       returns: Union[pd.DataFrame, np.ndarray],
                                       weights: Union[List, np.ndarray, pd.Series]) -> Dict[str, Any]:
        """
        Calculate risk concentration metrics.

        Args:
            returns: Asset returns matrix
            weights: Portfolio weights

        Returns:
            Dictionary with concentration metrics
        """
        # Get risk attribution
        attribution = self.calculate(returns, weights)
        contributions = attribution['value']['contributions']

        # Extract percentage contributions
        pct_contributions = np.array([
            contrib['percentage_contribution']
            for contrib in contributions.values()
        ])

        # Herfindahl index for risk concentration
        herfindahl_index = np.sum((pct_contributions / 100) ** 2)

        # Effective number of assets (risk-based)
        effective_n_assets = 1 / herfindahl_index if herfindahl_index > 0 else 0

        # Maximum contribution
        max_contribution = np.max(pct_contributions)
        max_contributor = list(contributions.keys())[np.argmax(pct_contributions)]

        # Top 3 contributors
        sorted_indices = np.argsort(pct_contributions)[::-1]
        top_3_contribution = np.sum(pct_contributions[sorted_indices[:3]])

        return self._create_result_dict(
            value={
                'herfindahl_index': herfindahl_index,
                'effective_n_assets': effective_n_assets,
                'max_contribution': max_contribution,
                'max_contributor': max_contributor,
                'top_3_contribution': top_3_contribution
            },
            method='concentration_metrics',
            parameters={'n_assets': len(weights)},
            metadata={
                'interpretation': 'Lower Herfindahl = more diversified; Effective N = risk-based diversification'
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Return list of supported calculation methods."""
        return ['risk_attribution', 'factor_attribution', 'group_attribution', 'concentration_metrics']
