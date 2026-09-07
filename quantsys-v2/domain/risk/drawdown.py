"""
Drawdown Analysis Calculator
=============================

Calculates various drawdown metrics including maximum drawdown,
average drawdown, drawdown duration, and recovery analysis.

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional, Tuple
from datetime import datetime

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    InsufficientDataError,
    DataValidationError
)


class DrawdownCalculator(BaseCalculator):
    """
    Drawdown Analysis Calculator

    Calculates drawdown metrics which measure the decline from a historical peak
    in cumulative returns. Drawdowns are important for understanding downside risk
    and recovery characteristics.

    Metrics:
        - Maximum Drawdown (MDD): Largest peak-to-trough decline
        - Average Drawdown: Mean of all drawdown periods
        - Drawdown Duration: Length of drawdown periods
        - Recovery Time: Time to recover from drawdowns
        - Calmar Ratio: Return / Maximum Drawdown
        - Ulcer Index: RMS of drawdowns

    Example:
        calculator = DrawdownCalculator(precision=4)
        result = calculator.calculate(returns)
        print(f"Max Drawdown: {result['value']['max_drawdown']}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Drawdown calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate for Calmar ratio calculation
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  returns: Union[List, np.ndarray, pd.Series],
                  prices: Optional[Union[List, np.ndarray, pd.Series]] = None) -> Dict[str, Any]:
        """
        Calculate comprehensive drawdown metrics.

        Args:
            returns: Historical returns data
            prices: Optional price series (if not provided, calculated from returns)

        Returns:
            Dictionary with drawdown metrics

        Raises:
            InsufficientDataError: If not enough data points
            CalculationError: If calculation fails
        """
        # Validate inputs
        returns = self._validate_returns(returns, 'returns')

        if len(returns) < 2:
            raise InsufficientDataError(
                required=2,
                provided=len(returns),
                calculation='Drawdown'
            )

        try:
            # Calculate cumulative returns (wealth index)
            if prices is not None:
                prices = self._validate_numeric_input(prices, 'prices')
                if isinstance(prices, pd.Series):
                    wealth_index = prices.values
                else:
                    wealth_index = np.array(prices)
            else:
                wealth_index = (1 + returns).cumprod()

            # Calculate drawdown series
            drawdown_series = self._calculate_drawdown_series(wealth_index)

            # Calculate metrics
            max_drawdown = np.min(drawdown_series)
            avg_drawdown = np.mean(drawdown_series[drawdown_series < 0]) if np.any(drawdown_series < 0) else 0.0

            # Find drawdown periods
            drawdown_periods = self._identify_drawdown_periods(drawdown_series)

            # Calculate durations
            if drawdown_periods:
                max_duration = max(period['duration'] for period in drawdown_periods)
                avg_duration = np.mean([period['duration'] for period in drawdown_periods])
                max_recovery = max((period['recovery_time'] for period in drawdown_periods
                                   if period['recovery_time'] is not None), default=None)
            else:
                max_duration = 0
                avg_duration = 0.0
                max_recovery = None

            # Calculate Ulcer Index
            ulcer_index = self._calculate_ulcer_index(drawdown_series)

            # Calculate Calmar Ratio
            annual_return = np.mean(returns) * 252  # Assuming daily returns
            calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown < 0 else 0.0

            # Pain Index (average drawdown over entire period)
            pain_index = np.mean(np.abs(drawdown_series))

            result_value = {
                'max_drawdown': abs(max_drawdown),
                'average_drawdown': abs(avg_drawdown),
                'current_drawdown': abs(drawdown_series[-1]),
                'max_drawdown_duration': max_duration,
                'average_drawdown_duration': avg_duration,
                'max_recovery_time': max_recovery,
                'ulcer_index': ulcer_index,
                'pain_index': pain_index,
                'calmar_ratio': calmar_ratio,
                'n_drawdown_periods': len(drawdown_periods)
            }

            return self._create_result_dict(
                value=result_value,
                method='drawdown_analysis',
                parameters={
                    'n_observations': len(returns),
                    'using_prices': prices is not None
                },
                metadata={
                    'drawdown_periods': drawdown_periods[:5] if len(drawdown_periods) > 5 else drawdown_periods,
                    'interpretation': 'Maximum drawdown shows worst peak-to-trough decline'
                }
            )

        except Exception as e:
            if isinstance(e, InsufficientDataError):
                raise
            raise CalculationError(str(e), calculation_type='Drawdown')

    def _calculate_drawdown_series(self, wealth_index: np.ndarray) -> np.ndarray:
        """
        Calculate drawdown series from wealth index.

        Drawdown at time t = (Wealth_t - Peak_t) / Peak_t
        """
        # Calculate running maximum (peak)
        running_max = np.maximum.accumulate(wealth_index)

        # Calculate drawdown
        drawdown = (wealth_index - running_max) / running_max

        return drawdown

    def _identify_drawdown_periods(self, drawdown_series: np.ndarray) -> List[Dict[str, Any]]:
        """
        Identify individual drawdown periods.

        A drawdown period starts when drawdown becomes negative and ends
        when it returns to zero (recovery).
        """
        periods = []
        in_drawdown = False
        start_idx = None
        max_dd_in_period = 0.0
        max_dd_idx = None

        for i, dd in enumerate(drawdown_series):
            if not in_drawdown and dd < 0:
                # Start of drawdown
                in_drawdown = True
                start_idx = i
                max_dd_in_period = dd
                max_dd_idx = i

            elif in_drawdown:
                if dd < max_dd_in_period:
                    max_dd_in_period = dd
                    max_dd_idx = i

                if dd >= 0:
                    # End of drawdown (recovery)
                    periods.append({
                        'start': start_idx,
                        'trough': max_dd_idx,
                        'end': i,
                        'duration': max_dd_idx - start_idx,
                        'recovery_time': i - max_dd_idx,
                        'total_duration': i - start_idx,
                        'depth': abs(max_dd_in_period)
                    })
                    in_drawdown = False
                    start_idx = None
                    max_dd_in_period = 0.0

        # Handle ongoing drawdown
        if in_drawdown:
            periods.append({
                'start': start_idx,
                'trough': max_dd_idx,
                'end': len(drawdown_series) - 1,
                'duration': max_dd_idx - start_idx,
                'recovery_time': None,  # Not yet recovered
                'total_duration': len(drawdown_series) - 1 - start_idx,
                'depth': abs(max_dd_in_period)
            })

        return periods

    def _calculate_ulcer_index(self, drawdown_series: np.ndarray) -> float:
        """
        Calculate Ulcer Index.

        Ulcer Index = sqrt(mean(drawdown^2))
        Measures the depth and duration of drawdowns.
        """
        squared_drawdowns = drawdown_series ** 2
        ulcer_index = np.sqrt(np.mean(squared_drawdowns))
        return ulcer_index

    def calculate_max_drawdown(self,
                               returns: Union[List, np.ndarray, pd.Series]) -> Dict[str, Any]:
        """
        Calculate only maximum drawdown (faster for simple use cases).

        Args:
            returns: Historical returns data

        Returns:
            Dictionary with maximum drawdown value
        """
        returns = self._validate_returns(returns, 'returns')

        wealth_index = (1 + returns).cumprod()
        drawdown_series = self._calculate_drawdown_series(wealth_index)
        max_drawdown = np.min(drawdown_series)

        return self._create_result_dict(
            value=abs(max_drawdown),
            method='max_drawdown',
            parameters={'n_observations': len(returns)}
        )

    def calculate_calmar_ratio(self,
                               returns: Union[List, np.ndarray, pd.Series],
                               periods_per_year: int = 252) -> Dict[str, Any]:
        """
        Calculate Calmar Ratio (Annualized Return / Maximum Drawdown).

        Args:
            returns: Historical returns data
            periods_per_year: Number of periods per year (252 for daily, 12 for monthly)

        Returns:
            Dictionary with Calmar ratio
        """
        returns = self._validate_returns(returns, 'returns')

        # Calculate annualized return
        total_return = (1 + returns).prod() - 1
        n_years = len(returns) / periods_per_year
        annualized_return = (1 + total_return) ** (1 / n_years) - 1

        # Calculate max drawdown
        wealth_index = (1 + returns).cumprod()
        drawdown_series = self._calculate_drawdown_series(wealth_index)
        max_drawdown = abs(np.min(drawdown_series))

        # Calmar ratio
        calmar = annualized_return / max_drawdown if max_drawdown > 0 else 0.0

        return self._create_result_dict(
            value=calmar,
            method='calmar_ratio',
            parameters={
                'annualized_return': annualized_return,
                'max_drawdown': max_drawdown,
                'periods_per_year': periods_per_year
            },
            metadata={
                'interpretation': 'Higher is better; measures return per unit of drawdown risk'
            }
        )

    def get_drawdown_series(self,
                           returns: Union[List, np.ndarray, pd.Series]) -> pd.Series:
        """
        Get the full drawdown series for plotting.

        Args:
            returns: Historical returns data

        Returns:
            Pandas Series with drawdown values
        """
        returns = self._validate_returns(returns, 'returns')

        wealth_index = (1 + returns).cumprod()
        drawdown_series = self._calculate_drawdown_series(wealth_index)

        if isinstance(returns, pd.Series):
            return pd.Series(drawdown_series, index=returns.index)
        else:
            return pd.Series(drawdown_series)

    def get_supported_methods(self) -> List[str]:
        """Return list of supported calculation methods."""
        return ['drawdown_analysis', 'max_drawdown', 'calmar_ratio']
