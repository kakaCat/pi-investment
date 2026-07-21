"""
Value at Risk (VaR) Calculator
===============================

Calculates Value at Risk using multiple methods:
- Historical simulation
- Parametric (variance-covariance)
- Monte Carlo simulation

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


class VaRCalculator(BaseCalculator):
    """
    Value at Risk (VaR) Calculator

    VaR estimates the maximum potential loss over a given time horizon
    at a specified confidence level.

    Methods:
        - historical: Historical simulation method
        - parametric: Variance-covariance method (assumes normal distribution)
        - monte_carlo: Monte Carlo simulation
        - cornish_fisher: Cornish-Fisher expansion (accounts for skewness/kurtosis)

    Example:
        calculator = VaRCalculator(precision=4)
        result = calculator.calculate(returns, confidence_level=0.95, method='historical')
        print(f"VaR (95%): {result['value']}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize VaR calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate (not used in VaR but kept for consistency)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  returns: Union[List, np.ndarray, pd.Series],
                  confidence_level: float = 0.95,
                  method: str = 'historical',
                  time_horizon: int = 1,
                  n_simulations: int = 10000) -> Dict[str, Any]:
        """
        Calculate Value at Risk.

        Args:
            returns: Historical returns data
            confidence_level: Confidence level (e.g., 0.95 for 95% VaR)
            method: Calculation method ('historical', 'parametric', 'monte_carlo', 'cornish_fisher')
            time_horizon: Time horizon in periods (default: 1)
            n_simulations: Number of simulations for Monte Carlo method

        Returns:
            Dictionary with VaR value and metadata

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
                calculation=f'VaR ({method})'
            )

        # Validate method
        method = self.validate_method(method)

        try:
            # Calculate VaR based on method
            if method == 'historical':
                var_value = self._historical_var(returns, confidence_level, time_horizon)
            elif method == 'parametric':
                var_value = self._parametric_var(returns, confidence_level, time_horizon)
            elif method == 'monte_carlo':
                var_value = self._monte_carlo_var(returns, confidence_level, time_horizon, n_simulations)
            elif method == 'cornish_fisher':
                var_value = self._cornish_fisher_var(returns, confidence_level, time_horizon)
            else:
                raise ConfigurationError(f"Unknown method: {method}", parameter='method')

            # Create result
            return self._create_result_dict(
                value=abs(var_value),  # Return as positive value
                method=f'var_{method}',
                parameters={
                    'confidence_level': confidence_level,
                    'method': method,
                    'time_horizon': time_horizon,
                    'n_observations': len(returns),
                    'n_simulations': n_simulations if method == 'monte_carlo' else None
                },
                metadata={
                    'interpretation': f'{confidence_level*100}% confidence that loss will not exceed this value',
                    'percentile': (1 - confidence_level) * 100
                }
            )

        except Exception as e:
            if isinstance(e, (InsufficientDataError, ConfigurationError)):
                raise
            raise CalculationError(str(e), calculation_type='VaR')

    def _historical_var(self, returns: np.ndarray, confidence_level: float, time_horizon: int) -> float:
        """
        Calculate VaR using historical simulation method.

        This is a non-parametric method that uses the actual distribution of returns.
        """
        # Scale returns for time horizon
        if time_horizon > 1:
            returns = returns * np.sqrt(time_horizon)

        # Calculate VaR as the percentile
        var = np.percentile(returns, (1 - confidence_level) * 100)

        return var

    def _parametric_var(self, returns: np.ndarray, confidence_level: float, time_horizon: int) -> float:
        """
        Calculate VaR using parametric (variance-covariance) method.

        Assumes returns are normally distributed.
        """
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)

        # Z-score for the confidence level
        z_score = stats.norm.ppf(1 - confidence_level)

        # VaR calculation
        var = mean + z_score * std

        # Scale for time horizon
        if time_horizon > 1:
            var = var * np.sqrt(time_horizon)

        return var

    def _monte_carlo_var(self, returns: np.ndarray, confidence_level: float,
                         time_horizon: int, n_simulations: int) -> float:
        """
        Calculate VaR using Monte Carlo simulation.

        Simulates future returns based on historical mean and volatility.
        """
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)

        # Generate random returns
        simulated_returns = np.random.normal(mean, std, n_simulations)

        # Scale for time horizon
        if time_horizon > 1:
            simulated_returns = simulated_returns * np.sqrt(time_horizon)

        # Calculate VaR as percentile of simulated returns
        var = np.percentile(simulated_returns, (1 - confidence_level) * 100)

        return var

    def _cornish_fisher_var(self, returns: np.ndarray, confidence_level: float, time_horizon: int) -> float:
        """
        Calculate VaR using Cornish-Fisher expansion.

        Adjusts for skewness and kurtosis in the return distribution.
        """
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        skew = stats.skew(returns)
        kurt = stats.kurtosis(returns)

        # Z-score for the confidence level
        z = stats.norm.ppf(1 - confidence_level)

        # Cornish-Fisher adjustment
        z_cf = (z +
                (z**2 - 1) * skew / 6 +
                (z**3 - 3*z) * kurt / 24 -
                (2*z**3 - 5*z) * skew**2 / 36)

        # VaR calculation
        var = mean + z_cf * std

        # Scale for time horizon
        if time_horizon > 1:
            var = var * np.sqrt(time_horizon)

        return var

    def get_supported_methods(self) -> List[str]:
        """Return list of supported VaR calculation methods."""
        return ['historical', 'parametric', 'monte_carlo', 'cornish_fisher']

    def calculate_multiple_confidence_levels(self,
                                            returns: Union[List, np.ndarray, pd.Series],
                                            confidence_levels: List[float] = [0.90, 0.95, 0.99],
                                            method: str = 'historical') -> Dict[str, Any]:
        """
        Calculate VaR for multiple confidence levels.

        Args:
            returns: Historical returns data
            confidence_levels: List of confidence levels
            method: Calculation method

        Returns:
            Dictionary with VaR values for each confidence level
        """
        results = {}

        for cl in confidence_levels:
            result = self.calculate(returns, confidence_level=cl, method=method)
            results[f'var_{int(cl*100)}'] = result['value']

        return self._create_result_dict(
            value=results,
            method=f'var_{method}_multiple',
            parameters={
                'confidence_levels': confidence_levels,
                'method': method
            }
        )

    def calculate_risk_metrics(self, returns) -> Dict[str, Any]:
        """
        Calculate comprehensive risk metrics: VaR, CVaR, max drawdown, Sharpe.

        Args:
            returns: Historical returns data (list, np.ndarray, or pd.Series)

        Returns:
            Dict with var_95, var_99, cvar_95, cvar_99, max_drawdown, sharpe_ratio, volatility, mean_return
        """
        import pandas as pd
        if not isinstance(returns, pd.Series):
            returns = pd.Series(returns)

        var_95 = self.calculate(returns, confidence_level=0.95, method='historical')['value']
        var_99 = self.calculate(returns, confidence_level=0.99, method='historical')['value']

        from domain.quantlib.risk.cvar import CVaRCalculator
        cvar_calc = CVaRCalculator()
        cvar_95 = cvar_calc.calculate(returns, confidence_level=0.95, method='historical')['value']
        cvar_99 = cvar_calc.calculate(returns, confidence_level=0.99, method='historical')['value']

        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_dd = abs(float(drawdown.min()))

        excess = returns - self.risk_free_rate / 252
        sharpe = float(excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0.0

        return {
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'cvar_99': cvar_99,
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe,
            'volatility': float(returns.std()),
            'mean_return': float(returns.mean()),
        }


def quick_var(returns, confidence_level: float = 0.95, method: str = 'historical') -> float:
    """Quick VaR calculation convenience function."""
    calc = VaRCalculator()
    return calc.calculate(returns, confidence_level=confidence_level, method=method)['value']


def quick_cvar(returns, confidence_level: float = 0.95, method: str = 'historical') -> float:
    """Quick CVaR calculation convenience function."""
    from domain.quantlib.risk.cvar import CVaRCalculator
    calc = CVaRCalculator()
    return calc.calculate(returns, confidence_level=confidence_level, method=method)['value']
