"""
Stress Test Calculator
=======================

Performs stress testing and scenario analysis to assess portfolio
resilience under adverse market conditions.

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    InsufficientDataError,
    DataValidationError,
    ConfigurationError
)


@dataclass
class Scenario:
    """
    Stress test scenario definition.

    Attributes:
        name: Scenario name
        description: Scenario description
        shocks: Dictionary of asset shocks (asset_name -> shock_percentage)
        probability: Scenario probability (optional)
    """
    name: str
    description: str
    shocks: Dict[str, float]
    probability: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'shocks': self.shocks,
            'probability': self.probability
        }


class StressTestCalculator(BaseCalculator):
    """
    Stress Test Calculator

    Performs stress testing and scenario analysis to evaluate portfolio
    performance under extreme market conditions.

    Methods:
        - historical_scenarios: Use historical crisis periods
        - hypothetical_scenarios: User-defined scenarios
        - sensitivity_analysis: Single factor sensitivity
        - monte_carlo_stress: Monte Carlo stress testing

    Example:
        calculator = StressTestCalculator()
        scenario = Scenario('Market Crash', 'Equity market -30%', {'stocks': -0.30})
        result = calculator.calculate(returns, weights, [scenario])
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Stress Test calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate (not used but kept for consistency)
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

        # Predefined historical scenarios
        self.historical_scenarios = self._define_historical_scenarios()

    def calculate(self,
                  returns: Union[pd.DataFrame, np.ndarray],
                  weights: Union[List, np.ndarray, pd.Series],
                  scenarios: List[Scenario],
                  asset_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Calculate stress test results for given scenarios.

        Args:
            returns: Historical returns matrix (observations x assets)
            weights: Portfolio weights
            scenarios: List of stress test scenarios
            asset_names: Optional names for assets

        Returns:
            Dictionary with stress test results

        Raises:
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

        try:
            # Calculate baseline portfolio metrics
            baseline_return = np.mean(returns_matrix @ weights)
            baseline_volatility = np.std(returns_matrix @ weights, ddof=1)

            # Run each scenario
            scenario_results = []

            for scenario in scenarios:
                result = self._run_scenario(
                    returns_matrix,
                    weights,
                    asset_names,
                    scenario,
                    baseline_return
                )
                scenario_results.append(result)

            # Calculate aggregate metrics
            worst_case = min(r['portfolio_return'] for r in scenario_results)
            best_case = max(r['portfolio_return'] for r in scenario_results)
            avg_stressed_return = np.mean([r['portfolio_return'] for r in scenario_results])

            # Probability-weighted expected loss (if probabilities provided)
            if all(s.probability is not None for s in scenarios):
                total_prob = sum(s.probability for s in scenarios)
                weighted_loss = sum(
                    r['portfolio_return'] * scenarios[i].probability / total_prob
                    for i, r in enumerate(scenario_results)
                )
            else:
                weighted_loss = None

            return self._create_result_dict(
                value={
                    'baseline_return': baseline_return,
                    'baseline_volatility': baseline_volatility,
                    'scenarios': scenario_results,
                    'worst_case': worst_case,
                    'best_case': best_case,
                    'average_stressed_return': avg_stressed_return,
                    'weighted_expected_loss': weighted_loss
                },
                method='stress_test',
                parameters={
                    'n_scenarios': len(scenarios),
                    'n_assets': n_assets,
                    'n_observations': returns_matrix.shape[0]
                },
                metadata={
                    'interpretation': 'Negative returns indicate portfolio losses under stress'
                }
            )

        except Exception as e:
            if isinstance(e, DataValidationError):
                raise
            raise CalculationError(str(e), calculation_type='Stress Test')

    def _run_scenario(self,
                     returns_matrix: np.ndarray,
                     weights: np.ndarray,
                     asset_names: List[str],
                     scenario: Scenario,
                     baseline_return: float) -> Dict[str, Any]:
        """
        Run a single stress test scenario.
        """
        # Apply shocks to each asset
        shocked_returns = np.zeros(len(asset_names))

        for i, name in enumerate(asset_names):
            if name in scenario.shocks:
                shocked_returns[i] = scenario.shocks[name]
            else:
                # No shock specified, use baseline
                shocked_returns[i] = np.mean(returns_matrix[:, i])

        # Calculate portfolio return under stress
        portfolio_return = np.dot(weights, shocked_returns)

        # Calculate loss relative to baseline
        loss = portfolio_return - baseline_return
        loss_percentage = (loss / abs(baseline_return)) * 100 if baseline_return != 0 else 0

        return {
            'scenario_name': scenario.name,
            'scenario_description': scenario.description,
            'portfolio_return': float(portfolio_return),
            'loss_vs_baseline': float(loss),
            'loss_percentage': float(loss_percentage),
            'probability': scenario.probability,
            'asset_contributions': {
                asset_names[i]: float(weights[i] * shocked_returns[i])
                for i in range(len(asset_names))
            }
        }

    def sensitivity_analysis(self,
                            returns: Union[pd.DataFrame, np.ndarray],
                            weights: Union[List, np.ndarray, pd.Series],
                            shock_range: Tuple[float, float] = (-0.50, 0.50),
                            n_points: int = 21,
                            asset_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Perform sensitivity analysis by shocking each asset individually.

        Args:
            returns: Historical returns matrix
            weights: Portfolio weights
            shock_range: Range of shocks to apply (min, max)
            n_points: Number of points in the shock range
            asset_names: Optional names for assets

        Returns:
            Dictionary with sensitivity analysis results
        """
        # Validate and prepare data
        if isinstance(returns, pd.DataFrame):
            asset_names = asset_names or returns.columns.tolist()
            returns_matrix = returns.values
        else:
            returns_matrix = np.array(returns)
            asset_names = asset_names or [f'Asset_{i+1}' for i in range(returns_matrix.shape[1])]

        weights = np.array(weights).flatten()

        # Generate shock levels
        shocks = np.linspace(shock_range[0], shock_range[1], n_points)

        # Calculate sensitivity for each asset
        sensitivity_results = {}

        for i, name in enumerate(asset_names):
            portfolio_returns = []

            for shock in shocks:
                # Apply shock to this asset only
                shocked_returns = np.mean(returns_matrix, axis=0).copy()
                shocked_returns[i] = shocked_returns[i] + shock

                # Calculate portfolio return
                portfolio_return = np.dot(weights, shocked_returns)
                portfolio_returns.append(portfolio_return)

            sensitivity_results[name] = {
                'shocks': shocks.tolist(),
                'portfolio_returns': portfolio_returns,
                'sensitivity': float(np.std(portfolio_returns)),  # Volatility of returns
                'weight': float(weights[i])
            }

        return self._create_result_dict(
            value=sensitivity_results,
            method='sensitivity_analysis',
            parameters={
                'shock_range': shock_range,
                'n_points': n_points,
                'n_assets': len(asset_names)
            },
            metadata={
                'interpretation': 'Higher sensitivity indicates greater impact from asset shocks'
            }
        )

    def historical_stress_test(self,
                               returns: Union[pd.DataFrame],
                               weights: Union[List, np.ndarray, pd.Series],
                               crisis_periods: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Any]:
        """
        Perform stress test using historical crisis periods.

        Args:
            returns: Historical returns DataFrame with datetime index
            weights: Portfolio weights
            crisis_periods: List of (start_date, end_date) tuples for crisis periods

        Returns:
            Dictionary with historical stress test results
        """
        if not isinstance(returns, pd.DataFrame):
            raise DataValidationError("Historical stress test requires DataFrame with datetime index")

        if crisis_periods is None:
            # Use predefined crisis periods
            crisis_periods = [
                ('2008-09-01', '2009-03-31'),  # Financial Crisis
                ('2020-02-01', '2020-04-30'),  # COVID-19 Crash
                ('2022-01-01', '2022-06-30'),  # 2022 Bear Market
            ]

        weights = np.array(weights).flatten()

        # Calculate portfolio returns
        portfolio_returns = returns @ weights

        # Analyze each crisis period
        crisis_results = []

        for start_date, end_date in crisis_periods:
            try:
                period_returns = portfolio_returns.loc[start_date:end_date]

                if len(period_returns) == 0:
                    continue

                cumulative_return = (1 + period_returns).prod() - 1
                max_drawdown = (period_returns.cumsum() - period_returns.cumsum().cummax()).min()
                volatility = period_returns.std() * np.sqrt(252)

                crisis_results.append({
                    'period': f'{start_date} to {end_date}',
                    'cumulative_return': float(cumulative_return),
                    'max_drawdown': float(max_drawdown),
                    'volatility': float(volatility),
                    'n_observations': len(period_returns)
                })

            except Exception as e:
                self.logger.warning(f"Could not analyze period {start_date} to {end_date}: {e}")
                continue

        if not crisis_results:
            raise CalculationError("No valid crisis periods found in data")

        # Aggregate statistics
        worst_return = min(r['cumulative_return'] for r in crisis_results)
        worst_drawdown = min(r['max_drawdown'] for r in crisis_results)
        avg_crisis_return = np.mean([r['cumulative_return'] for r in crisis_results])

        return self._create_result_dict(
            value={
                'crisis_periods': crisis_results,
                'worst_return': worst_return,
                'worst_drawdown': worst_drawdown,
                'average_crisis_return': avg_crisis_return
            },
            method='historical_stress_test',
            parameters={
                'n_periods': len(crisis_results),
                'n_assets': len(weights)
            }
        )

    def _define_historical_scenarios(self) -> List[Scenario]:
        """
        Define common historical stress scenarios.
        """
        return [
            Scenario(
                name='2008 Financial Crisis',
                description='Global financial crisis scenario',
                shocks={'stocks': -0.40, 'bonds': -0.10, 'commodities': -0.35},
                probability=0.05
            ),
            Scenario(
                name='COVID-19 Crash',
                description='Pandemic-induced market crash',
                shocks={'stocks': -0.35, 'bonds': 0.05, 'commodities': -0.25},
                probability=0.03
            ),
            Scenario(
                name='Inflation Shock',
                description='Rapid inflation increase',
                shocks={'stocks': -0.15, 'bonds': -0.20, 'commodities': 0.30},
                probability=0.10
            ),
            Scenario(
                name='Interest Rate Spike',
                description='Sudden interest rate increase',
                shocks={'stocks': -0.20, 'bonds': -0.15, 'real_estate': -0.25},
                probability=0.08
            )
        ]

    def get_supported_methods(self) -> List[str]:
        """Return list of supported calculation methods."""
        return ['stress_test', 'sensitivity_analysis', 'historical_stress_test']
