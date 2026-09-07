"""
Conditional Value at Risk (CVaR) Calculator
============================================

Calculates Conditional Value at Risk (CVaR), also known as Expected Shortfall (ES).
CVaR measures the expected loss given that the loss exceeds the VaR threshold.

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional
from scipy import stats

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    InsufficientDataError,
    ConfigurationError
)


class CVaRCalculator(BaseCalculator):
    """
    Conditional Value at Risk (CVaR) Calculator

    CVaR (also called Expected Shortfall) measures the expected loss
    in the worst (1-α)% of cases, where α is the confidence level.

    CVaR is a coherent risk measure and provides more information than VaR
    about the tail of the loss distribution.

    Methods:
        - historical: Historical simulation method
        - parametric: Parametric method (assumes normal distribution)
        - monte_carlo: Monte Carlo simulation

    Example:
        calculator = CVaRCalculator(precision=4)
        result = calculator.calculate(returns, confidence_level=0.95, method='historical')
        print(f"CVaR (95%): {result['value']}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize CVaR calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate (not used in CVaR but kept for consistency)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  returns: Union[List, np.ndarray, pd.Series],
                  confidence_level: float = 0.95,
                  method: str = 'historical',
                  time_horizon: int = 1,
                  n_simulations: int = 10000) -> Dict[str, Any]:
        """
        Calculate Conditional Value at Risk.

        Args:
            returns: Historical returns data
            confidence_level: Confidence level (e.g., 0.95 for 95% CVaR)
            method: Calculation method ('historical', 'parametric', 'monte_carlo')
            time_horizon: Time horizon in periods (default: 1)
            n_simulations: Number of simulations for Monte Carlo method

        Returns:
            Dictionary with CVaR value and metadata

        Raises:
            InsufficientDataError: If not enough data points
            ConfigurationError: If invalid parameters
            CalculationError: If calculation fails
        """
        # Validate inputs
        returns = self._validate_returns(returns, 'returns')
        confidence_level = self._validate_probability(confidence_level, 'confidence_level')

        if confidence_level <= 0.5:
            raise ConfigurationError(
                "Confidence level should be > 0.5 (typically 0.90, 0.95, or 0.99)",
                parameter='confidence_level'
            )

        # Check data sufficiency
        min_observations = 30 if method == 'historical' else 20
        if len(returns) < min_observations:
            raise InsufficientDataError(
                required=min_observations,
                provided=len(returns),
                calculation=f'CVaR ({method})'
            )

        # Validate method
        method = self.validate_method(method)

        try:
            # Calculate CVaR based on method
            if method == 'historical':
                cvar_value = self._historical_cvar(returns, confidence_level, time_horizon)
            elif method == 'parametric':
                cvar_value = self._parametric_cvar(returns, confidence_level, time_horizon)
            elif method == 'monte_carlo':
                cvar_value = self._monte_carlo_cvar(returns, confidence_level, time_horizon, n_simulations)
            else:
                raise ConfigurationError(f"Unknown method: {method}", parameter='method')

            # Create result
            return self._create_result_dict(
                value=abs(cvar_value),  # Return as positive value
                method=f'cvar_{method}',
                parameters={
                    'confidence_level': confidence_level,
                    'method': method,
                    'time_horizon': time_horizon,
                    'n_observations': len(returns),
                    'n_simulations': n_simulations if method == 'monte_carlo' else None
                },
                metadata={
                    'interpretation': f'Expected loss in the worst {(1-confidence_level)*100}% of cases',
                    'coherent_risk_measure': True,
                    'also_known_as': 'Expected Shortfall (ES)'
                }
            )

        except Exception as e:
            if isinstance(e, (InsufficientDataError, ConfigurationError)):
                raise
            raise CalculationError(str(e), calculation_type='CVaR')

    def _historical_cvar(self, returns: np.ndarray, confidence_level: float, time_horizon: int) -> float:
        """
        Calculate CVaR using historical simulation method.

        CVaR is the average of all losses that exceed the VaR threshold.
        """
        # Scale returns for time horizon
        if time_horizon > 1:
            returns = returns * np.sqrt(time_horizon)

        # Calculate VaR threshold
        var_threshold = np.percentile(returns, (1 - confidence_level) * 100)

        # CVaR is the mean of returns below the VaR threshold
        tail_losses = returns[returns <= var_threshold]

        if len(tail_losses) == 0:
            # If no losses exceed VaR, return VaR itself
            return var_threshold

        cvar = np.mean(tail_losses)

        return cvar

    def _parametric_cvar(self, returns: np.ndarray, confidence_level: float, time_horizon: int) -> float:
        """
        Calculate CVaR using parametric method.

        Assumes returns are normally distributed.
        For normal distribution: CVaR = μ - σ * φ(Φ^(-1)(α)) / (1-α)
        where φ is the PDF and Φ is the CDF of standard normal.
        """
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)

        # Z-score for the confidence level
        z = stats.norm.ppf(1 - confidence_level)

        # CVaR formula for normal distribution
        cvar = mean - std * stats.norm.pdf(z) / (1 - confidence_level)

        # Scale for time horizon
        if time_horizon > 1:
            cvar = cvar * np.sqrt(time_horizon)

        return cvar

    def _monte_carlo_cvar(self, returns: np.ndarray, confidence_level: float,
                          time_horizon: int, n_simulations: int) -> float:
        """
        Calculate CVaR using Monte Carlo simulation.

        Simulates future returns and calculates the average of the worst outcomes.
        """
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)

        # Generate random returns
        simulated_returns = np.random.normal(mean, std, n_simulations)

        # Scale for time horizon
        if time_horizon > 1:
            simulated_returns = simulated_returns * np.sqrt(time_horizon)

        # Calculate VaR threshold
        var_threshold = np.percentile(simulated_returns, (1 - confidence_level) * 100)

        # CVaR is the mean of simulated returns below VaR
        tail_losses = simulated_returns[simulated_returns <= var_threshold]

        if len(tail_losses) == 0:
            return var_threshold

        cvar = np.mean(tail_losses)

        return cvar

    def get_supported_methods(self) -> List[str]:
        """Return list of supported CVaR calculation methods."""
        return ['historical', 'parametric', 'monte_carlo']

    def calculate_with_var(self,
                          returns: Union[List, np.ndarray, pd.Series],
                          confidence_level: float = 0.95,
                          method: str = 'historical') -> Dict[str, Any]:
        """
        Calculate both VaR and CVaR together.

        Args:
            returns: Historical returns data
            confidence_level: Confidence level
            method: Calculation method

        Returns:
            Dictionary with both VaR and CVaR values
        """
        returns = self._validate_returns(returns, 'returns')

        # Calculate CVaR
        cvar_result = self.calculate(returns, confidence_level, method)

        # Calculate VaR for comparison
        if method == 'historical':
            var_value = np.percentile(returns, (1 - confidence_level) * 100)
        elif method == 'parametric':
            mean = np.mean(returns)
            std = np.std(returns, ddof=1)
            z = stats.norm.ppf(1 - confidence_level)
            var_value = mean + z * std
        else:  # monte_carlo
            mean = np.mean(returns)
            std = np.std(returns, ddof=1)
            simulated = np.random.normal(mean, std, 10000)
            var_value = np.percentile(simulated, (1 - confidence_level) * 100)

        return self._create_result_dict(
            value={
                'var': abs(var_value),
                'cvar': cvar_result['value'],
                'cvar_var_ratio': cvar_result['value'] / abs(var_value) if var_value != 0 else None
            },
            method=f'var_cvar_{method}',
            parameters={
                'confidence_level': confidence_level,
                'method': method
            },
            metadata={
                'interpretation': 'CVaR is always >= VaR; ratio shows tail risk severity'
            }
        )

    def calculate_multiple_confidence_levels(self,
                                            returns: Union[List, np.ndarray, pd.Series],
                                            confidence_levels: List[float] = [0.90, 0.95, 0.99],
                                            method: str = 'historical') -> Dict[str, Any]:
        """
        Calculate CVaR for multiple confidence levels.

        Args:
            returns: Historical returns data
            confidence_levels: List of confidence levels
            method: Calculation method

        Returns:
            Dictionary with CVaR values for each confidence level
        """
        results = {}

        for cl in confidence_levels:
            result = self.calculate(returns, confidence_level=cl, method=method)
            results[f'cvar_{int(cl*100)}'] = result['value']

        return self._create_result_dict(
            value=results,
            method=f'cvar_{method}_multiple',
            parameters={
                'confidence_levels': confidence_levels,
                'method': method
            }
        )
