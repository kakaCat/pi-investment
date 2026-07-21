"""
Factor Exposure Calculator
===========================

Calculate factor exposures and analyze factor contributions to portfolio returns.

Provides tools for:
    - Factor exposure calculation
    - Factor contribution analysis
    - Factor tilts and biases
    - Active factor exposures vs benchmark

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Union, List
from scipy import stats

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    DataValidationError,
    InsufficientDataError,
    CalculationError
)


class FactorExposureCalculator(BaseCalculator):
    """
    Factor Exposure Calculator

    Calculates and analyzes factor exposures for portfolios and individual assets.

    Features:
        - Calculate factor exposures from returns and factor data
        - Decompose returns into factor contributions
        - Analyze active exposures vs benchmark
        - Calculate factor tilts and biases

    Example:
        calculator = FactorExposureCalculator()
        result = calculator.calculate_exposure(
            asset_returns=returns,
            factor_returns=factors
        )
        print(f"Factor Exposures: {result['value']['exposures']}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize factor exposure calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Default risk-free rate
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Main calculation method (delegates to calculate_exposure).

        This implements the abstract method from BaseCalculator.
        """
        return self.calculate_exposure(*args, **kwargs)

    def calculate_exposure(self,
                           asset_returns: Union[np.ndarray, pd.Series],
                           factor_returns: pd.DataFrame,
                           method: str = 'regression') -> Dict[str, Any]:
        """
        Calculate factor exposures for an asset.

        Args:
            asset_returns: Asset return series
            factor_returns: DataFrame of factor returns (time x factors)
            method: Method for calculating exposures ('regression' or 'correlation')

        Returns:
            Dictionary containing:
                - exposures: Factor exposure values
                - t_stats: t-statistics for exposures
                - p_values: p-values for exposures
                - r_squared: R-squared of regression

        Raises:
            DataValidationError: If input data is invalid
            InsufficientDataError: If not enough observations
        """
        # Validate inputs
        asset_returns = self._validate_returns(asset_returns, 'asset_returns')

        if factor_returns.empty:
            raise DataValidationError("factor_returns DataFrame is empty", field_name="factor_returns")

        # Align data
        if isinstance(asset_returns, pd.Series):
            common_index = asset_returns.index.intersection(factor_returns.index)
        else:
            # Convert to series with factor_returns index
            if len(asset_returns) != len(factor_returns):
                raise DataValidationError(
                    f"Length mismatch: asset_returns ({len(asset_returns)}) vs factor_returns ({len(factor_returns)})",
                    field_name="length_mismatch"
                )
            asset_returns = pd.Series(asset_returns, index=factor_returns.index)
            common_index = factor_returns.index

        if len(common_index) < 30:
            raise InsufficientDataError(
                required=30,
                provided=len(common_index),
                calculation="factor_exposure"
            )

        asset_returns = asset_returns[common_index]
        factor_returns = factor_returns.loc[common_index]

        if method == 'regression':
            # Time-series regression: r_t = α + Σ(β_i * f_i,t) + ε_t
            X = factor_returns.values
            y = asset_returns.values

            # Add intercept
            X_with_intercept = np.column_stack([np.ones(len(X)), X])

            # OLS regression
            from scipy.linalg import lstsq
            result = lstsq(X_with_intercept, y)
            coeffs = result[0]
            rank = result[2]

            alpha = coeffs[0]
            betas = coeffs[1:]

            # Calculate statistics
            y_pred = X_with_intercept @ coeffs
            residuals = y - y_pred

            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)

            if ss_tot == 0:
                r_squared = 0.0
            else:
                r_squared = 1 - (ss_res / ss_tot)

            # Standard errors
            n = len(y)
            k = X_with_intercept.shape[1]
            mse = ss_res / (n - k)

            XtX_inv = np.linalg.inv(X_with_intercept.T @ X_with_intercept)
            var_covar = mse * XtX_inv
            std_errors = np.sqrt(np.diag(var_covar))

            # t-statistics and p-values
            t_stats = coeffs / std_errors
            df = n - k
            p_values = 2 * (1 - stats.t.cdf(np.abs(t_stats), df))

            exposures = pd.Series(betas, index=factor_returns.columns)
            t_stats_dict = pd.Series(t_stats[1:], index=factor_returns.columns)
            p_values_dict = pd.Series(p_values[1:], index=factor_returns.columns)

            result_value = {
                'exposures': exposures.to_dict(),
                'alpha': float(alpha),
                't_stats': t_stats_dict.to_dict(),
                'p_values': p_values_dict.to_dict(),
                'r_squared': float(r_squared),
                'alpha_t_stat': float(t_stats[0]),
                'alpha_p_value': float(p_values[0])
            }

        elif method == 'correlation':
            # Simple correlation-based exposures
            correlations = {}
            for factor in factor_returns.columns:
                corr, p_val = stats.pearsonr(asset_returns, factor_returns[factor])
                correlations[factor] = {
                    'exposure': corr,
                    'p_value': p_val
                }

            result_value = {
                'exposures': {k: v['exposure'] for k, v in correlations.items()},
                'p_values': {k: v['p_value'] for k, v in correlations.items()}
            }

        else:
            raise DataValidationError(
                f"Unknown method: {method}. Use 'regression' or 'correlation'",
                field_name="method"
            )

        return self._create_result_dict(
            value=result_value,
            method=f'factor_exposure_{method}',
            parameters={
                'n_observations': len(common_index),
                'n_factors': len(factor_returns.columns),
                'method': method
            },
            metadata={
                'factors': list(factor_returns.columns)
            }
        )

    def calculate_factor_contribution(self,
                                       portfolio_returns: Union[np.ndarray, pd.Series],
                                       factor_returns: pd.DataFrame,
                                       factor_exposures: Optional[pd.Series] = None) -> Dict[str, Any]:
        """
        Decompose portfolio returns into factor contributions.

        Args:
            portfolio_returns: Portfolio return series
            factor_returns: Factor return series
            factor_exposures: Pre-calculated factor exposures (if None, will calculate)

        Returns:
            Dictionary containing factor contributions to returns
        """
        # Validate inputs
        portfolio_returns = self._validate_returns(portfolio_returns, 'portfolio_returns')

        if factor_returns.empty:
            raise DataValidationError("factor_returns DataFrame is empty", field_name="factor_returns")

        # Calculate exposures if not provided
        if factor_exposures is None:
            exposure_result = self.calculate_exposure(portfolio_returns, factor_returns)
            factor_exposures = pd.Series(exposure_result['value']['exposures'])

        # Align data
        if isinstance(portfolio_returns, pd.Series):
            common_index = portfolio_returns.index.intersection(factor_returns.index)
        else:
            if len(portfolio_returns) != len(factor_returns):
                raise DataValidationError(
                    "Length mismatch between portfolio_returns and factor_returns",
                    field_name="length_mismatch"
                )
            portfolio_returns = pd.Series(portfolio_returns, index=factor_returns.index)
            common_index = factor_returns.index

        portfolio_returns = portfolio_returns[common_index]
        factor_returns = factor_returns.loc[common_index]

        # Calculate factor contributions: contribution_i = β_i * f_i
        factor_contributions = pd.DataFrame(index=common_index, columns=factor_returns.columns)

        for factor in factor_returns.columns:
            if factor in factor_exposures.index:
                factor_contributions[factor] = factor_exposures[factor] * factor_returns[factor]
            else:
                factor_contributions[factor] = 0.0

        # Total factor contribution
        total_factor_contribution = factor_contributions.sum(axis=1)

        # Specific return (residual)
        specific_return = portfolio_returns - total_factor_contribution

        # Summary statistics
        avg_contributions = factor_contributions.mean()
        contribution_volatility = factor_contributions.std()

        # Percentage contribution to total return
        total_return = portfolio_returns.sum()
        if total_return != 0:
            pct_contributions = (factor_contributions.sum() / total_return * 100)
        else:
            pct_contributions = pd.Series(0, index=factor_returns.columns)

        result_value = {
            'factor_contributions': factor_contributions.to_dict(),
            'average_contributions': avg_contributions.to_dict(),
            'contribution_volatility': contribution_volatility.to_dict(),
            'percentage_contributions': pct_contributions.to_dict(),
            'total_factor_contribution': float(total_factor_contribution.sum()),
            'specific_return': float(specific_return.sum()),
            'total_return': float(total_return)
        }

        return self._create_result_dict(
            value=result_value,
            method='factor_contribution',
            parameters={
                'n_observations': len(common_index),
                'n_factors': len(factor_returns.columns)
            }
        )

    def calculate_active_exposure(self,
                                   portfolio_returns: Union[np.ndarray, pd.Series],
                                   benchmark_returns: Union[np.ndarray, pd.Series],
                                   factor_returns: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate active factor exposures vs benchmark.

        Args:
            portfolio_returns: Portfolio return series
            benchmark_returns: Benchmark return series
            factor_returns: Factor return series

        Returns:
            Dictionary containing active exposures and statistics
        """
        # Calculate portfolio exposures
        portfolio_exposure = self.calculate_exposure(portfolio_returns, factor_returns)
        portfolio_betas = pd.Series(portfolio_exposure['value']['exposures'])

        # Calculate benchmark exposures
        benchmark_exposure = self.calculate_exposure(benchmark_returns, factor_returns)
        benchmark_betas = pd.Series(benchmark_exposure['value']['exposures'])

        # Active exposures
        active_exposures = portfolio_betas - benchmark_betas

        # Calculate active return
        portfolio_returns = self._validate_returns(portfolio_returns, 'portfolio_returns')
        benchmark_returns = self._validate_returns(benchmark_returns, 'benchmark_returns')

        if isinstance(portfolio_returns, pd.Series) and isinstance(benchmark_returns, pd.Series):
            common_index = portfolio_returns.index.intersection(benchmark_returns.index)
            active_returns = portfolio_returns[common_index] - benchmark_returns[common_index]
        else:
            if len(portfolio_returns) != len(benchmark_returns):
                raise DataValidationError(
                    "Length mismatch between portfolio and benchmark returns",
                    field_name="length_mismatch"
                )
            active_returns = portfolio_returns - benchmark_returns

        # Active return statistics
        avg_active_return = np.mean(active_returns)
        active_volatility = np.std(active_returns)
        information_ratio = avg_active_return / active_volatility if active_volatility > 0 else 0.0

        result_value = {
            'portfolio_exposures': portfolio_betas.to_dict(),
            'benchmark_exposures': benchmark_betas.to_dict(),
            'active_exposures': active_exposures.to_dict(),
            'average_active_return': float(avg_active_return),
            'active_volatility': float(active_volatility),
            'information_ratio': float(information_ratio),
            'tracking_error': float(active_volatility)
        }

        return self._create_result_dict(
            value=result_value,
            method='active_exposure',
            parameters={
                'n_factors': len(factor_returns.columns)
            }
        )

    def calculate_factor_tilts(self,
                                factor_exposures: pd.Series,
                                benchmark_exposures: Optional[pd.Series] = None) -> Dict[str, Any]:
        """
        Calculate factor tilts (deviations from neutral or benchmark).

        Args:
            factor_exposures: Portfolio factor exposures
            benchmark_exposures: Benchmark exposures (if None, use zero as neutral)

        Returns:
            Dictionary containing factor tilts and classifications
        """
        if benchmark_exposures is None:
            # Use zero as neutral
            tilts = factor_exposures
        else:
            # Calculate relative to benchmark
            tilts = factor_exposures - benchmark_exposures

        # Classify tilts
        tilt_classifications = {}
        for factor, tilt in tilts.items():
            if abs(tilt) < 0.1:
                classification = 'neutral'
            elif tilt > 0.5:
                classification = 'strong_positive'
            elif tilt > 0.1:
                classification = 'positive'
            elif tilt < -0.5:
                classification = 'strong_negative'
            else:
                classification = 'negative'

            tilt_classifications[factor] = classification

        # Summary statistics
        max_tilt = tilts.abs().max()
        max_tilt_factor = tilts.abs().idxmax()
        avg_abs_tilt = tilts.abs().mean()

        result_value = {
            'tilts': tilts.to_dict(),
            'classifications': tilt_classifications,
            'max_tilt': float(max_tilt),
            'max_tilt_factor': max_tilt_factor,
            'average_absolute_tilt': float(avg_abs_tilt)
        }

        return self._create_result_dict(
            value=result_value,
            method='factor_tilts',
            parameters={
                'n_factors': len(factor_exposures),
                'has_benchmark': benchmark_exposures is not None
            }
        )

    def calculate_rolling_exposure(self,
                                    asset_returns: pd.Series,
                                    factor_returns: pd.DataFrame,
                                    window: int = 60) -> pd.DataFrame:
        """
        Calculate rolling factor exposures over time.

        Args:
            asset_returns: Asset return series
            factor_returns: Factor return series
            window: Rolling window size (number of periods)

        Returns:
            DataFrame of rolling factor exposures
        """
        if len(asset_returns) < window:
            raise InsufficientDataError(
                required=window,
                provided=len(asset_returns),
                calculation="rolling_exposure"
            )

        # Align data
        common_index = asset_returns.index.intersection(factor_returns.index)
        asset_returns = asset_returns[common_index]
        factor_returns = factor_returns.loc[common_index]

        rolling_exposures = []

        for i in range(window, len(common_index) + 1):
            window_returns = asset_returns.iloc[i - window:i]
            window_factors = factor_returns.iloc[i - window:i]

            try:
                exposure_result = self.calculate_exposure(window_returns, window_factors)
                exposures = exposure_result['value']['exposures']
                exposures['date'] = common_index[i - 1]
                rolling_exposures.append(exposures)
            except Exception:
                # Skip if calculation fails
                continue

        if not rolling_exposures:
            raise CalculationError(
                "Failed to calculate rolling exposures",
                calculation_type="rolling_exposure"
            )

        rolling_df = pd.DataFrame(rolling_exposures)
        rolling_df.set_index('date', inplace=True)

        return rolling_df
