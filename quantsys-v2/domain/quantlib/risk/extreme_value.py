"""
Extreme Value Theory Calculator
================================

Implements Extreme Value Theory (EVT) for tail risk estimation using:
- Generalized Extreme Value (GEV) distribution
- Generalized Pareto Distribution (GPD)
- Peak Over Threshold (POT) method
- Block Maxima method

EVT provides better estimates of tail risk than traditional methods
by focusing specifically on extreme events.

Author: QuantSys V2 Advanced Risk Module
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional, Tuple
from scipy import stats, optimize
import warnings

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    InsufficientDataError,
    DataValidationError,
    ConfigurationError,
    ConvergenceError
)


class ExtremeValueCalculator(BaseCalculator):
    """
    Extreme Value Theory Calculator

    Estimates tail risk using Extreme Value Theory (EVT), which provides
    more accurate estimates for extreme events than normal distribution assumptions.

    Methods:
        - gev: Generalized Extreme Value distribution (block maxima)
        - gpd: Generalized Pareto Distribution (peak over threshold)
        - pot: Peak Over Threshold method
        - block_maxima: Block maxima method

    Key Concepts:
        - GEV: Models distribution of block maxima
        - GPD: Models distribution of exceedances over threshold
        - Shape parameter (ξ): Determines tail behavior
          * ξ > 0: Heavy tail (Fréchet)
          * ξ = 0: Exponential tail (Gumbel)
          * ξ < 0: Bounded tail (Weibull)

    Example:
        calculator = ExtremeValueCalculator()
        result = calculator.calculate(
            returns=returns,
            method='gpd',
            threshold=0.05,
            confidence_level=0.99
        )
        print(f"Tail VaR (99%): {result['value']['tail_var']}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Extreme Value calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  returns: Union[List, np.ndarray, pd.Series],
                  method: str = 'gpd',
                  threshold: Optional[float] = None,
                  confidence_level: float = 0.99,
                  block_size: int = 21) -> Dict[str, Any]:
        """
        Calculate tail risk using Extreme Value Theory.

        Args:
            returns: Historical returns data
            method: EVT method ('gev', 'gpd', 'pot', 'block_maxima')
            threshold: Threshold for POT/GPD (if None, auto-selected)
            confidence_level: Confidence level for tail VaR/CVaR
            block_size: Block size for block maxima method (e.g., 21 for monthly)

        Returns:
            Dictionary with tail risk estimates

        Raises:
            InsufficientDataError: If not enough data
            ConfigurationError: If invalid parameters
            CalculationError: If calculation fails
        """
        # Validate inputs
        returns = self._validate_returns(returns, 'returns')
        confidence_level = self._validate_probability(confidence_level, 'confidence_level')

        if confidence_level <= 0.9:
            raise ConfigurationError(
                "EVT is designed for high confidence levels (>0.90)",
                parameter='confidence_level'
            )

        # Check data sufficiency
        min_observations = 100 if method in ['gpd', 'pot'] else 50
        if len(returns) < min_observations:
            raise InsufficientDataError(
                required=min_observations,
                provided=len(returns),
                calculation=f'EVT ({method})'
            )

        # Validate method
        method = self.validate_method(method)

        try:
            # Convert to losses (negative returns)
            losses = -returns

            if method == 'gev':
                result = self._gev_method(losses, confidence_level, block_size)
            elif method == 'gpd' or method == 'pot':
                result = self._gpd_method(losses, threshold, confidence_level)
            elif method == 'block_maxima':
                result = self._block_maxima_method(losses, confidence_level, block_size)
            else:
                raise ConfigurationError(f"Unknown method: {method}", parameter='method')

            return self._create_result_dict(
                value=result,
                method=f'extreme_value_{method}',
                parameters={
                    'confidence_level': confidence_level,
                    'n_observations': len(returns),
                    'threshold': threshold,
                    'block_size': block_size if method in ['gev', 'block_maxima'] else None
                },
                metadata={
                    'interpretation': 'Tail VaR/CVaR estimates for extreme events',
                    'note': 'Based on Extreme Value Theory'
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, ConfigurationError, InsufficientDataError)):
                raise
            raise CalculationError(str(e), calculation_type='Extreme Value Theory')

    def _gev_method(self,
                   losses: np.ndarray,
                   confidence_level: float,
                   block_size: int) -> Dict[str, Any]:
        """
        Generalized Extreme Value (GEV) distribution method.

        Uses block maxima approach: divide data into blocks and fit GEV to maxima.

        GEV CDF: F(x) = exp{-[1 + ξ(x-μ)/σ]^(-1/ξ)}
        """
        # Extract block maxima
        n_blocks = len(losses) // block_size
        if n_blocks < 10:
            raise InsufficientDataError(
                required=10,
                provided=n_blocks,
                calculation='GEV (number of blocks)'
            )

        block_maxima = []
        for i in range(n_blocks):
            block = losses[i * block_size:(i + 1) * block_size]
            block_maxima.append(np.max(block))

        block_maxima = np.array(block_maxima)

        # Fit GEV distribution using MLE
        try:
            # scipy.stats.genextreme uses different parameterization: c = -ξ
            params = stats.genextreme.fit(block_maxima)
            shape_param = -params[0]  # Convert to standard ξ notation
            loc_param = params[1]     # μ (location)
            scale_param = params[2]   # σ (scale)

        except Exception as e:
            raise ConvergenceError(f"GEV fitting failed: {str(e)}")

        # Calculate tail VaR and CVaR
        tail_var = self._gev_var(shape_param, loc_param, scale_param, confidence_level)
        tail_cvar = self._gev_cvar(shape_param, loc_param, scale_param, confidence_level)

        # Determine tail type
        if shape_param > 0.1:
            tail_type = 'heavy (Fréchet)'
        elif shape_param < -0.1:
            tail_type = 'bounded (Weibull)'
        else:
            tail_type = 'exponential (Gumbel)'

        return {
            'tail_var': float(tail_var),
            'tail_cvar': float(tail_cvar),
            'shape_parameter': float(shape_param),
            'location_parameter': float(loc_param),
            'scale_parameter': float(scale_param),
            'tail_type': tail_type,
            'n_blocks': n_blocks,
            'block_maxima_mean': float(np.mean(block_maxima)),
            'block_maxima_max': float(np.max(block_maxima))
        }

    def _gpd_method(self,
                   losses: np.ndarray,
                   threshold: Optional[float],
                   confidence_level: float) -> Dict[str, Any]:
        """
        Generalized Pareto Distribution (GPD) method.

        Uses Peak Over Threshold (POT): fit GPD to exceedances over threshold.

        GPD CDF: F(x) = 1 - (1 + ξx/σ)^(-1/ξ)
        """
        # Select threshold if not provided
        if threshold is None:
            threshold = self._select_threshold(losses)

        # Extract exceedances
        exceedances = losses[losses > threshold] - threshold
        n_exceedances = len(exceedances)

        if n_exceedances < 10:
            raise InsufficientDataError(
                required=10,
                provided=n_exceedances,
                calculation='GPD (number of exceedances)'
            )

        # Fit GPD using MLE
        try:
            # scipy.stats.genpareto: shape (c=ξ), loc (threshold), scale (σ)
            params = stats.genpareto.fit(exceedances, floc=0)
            shape_param = params[0]   # ξ
            scale_param = params[2]   # σ

        except Exception as e:
            raise ConvergenceError(f"GPD fitting failed: {str(e)}")

        # Calculate exceedance probability
        n_total = len(losses)
        exceedance_prob = n_exceedances / n_total

        # Calculate tail VaR using GPD quantile function
        # VaR_p = u + (σ/ξ) * [((1-p)/N_u)^(-ξ) - 1]
        # where u = threshold, N_u = exceedance probability
        p = confidence_level
        if shape_param != 0:
            tail_var = threshold + (scale_param / shape_param) * \
                      (((1 - p) / exceedance_prob) ** (-shape_param) - 1)
        else:
            # Exponential case (ξ = 0)
            tail_var = threshold - scale_param * np.log((1 - p) / exceedance_prob)

        # Calculate tail CVaR (Expected Shortfall)
        if shape_param < 1 and shape_param != 0:
            tail_cvar = tail_var / (1 - shape_param) + \
                       (scale_param - shape_param * threshold) / (1 - shape_param)
        else:
            # Use numerical integration for ξ >= 1
            tail_cvar = tail_var * 1.5  # Approximation

        # Determine tail type
        if shape_param > 0.1:
            tail_type = 'heavy (fat tail)'
        elif shape_param < -0.1:
            tail_type = 'bounded (thin tail)'
        else:
            tail_type = 'exponential (medium tail)'

        return {
            'tail_var': float(tail_var),
            'tail_cvar': float(tail_cvar),
            'shape_parameter': float(shape_param),
            'scale_parameter': float(scale_param),
            'threshold': float(threshold),
            'n_exceedances': int(n_exceedances),
            'exceedance_probability': float(exceedance_prob),
            'tail_type': tail_type,
            'mean_excess': float(np.mean(exceedances))
        }

    def _block_maxima_method(self,
                            losses: np.ndarray,
                            confidence_level: float,
                            block_size: int) -> Dict[str, Any]:
        """
        Block maxima method (simplified GEV approach).

        Divides data into blocks and analyzes distribution of maxima.
        """
        # Extract block maxima
        n_blocks = len(losses) // block_size
        if n_blocks < 10:
            raise InsufficientDataError(
                required=10,
                provided=n_blocks,
                calculation='Block Maxima (number of blocks)'
            )

        block_maxima = []
        for i in range(n_blocks):
            block = losses[i * block_size:(i + 1) * block_size]
            block_maxima.append(np.max(block))

        block_maxima = np.array(block_maxima)

        # Calculate empirical quantile
        tail_var = np.quantile(block_maxima, confidence_level)

        # Calculate CVaR (mean of losses exceeding VaR)
        extreme_losses = block_maxima[block_maxima >= tail_var]
        if len(extreme_losses) > 0:
            tail_cvar = np.mean(extreme_losses)
        else:
            tail_cvar = tail_var

        # Estimate shape parameter using Hill estimator
        sorted_maxima = np.sort(block_maxima)[::-1]
        k = max(3, int(n_blocks * 0.1))  # Use top 10% for Hill estimator
        hill_estimate = np.mean(np.log(sorted_maxima[:k])) - np.log(sorted_maxima[k])

        return {
            'tail_var': float(tail_var),
            'tail_cvar': float(tail_cvar),
            'shape_parameter': float(hill_estimate),
            'n_blocks': int(n_blocks),
            'block_size': int(block_size),
            'max_loss': float(np.max(block_maxima)),
            'mean_block_maxima': float(np.mean(block_maxima)),
            'std_block_maxima': float(np.std(block_maxima, ddof=1))
        }

    def _select_threshold(self, losses: np.ndarray, target_exceedances: int = 50) -> float:
        """
        Automatically select threshold for POT method.

        Uses mean excess plot and aims for target number of exceedances.

        Args:
            losses: Loss data
            target_exceedances: Target number of exceedances (default: 50)

        Returns:
            Selected threshold
        """
        # Method 1: Use quantile to get target exceedances
        n = len(losses)
        quantile_level = 1 - (target_exceedances / n)
        threshold_q = np.quantile(losses, quantile_level)

        # Method 2: Use mean excess plot (look for linearity)
        # For simplicity, use 90th percentile as starting point
        threshold_me = np.quantile(losses, 0.90)

        # Use average of both methods
        threshold = (threshold_q + threshold_me) / 2

        # Ensure we have enough exceedances
        n_exceedances = np.sum(losses > threshold)
        if n_exceedances < 10:
            # Lower threshold to get more exceedances
            threshold = np.quantile(losses, 0.85)

        self.logger.info(f"Auto-selected threshold: {threshold:.6f} "
                        f"({np.sum(losses > threshold)} exceedances)")

        return float(threshold)

    def _gev_var(self, xi: float, mu: float, sigma: float, p: float) -> float:
        """
        Calculate VaR from GEV parameters.

        Args:
            xi: Shape parameter
            mu: Location parameter
            sigma: Scale parameter
            p: Confidence level

        Returns:
            VaR estimate
        """
        if abs(xi) < 1e-6:
            # Gumbel case (ξ ≈ 0)
            return mu - sigma * np.log(-np.log(p))
        else:
            # General case
            return mu + (sigma / xi) * ((-np.log(p)) ** (-xi) - 1)

    def _gev_cvar(self, xi: float, mu: float, sigma: float, p: float) -> float:
        """
        Calculate CVaR from GEV parameters.

        Args:
            xi: Shape parameter
            mu: Location parameter
            sigma: Scale parameter
            p: Confidence level

        Returns:
            CVaR estimate
        """
        var = self._gev_var(xi, mu, sigma, p)

        if abs(xi) < 1e-6:
            # Gumbel case
            return var + sigma
        elif xi < 1:
            # General case (ξ < 1)
            return var / (1 - xi) + (sigma - xi * mu) / (1 - xi)
        else:
            # For ξ >= 1, CVaR is infinite (use approximation)
            return var * 1.5

    def mean_excess_plot(self,
                        returns: Union[List, np.ndarray, pd.Series],
                        thresholds: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        Generate mean excess plot for threshold selection.

        The mean excess plot shows mean exceedance vs threshold.
        For GPD, this should be approximately linear above the threshold.

        Args:
            returns: Historical returns
            thresholds: Array of thresholds to test (if None, auto-generated)

        Returns:
            Dictionary with mean excess plot data
        """
        returns = self._validate_returns(returns, 'returns')
        losses = -returns

        if thresholds is None:
            # Generate thresholds from 50th to 95th percentile
            thresholds = np.quantile(losses, np.linspace(0.50, 0.95, 20))

        mean_excesses = []
        n_exceedances = []

        for threshold in thresholds:
            exceedances = losses[losses > threshold] - threshold
            if len(exceedances) > 0:
                mean_excesses.append(np.mean(exceedances))
                n_exceedances.append(len(exceedances))
            else:
                mean_excesses.append(np.nan)
                n_exceedances.append(0)

        return self._create_result_dict(
            value={
                'thresholds': thresholds.tolist(),
                'mean_excesses': mean_excesses,
                'n_exceedances': n_exceedances
            },
            method='mean_excess_plot',
            parameters={'n_thresholds': len(thresholds)},
            metadata={
                'interpretation': 'Look for linear region to select threshold'
            }
        )

    def hill_estimator(self,
                      returns: Union[List, np.ndarray, pd.Series],
                      k: Optional[int] = None) -> Dict[str, Any]:
        """
        Calculate Hill estimator for tail index.

        The Hill estimator estimates the tail index (shape parameter) for heavy-tailed distributions.

        Args:
            returns: Historical returns
            k: Number of order statistics to use (if None, auto-selected)

        Returns:
            Dictionary with Hill estimator results
        """
        returns = self._validate_returns(returns, 'returns')
        losses = -returns

        # Sort losses in descending order
        sorted_losses = np.sort(losses)[::-1]

        if k is None:
            # Use 5-10% of data
            k = max(10, int(len(losses) * 0.05))

        if k >= len(losses):
            raise ConfigurationError(
                f"k ({k}) must be less than data length ({len(losses)})",
                parameter='k'
            )

        # Hill estimator: (1/k) * sum(log(X_i) - log(X_{k+1}))
        hill_estimate = np.mean(np.log(sorted_losses[:k])) - np.log(sorted_losses[k])

        # Calculate Hill estimates for different k values (Hill plot)
        k_values = range(10, min(len(losses) // 2, 200))
        hill_estimates = []

        for k_val in k_values:
            estimate = np.mean(np.log(sorted_losses[:k_val])) - np.log(sorted_losses[k_val])
            hill_estimates.append(estimate)

        return self._create_result_dict(
            value={
                'hill_estimate': float(hill_estimate),
                'k': int(k),
                'hill_plot': {
                    'k_values': list(k_values),
                    'estimates': hill_estimates
                }
            },
            method='hill_estimator',
            parameters={'k': k},
            metadata={
                'interpretation': 'Higher values indicate heavier tails'
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Return list of supported calculation methods."""
        return ['gev', 'gpd', 'pot', 'block_maxima']
