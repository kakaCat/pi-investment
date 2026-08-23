"""
Scenario Analysis Calculator
=============================

Performs comprehensive scenario analysis including historical scenarios,
hypothetical scenarios, and probability-weighted impact assessment.

This module provides:
- Historical scenario replay
- Hypothetical scenario construction
- Scenario generation and simulation
- Portfolio impact assessment
- Probability-weighted loss calculation

Author: QuantSys V2 Advanced Risk Module
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    InsufficientDataError,
    DataValidationError,
    ConfigurationError
)


@dataclass
class MarketScenario:
    """
    Market scenario definition.

    Attributes:
        name: Scenario name
        description: Detailed description
        asset_returns: Dictionary of asset returns (asset_name -> return)
        market_conditions: Dictionary of market condition changes
        probability: Scenario probability
        time_horizon: Time horizon in days
        scenario_type: Type ('historical', 'hypothetical', 'stress')
    """
    name: str
    description: str
    asset_returns: Dict[str, float]
    market_conditions: Dict[str, float]
    probability: float = 1.0
    time_horizon: int = 1
    scenario_type: str = 'hypothetical'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'asset_returns': self.asset_returns,
            'market_conditions': self.market_conditions,
            'probability': self.probability,
            'time_horizon': self.time_horizon,
            'scenario_type': self.scenario_type
        }


class ScenarioAnalysisCalculator(BaseCalculator):
    """
    Scenario Analysis Calculator

    Performs comprehensive scenario analysis to evaluate portfolio
    performance under various market conditions.

    Features:
        - Historical scenario replay (2008 crisis, 2020 pandemic, etc.)
        - Hypothetical scenario construction
        - Scenario generation using statistical methods
        - Portfolio impact assessment
        - Probability-weighted loss calculation
        - Scenario recommendations

    Methods:
        - historical_scenarios: Replay historical crisis periods
        - hypothetical_scenarios: Analyze user-defined scenarios
        - generate_scenarios: Generate scenarios using Monte Carlo
        - assess_impact: Assess portfolio impact

    Example:
        calculator = ScenarioAnalysisCalculator()
        result = calculator.calculate(
            portfolio={'stocks': 0.6, 'bonds': 0.4},
            scenarios=[scenario1, scenario2],
            risk_factors=factors,
            scenario_type='historical'
        )
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Scenario Analysis calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

        # Predefined historical scenarios
        self.historical_scenarios = self._define_historical_scenarios()

    def calculate(self,
                  portfolio: Union[Dict[str, float], pd.Series],
                  scenarios: Optional[List[MarketScenario]] = None,
                  risk_factors: Optional[Union[pd.DataFrame, np.ndarray]] = None,
                  scenario_type: str = 'historical') -> Dict[str, Any]:
        """
        Calculate scenario analysis results.

        Args:
            portfolio: Portfolio weights (asset_name -> weight)
            scenarios: List of scenarios to analyze
            risk_factors: Optional risk factor data for scenario generation
            scenario_type: Type of scenarios ('historical', 'hypothetical', 'generated')

        Returns:
            Dictionary with scenario analysis results

        Raises:
            ConfigurationError: If invalid scenario type
            DataValidationError: If portfolio weights invalid
            CalculationError: If calculation fails
        """
        # Validate portfolio
        if isinstance(portfolio, pd.Series):
            portfolio = portfolio.to_dict()

        if not isinstance(portfolio, dict):
            raise DataValidationError("Portfolio must be a dictionary or pandas Series")

        # Validate weights sum to 1
        total_weight = sum(portfolio.values())
        if not np.isclose(total_weight, 1.0, atol=1e-6):
            self.logger.warning(f"Portfolio weights sum to {total_weight}, normalizing to 1.0")
            portfolio = {k: v / total_weight for k, v in portfolio.items()}

        # Select scenarios based on type
        if scenarios is None:
            if scenario_type == 'historical':
                scenarios = self.historical_scenarios
            elif scenario_type == 'generated' and risk_factors is not None:
                scenarios = self._generate_scenarios(risk_factors, n_scenarios=10)
            else:
                raise ConfigurationError(
                    "Must provide scenarios or risk_factors for scenario generation",
                    parameter='scenarios'
                )

        try:
            # Analyze each scenario
            scenario_results = []

            for scenario in scenarios:
                result = self._analyze_scenario(portfolio, scenario)
                scenario_results.append(result)

            # Calculate aggregate metrics
            portfolio_impacts = [r['portfolio_impact'] for r in scenario_results]
            worst_case = min(portfolio_impacts)
            best_case = max(portfolio_impacts)
            average_impact = np.mean(portfolio_impacts)

            # Probability-weighted loss
            total_prob = sum(s.probability for s in scenarios)
            probability_weighted_loss = sum(
                r['portfolio_impact'] * scenarios[i].probability / total_prob
                for i, r in enumerate(scenario_results)
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(
                scenario_results,
                portfolio,
                probability_weighted_loss
            )

            return self._create_result_dict(
                value={
                    'scenario_results': scenario_results,
                    'portfolio_impact': {
                        'worst_case': float(worst_case),
                        'best_case': float(best_case),
                        'average': float(average_impact),
                        'probability_weighted_loss': float(probability_weighted_loss)
                    },
                    'recommendations': recommendations,
                    'portfolio': portfolio
                },
                method=f'scenario_analysis_{scenario_type}',
                parameters={
                    'n_scenarios': len(scenarios),
                    'n_assets': len(portfolio),
                    'scenario_type': scenario_type
                },
                metadata={
                    'interpretation': 'Negative impacts indicate portfolio losses'
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, ConfigurationError)):
                raise
            raise CalculationError(str(e), calculation_type='Scenario Analysis')

    def _analyze_scenario(self,
                         portfolio: Dict[str, float],
                         scenario: MarketScenario) -> Dict[str, Any]:
        """
        Analyze a single scenario's impact on portfolio.

        Args:
            portfolio: Portfolio weights
            scenario: Market scenario

        Returns:
            Dictionary with scenario analysis results
        """
        # Calculate portfolio impact
        portfolio_impact = 0.0
        asset_contributions = {}

        for asset, weight in portfolio.items():
            if asset in scenario.asset_returns:
                contribution = weight * scenario.asset_returns[asset]
                portfolio_impact += contribution
                asset_contributions[asset] = float(contribution)
            else:
                # Asset not affected in this scenario
                asset_contributions[asset] = 0.0

        # Calculate risk metrics
        volatility_impact = scenario.market_conditions.get('volatility_change', 0.0)
        liquidity_impact = scenario.market_conditions.get('liquidity_change', 0.0)
        correlation_impact = scenario.market_conditions.get('correlation_change', 0.0)

        # Assess severity
        if portfolio_impact < -0.20:
            severity = 'extreme'
        elif portfolio_impact < -0.10:
            severity = 'severe'
        elif portfolio_impact < -0.05:
            severity = 'moderate'
        elif portfolio_impact < 0:
            severity = 'mild'
        else:
            severity = 'positive'

        return {
            'scenario_name': scenario.name,
            'scenario_description': scenario.description,
            'scenario_type': scenario.scenario_type,
            'portfolio_impact': float(portfolio_impact),
            'asset_contributions': asset_contributions,
            'market_conditions': {
                'volatility_change': float(volatility_impact),
                'liquidity_change': float(liquidity_impact),
                'correlation_change': float(correlation_impact)
            },
            'probability': scenario.probability,
            'time_horizon': scenario.time_horizon,
            'severity': severity
        }

    def _generate_scenarios(self,
                           risk_factors: Union[pd.DataFrame, np.ndarray],
                           n_scenarios: int = 10,
                           confidence_level: float = 0.95) -> List[MarketScenario]:
        """
        Generate scenarios using Monte Carlo simulation.

        Args:
            risk_factors: Historical risk factor data
            n_scenarios: Number of scenarios to generate
            confidence_level: Confidence level for extreme scenarios

        Returns:
            List of generated scenarios
        """
        if isinstance(risk_factors, pd.DataFrame):
            factor_names = risk_factors.columns.tolist()
            risk_factors_matrix = risk_factors.values
        else:
            risk_factors_matrix = np.array(risk_factors)
            factor_names = [f'Factor_{i+1}' for i in range(risk_factors_matrix.shape[1])]

        # Calculate statistics
        mean_returns = np.mean(risk_factors_matrix, axis=0)
        cov_matrix = np.cov(risk_factors_matrix.T)

        scenarios = []

        # Generate normal scenarios
        for i in range(n_scenarios // 2):
            # Sample from multivariate normal
            sampled_returns = np.random.multivariate_normal(mean_returns, cov_matrix)

            asset_returns = {
                factor_names[j]: float(sampled_returns[j])
                for j in range(len(factor_names))
            }

            scenarios.append(MarketScenario(
                name=f'Generated Scenario {i+1}',
                description='Monte Carlo generated scenario',
                asset_returns=asset_returns,
                market_conditions={'volatility_change': 0.0},
                probability=1.0 / n_scenarios,
                scenario_type='generated'
            ))

        # Generate tail scenarios (extreme)
        from scipy.stats import norm
        z_score = norm.ppf(1 - (1 - confidence_level) / 2)

        for i in range(n_scenarios // 2):
            # Generate extreme scenario
            direction = np.random.randn(len(factor_names))
            direction = direction / np.linalg.norm(direction)

            # Scale by z-score and volatility
            std_devs = np.sqrt(np.diag(cov_matrix))
            extreme_returns = mean_returns + z_score * std_devs * direction

            asset_returns = {
                factor_names[j]: float(extreme_returns[j])
                for j in range(len(factor_names))
            }

            scenarios.append(MarketScenario(
                name=f'Extreme Scenario {i+1}',
                description='Tail risk scenario',
                asset_returns=asset_returns,
                market_conditions={'volatility_change': 0.5},
                probability=0.5 / n_scenarios,
                scenario_type='generated'
            ))

        return scenarios

    def _generate_recommendations(self,
                                 scenario_results: List[Dict[str, Any]],
                                 portfolio: Dict[str, float],
                                 weighted_loss: float) -> List[str]:
        """
        Generate recommendations based on scenario analysis.

        Args:
            scenario_results: Results from scenario analysis
            portfolio: Current portfolio
            weighted_loss: Probability-weighted expected loss

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Check for severe scenarios
        severe_scenarios = [r for r in scenario_results if r['severity'] in ['severe', 'extreme']]
        if len(severe_scenarios) > len(scenario_results) * 0.3:
            recommendations.append(
                "High exposure to severe scenarios detected. Consider reducing risk exposure."
            )

        # Check weighted loss
        if weighted_loss < -0.10:
            recommendations.append(
                f"Expected loss under scenarios is {weighted_loss:.1%}. Consider hedging strategies."
            )

        # Check asset concentration
        max_contribution = max(
            abs(sum(r['asset_contributions'].get(asset, 0) for r in scenario_results))
            for asset in portfolio.keys()
        )
        if max_contribution > 0.5:
            recommendations.append(
                "High concentration risk detected. Consider diversifying across more assets."
            )

        # Check for positive scenarios
        positive_scenarios = [r for r in scenario_results if r['portfolio_impact'] > 0]
        if len(positive_scenarios) < len(scenario_results) * 0.2:
            recommendations.append(
                "Few positive scenarios detected. Portfolio may be overly defensive."
            )

        # Default recommendation
        if not recommendations:
            recommendations.append(
                "Portfolio shows reasonable resilience across scenarios. Continue monitoring."
            )

        return recommendations

    def _define_historical_scenarios(self) -> List[MarketScenario]:
        """
        Define historical crisis scenarios.
        """
        return [
            MarketScenario(
                name='2008 Financial Crisis',
                description='Global financial crisis: Lehman collapse, credit freeze',
                asset_returns={
                    'stocks': -0.40,
                    'bonds': -0.10,
                    'real_estate': -0.35,
                    'commodities': -0.30,
                    'cash': 0.02
                },
                market_conditions={
                    'volatility_change': 1.50,
                    'liquidity_change': -0.70,
                    'correlation_change': 0.40,
                    'credit_spread_change': 0.05
                },
                probability=0.02,
                time_horizon=180,
                scenario_type='historical'
            ),
            MarketScenario(
                name='2020 COVID-19 Pandemic',
                description='Global pandemic: lockdowns, economic shutdown',
                asset_returns={
                    'stocks': -0.30,
                    'bonds': 0.05,
                    'real_estate': -0.15,
                    'commodities': -0.25,
                    'gold': 0.15
                },
                market_conditions={
                    'volatility_change': 2.00,
                    'liquidity_change': -0.50,
                    'correlation_change': 0.30,
                    'credit_spread_change': 0.03
                },
                probability=0.03,
                time_horizon=60,
                scenario_type='historical'
            ),
            MarketScenario(
                name='2022 Inflation Surge',
                description='High inflation and aggressive rate hikes',
                asset_returns={
                    'stocks': -0.18,
                    'bonds': -0.15,
                    'real_estate': -0.10,
                    'commodities': 0.20,
                    'tips': 0.05
                },
                market_conditions={
                    'volatility_change': 0.60,
                    'liquidity_change': -0.30,
                    'correlation_change': 0.20,
                    'interest_rate_change': 0.04
                },
                probability=0.10,
                time_horizon=365,
                scenario_type='historical'
            ),
            MarketScenario(
                name='1987 Black Monday',
                description='Single-day market crash',
                asset_returns={
                    'stocks': -0.22,
                    'bonds': 0.02,
                    'commodities': -0.05,
                    'cash': 0.01
                },
                market_conditions={
                    'volatility_change': 3.00,
                    'liquidity_change': -0.80,
                    'correlation_change': 0.50
                },
                probability=0.01,
                time_horizon=1,
                scenario_type='historical'
            ),
            MarketScenario(
                name='2011 European Debt Crisis',
                description='Sovereign debt crisis in Europe',
                asset_returns={
                    'stocks': -0.15,
                    'bonds': -0.08,
                    'european_bonds': -0.25,
                    'gold': 0.10,
                    'usd': 0.05
                },
                market_conditions={
                    'volatility_change': 0.80,
                    'liquidity_change': -0.40,
                    'correlation_change': 0.25,
                    'credit_spread_change': 0.04
                },
                probability=0.05,
                time_horizon=120,
                scenario_type='historical'
            ),
            MarketScenario(
                name='Interest Rate Shock',
                description='Hypothetical: 200bp rate increase',
                asset_returns={
                    'stocks': -0.15,
                    'bonds': -0.12,
                    'real_estate': -0.20,
                    'growth_stocks': -0.25,
                    'value_stocks': -0.10
                },
                market_conditions={
                    'volatility_change': 0.50,
                    'liquidity_change': -0.20,
                    'interest_rate_change': 0.02
                },
                probability=0.15,
                time_horizon=90,
                scenario_type='hypothetical'
            ),
            MarketScenario(
                name='Geopolitical Crisis',
                description='Hypothetical: Major geopolitical conflict',
                asset_returns={
                    'stocks': -0.25,
                    'bonds': 0.03,
                    'commodities': 0.30,
                    'gold': 0.20,
                    'defense': 0.10
                },
                market_conditions={
                    'volatility_change': 1.20,
                    'liquidity_change': -0.60,
                    'correlation_change': 0.35
                },
                probability=0.08,
                time_horizon=30,
                scenario_type='hypothetical'
            )
        ]

    def get_supported_methods(self) -> List[str]:
        """Return list of supported calculation methods."""
        return ['historical', 'hypothetical', 'generated']
