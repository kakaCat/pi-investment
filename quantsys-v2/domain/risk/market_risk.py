"""
Market Risk Calculator
======================

Calculates market risk measures including Beta, correlation,
tracking error, and systematic vs. idiosyncratic risk.

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional, Tuple
from scipy import stats

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    InsufficientDataError,
    DataValidationError
)


class MarketRiskCalculator(BaseCalculator):
    """
    Market Risk Calculator

    Calculates market risk measures that quantify the relationship
    between a portfolio/asset and the market or benchmark.

    Metrics:
        - Beta: Systematic risk relative to market
        - Alpha: Excess return over expected return (CAPM)
        - Correlation: Linear relationship with market
        - R-squared: Proportion of variance explained by market
        - Tracking Error: Standard deviation of excess returns
        - Information Ratio: Excess return / Tracking error
        - Systematic Risk: Risk from market exposure
        - Idiosyncratic Risk: Asset-specific risk

    Example:
        calculator = MarketRiskCalculator(risk_free_rate=0.02)
        result = calculator.calculate(portfolio_returns, market_returns)
        print(f"Beta: {result['value']['beta']}")
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Market Risk calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate for alpha calculation
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

    def calculate(self,
                  portfolio_returns: Union[List, np.ndarray, pd.Series],
                  benchmark_returns: Union[List, np.ndarray, pd.Series],
                  risk_free_rate: Optional[float] = None) -> Dict[str, Any]:
        """
        Calculate comprehensive market risk metrics.

        Args:
            portfolio_returns: Portfolio or asset returns
            benchmark_returns: Market or benchmark returns
            risk_free_rate: Risk-free rate (uses instance default if not provided)

        Returns:
            Dictionary with market risk metrics

        Raises:
            InsufficientDataError: If not enough data points
            DataValidationError: If returns series have different lengths
            CalculationError: If calculation fails
        """
        # Validate inputs
        portfolio_returns = self._validate_returns(portfolio_returns, 'portfolio_returns')
        benchmark_returns = self._validate_returns(benchmark_returns, 'benchmark_returns')

        if len(portfolio_returns) != len(benchmark_returns):
            raise DataValidationError(
                f"Portfolio and benchmark returns must have same length: "
                f"{len(portfolio_returns)} vs {len(benchmark_returns)}"
            )

        if len(portfolio_returns) < 10:
            raise InsufficientDataError(
                required=10,
                provided=len(portfolio_returns),
                calculation='Market Risk'
            )

        if risk_free_rate is None:
            risk_free_rate = self.risk_free_rate

        try:
            # Calculate excess returns
            portfolio_excess = portfolio_returns - risk_free_rate / 252  # Assuming daily returns
            benchmark_excess = benchmark_returns - risk_free_rate / 252

            # Beta calculation
            covariance = np.cov(portfolio_excess, benchmark_excess)[0, 1]
            benchmark_variance = np.var(benchmark_excess, ddof=1)
            beta = covariance / benchmark_variance if benchmark_variance > 0 else 0.0

            # Alpha calculation (CAPM)
            portfolio_mean = np.mean(portfolio_excess) * 252  # Annualized
            benchmark_mean = np.mean(benchmark_excess) * 252
            alpha = portfolio_mean - beta * benchmark_mean

            # Correlation and R-squared
            correlation = np.corrcoef(portfolio_returns, benchmark_returns)[0, 1]
            r_squared = correlation ** 2

            # Tracking error
            active_returns = portfolio_returns - benchmark_returns
            tracking_error = np.std(active_returns, ddof=1) * np.sqrt(252)  # Annualized

            # Information ratio
            active_return_mean = np.mean(active_returns) * 252  # Annualized
            information_ratio = active_return_mean / tracking_error if tracking_error > 0 else 0.0

            # Systematic and idiosyncratic risk
            portfolio_variance = np.var(portfolio_returns, ddof=1)
            systematic_risk = (beta ** 2) * benchmark_variance
            idiosyncratic_risk = portfolio_variance - systematic_risk

            # Treynor ratio
            treynor_ratio = portfolio_mean / beta if beta > 0 else 0.0

            result_value = {
                'beta': beta,
                'alpha': alpha,
                'correlation': correlation,
                'r_squared': r_squared,
                'tracking_error': tracking_error,
                'information_ratio': information_ratio,
                'systematic_risk': systematic_risk,
                'idiosyncratic_risk': max(0, idiosyncratic_risk),  # Can't be negative
                'total_risk': portfolio_variance,
                'treynor_ratio': treynor_ratio
            }

            return self._create_result_dict(
                value=result_value,
                method='market_risk_analysis',
                parameters={
                    'n_observations': len(portfolio_returns),
                    'risk_free_rate': risk_free_rate
                },
                metadata={
                    'interpretation': {
                        'beta': 'Beta > 1: more volatile than market; Beta < 1: less volatile',
                        'alpha': 'Positive alpha indicates outperformance',
                        'r_squared': 'Proportion of variance explained by market (0-1)',
                        'tracking_error': 'Volatility of excess returns vs benchmark'
                    }
                }
            )

        except Exception as e:
            if isinstance(e, (InsufficientDataError, DataValidationError)):
                raise
            raise CalculationError(str(e), calculation_type='Market Risk')

    def calculate_beta(self,
                      portfolio_returns: Union[List, np.ndarray, pd.Series],
                      benchmark_returns: Union[List, np.ndarray, pd.Series]) -> Dict[str, Any]:
        """
        Calculate Beta only (faster for simple use cases).

        Args:
            portfolio_returns: Portfolio or asset returns
            benchmark_returns: Market or benchmark returns

        Returns:
            Dictionary with beta value
        """
        portfolio_returns = self._validate_returns(portfolio_returns, 'portfolio_returns')
        benchmark_returns = self._validate_returns(benchmark_returns, 'benchmark_returns')

        if len(portfolio_returns) != len(benchmark_returns):
            raise DataValidationError("Returns series must have same length")

        covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns, ddof=1)
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 0.0

        return self._create_result_dict(
            value=beta,
            method='beta',
            parameters={'n_observations': len(portfolio_returns)}
        )

    def calculate_tracking_error(self,
                                 portfolio_returns: Union[List, np.ndarray, pd.Series],
                                 benchmark_returns: Union[List, np.ndarray, pd.Series],
                                 periods_per_year: int = 252) -> Dict[str, Any]:
        """
        Calculate Tracking Error.

        Args:
            portfolio_returns: Portfolio returns
            benchmark_returns: Benchmark returns
            periods_per_year: Number of periods per year for annualization

        Returns:
            Dictionary with tracking error
        """
        portfolio_returns = self._validate_returns(portfolio_returns, 'portfolio_returns')
        benchmark_returns = self._validate_returns(benchmark_returns, 'benchmark_returns')

        if len(portfolio_returns) != len(benchmark_returns):
            raise DataValidationError("Returns series must have same length")

        active_returns = portfolio_returns - benchmark_returns
        tracking_error = np.std(active_returns, ddof=1) * np.sqrt(periods_per_year)

        return self._create_result_dict(
            value=tracking_error,
            method='tracking_error',
            parameters={
                'n_observations': len(portfolio_returns),
                'periods_per_year': periods_per_year
            },
            metadata={
                'interpretation': 'Lower tracking error indicates closer tracking of benchmark'
            }
        )

    def calculate_information_ratio(self,
                                    portfolio_returns: Union[List, np.ndarray, pd.Series],
                                    benchmark_returns: Union[List, np.ndarray, pd.Series],
                                    periods_per_year: int = 252) -> Dict[str, Any]:
        """
        Calculate Information Ratio (Active Return / Tracking Error).

        Args:
            portfolio_returns: Portfolio returns
            benchmark_returns: Benchmark returns
            periods_per_year: Number of periods per year for annualization

        Returns:
            Dictionary with information ratio
        """
        portfolio_returns = self._validate_returns(portfolio_returns, 'portfolio_returns')
        benchmark_returns = self._validate_returns(benchmark_returns, 'benchmark_returns')

        if len(portfolio_returns) != len(benchmark_returns):
            raise DataValidationError("Returns series must have same length")

        active_returns = portfolio_returns - benchmark_returns
        active_return_mean = np.mean(active_returns) * periods_per_year
        tracking_error = np.std(active_returns, ddof=1) * np.sqrt(periods_per_year)

        information_ratio = active_return_mean / tracking_error if tracking_error > 0 else 0.0

        return self._create_result_dict(
            value=information_ratio,
            method='information_ratio',
            parameters={
                'active_return': active_return_mean,
                'tracking_error': tracking_error,
                'periods_per_year': periods_per_year
            },
            metadata={
                'interpretation': 'Higher is better; measures risk-adjusted active return'
            }
        )

    def calculate_rolling_beta(self,
                               portfolio_returns: Union[pd.Series],
                               benchmark_returns: Union[pd.Series],
                               window: int = 60) -> pd.Series:
        """
        Calculate rolling beta over time.

        Args:
            portfolio_returns: Portfolio returns (must be pandas Series)
            benchmark_returns: Benchmark returns (must be pandas Series)
            window: Rolling window size

        Returns:
            Pandas Series with rolling beta values
        """
        if not isinstance(portfolio_returns, pd.Series) or not isinstance(benchmark_returns, pd.Series):
            raise DataValidationError("Rolling calculations require pandas Series")

        if len(portfolio_returns) != len(benchmark_returns):
            raise DataValidationError("Returns series must have same length")

        # Calculate rolling covariance and variance
        rolling_cov = portfolio_returns.rolling(window).cov(benchmark_returns)
        rolling_var = benchmark_returns.rolling(window).var()

        rolling_beta = rolling_cov / rolling_var

        return rolling_beta

    def decompose_risk(self,
                      portfolio_returns: Union[List, np.ndarray, pd.Series],
                      benchmark_returns: Union[List, np.ndarray, pd.Series]) -> Dict[str, Any]:
        """
        Decompose total risk into systematic and idiosyncratic components.

        Args:
            portfolio_returns: Portfolio returns
            benchmark_returns: Benchmark returns

        Returns:
            Dictionary with risk decomposition
        """
        portfolio_returns = self._validate_returns(portfolio_returns, 'portfolio_returns')
        benchmark_returns = self._validate_returns(benchmark_returns, 'benchmark_returns')

        if len(portfolio_returns) != len(benchmark_returns):
            raise DataValidationError("Returns series must have same length")

        # Calculate beta
        covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns, ddof=1)
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 0.0

        # Risk decomposition
        portfolio_variance = np.var(portfolio_returns, ddof=1)
        systematic_variance = (beta ** 2) * benchmark_variance
        idiosyncratic_variance = portfolio_variance - systematic_variance

        # Convert to standard deviations (volatility)
        total_vol = np.sqrt(portfolio_variance)
        systematic_vol = np.sqrt(systematic_variance)
        idiosyncratic_vol = np.sqrt(max(0, idiosyncratic_variance))

        # Percentage contributions
        systematic_pct = systematic_variance / portfolio_variance * 100 if portfolio_variance > 0 else 0
        idiosyncratic_pct = 100 - systematic_pct

        return self._create_result_dict(
            value={
                'total_volatility': total_vol,
                'systematic_volatility': systematic_vol,
                'idiosyncratic_volatility': idiosyncratic_vol,
                'systematic_percentage': systematic_pct,
                'idiosyncratic_percentage': idiosyncratic_pct,
                'beta': beta
            },
            method='risk_decomposition',
            parameters={'n_observations': len(portfolio_returns)},
            metadata={
                'interpretation': 'Systematic risk from market; idiosyncratic risk is diversifiable'
            }
        )

    def get_supported_methods(self) -> List[str]:
        """Return list of supported calculation methods."""
        return ['market_risk_analysis', 'beta', 'tracking_error', 'information_ratio', 'risk_decomposition']
