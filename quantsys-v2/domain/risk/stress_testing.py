"""
Advanced Stress Testing Calculator
===================================

Performs advanced stress testing including multi-factor stress tests,
reverse stress testing, and comprehensive scenario analysis.

This module extends the basic stress testing capabilities with:
- Multi-factor stress testing
- Reverse stress testing (finding scenarios that cause specific losses)
- Factor sensitivity analysis
- Correlation stress testing

Author: QuantSys V2 Advanced Risk Module
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Union, Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from scipy import optimize
from scipy.stats import norm

from domain.quantlib import BaseCalculator
from domain.quantlib.exceptions import (
    CalculationError,
    InsufficientDataError,
    DataValidationError,
    ConfigurationError
)


@dataclass
class StressScenario:
    """
    Advanced stress scenario definition.

    Attributes:
        name: Scenario name
        description: Scenario description
        factor_shocks: Dictionary of factor shocks (factor_name -> shock_value)
        correlation_shock: Optional correlation matrix shock
        probability: Scenario probability
        severity: Severity level ('mild', 'moderate', 'severe', 'extreme')
    """
    name: str
    description: str
    factor_shocks: Dict[str, float]
    correlation_shock: Optional[np.ndarray] = None
    probability: float = 1.0
    severity: str = 'moderate'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'factor_shocks': self.factor_shocks,
            'probability': self.probability,
            'severity': self.severity
        }


class AdvancedStressTestCalculator(BaseCalculator):
    """
    Advanced Stress Test Calculator

    Performs sophisticated stress testing including:
    - Single and multi-factor stress tests
    - Reverse stress testing
    - Factor sensitivity analysis
    - Historical and hypothetical scenarios

    Methods:
        - single_factor_stress: Test impact of single factor shock
        - multi_factor_stress: Test impact of multiple simultaneous shocks
        - reverse_stress_test: Find scenarios causing specific loss levels
        - factor_sensitivity: Analyze sensitivity to each factor

    Example:
        calculator = AdvancedStressTestCalculator()
        result = calculator.calculate(
            portfolio_returns=returns,
            risk_factors=factors,
            stress_scenarios=[scenario1, scenario2],
            method='multi_factor'
        )
    """

    def __init__(self, precision: int = 6, risk_free_rate: float = 0.0):
        """
        Initialize Advanced Stress Test calculator.

        Args:
            precision: Number of decimal places for results
            risk_free_rate: Risk-free rate
        """
        super().__init__(precision=precision, risk_free_rate=risk_free_rate)

        # Predefined stress scenarios
        self.predefined_scenarios = self._define_predefined_scenarios()

    def calculate(self,
                  portfolio_returns: Union[np.ndarray, pd.Series],
                  risk_factors: Union[pd.DataFrame, np.ndarray],
                  stress_scenarios: Optional[List[StressScenario]] = None,
                  method: str = 'multi_factor',
                  factor_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Calculate stress test results.

        Args:
            portfolio_returns: Historical portfolio returns
            risk_factors: Risk factor returns/values (observations x factors)
            stress_scenarios: List of stress scenarios to test
            method: Stress test method ('single_factor', 'multi_factor', 'reverse')
            factor_names: Optional names for risk factors

        Returns:
            Dictionary with stress test results

        Raises:
            DataValidationError: If dimensions don't match
            ConfigurationError: If invalid method
            CalculationError: If calculation fails
        """
        # Validate inputs
        portfolio_returns = self._validate_returns(portfolio_returns, 'portfolio_returns')

        if isinstance(risk_factors, pd.DataFrame):
            factor_names = factor_names or risk_factors.columns.tolist()
            risk_factors_matrix = risk_factors.values
        else:
            risk_factors_matrix = np.array(risk_factors)
            if risk_factors_matrix.ndim == 1:
                risk_factors_matrix = risk_factors_matrix.reshape(-1, 1)
            factor_names = factor_names or [f'Factor_{i+1}' for i in range(risk_factors_matrix.shape[1])]

        # Validate dimensions
        if len(portfolio_returns) != risk_factors_matrix.shape[0]:
            raise DataValidationError(
                f"Portfolio returns length ({len(portfolio_returns)}) must match "
                f"risk factors observations ({risk_factors_matrix.shape[0]})"
            )

        # Check data sufficiency
        if len(portfolio_returns) < 30:
            raise InsufficientDataError(
                required=30,
                provided=len(portfolio_returns),
                calculation='Advanced Stress Test'
            )

        # Validate method
        method = self.validate_method(method)

        # Use predefined scenarios if none provided
        if stress_scenarios is None:
            stress_scenarios = self.predefined_scenarios

        try:
            # Estimate factor sensitivities (betas)
            factor_sensitivities = self._estimate_factor_sensitivities(
                portfolio_returns,
                risk_factors_matrix,
                factor_names
            )

            # Run stress tests based on method
            if method == 'single_factor':
                results = self._single_factor_stress(
                    portfolio_returns,
                    risk_factors_matrix,
                    factor_names,
                    factor_sensitivities,
                    stress_scenarios
                )
            elif method == 'multi_factor':
                results = self._multi_factor_stress(
                    portfolio_returns,
                    risk_factors_matrix,
                    factor_names,
                    factor_sensitivities,
                    stress_scenarios
                )
            elif method == 'reverse':
                results = self._reverse_stress_test(
                    portfolio_returns,
                    risk_factors_matrix,
                    factor_names,
                    factor_sensitivities
                )
            else:
                raise ConfigurationError(f"Unknown method: {method}", parameter='method')

            return self._create_result_dict(
                value=results,
                method=f'advanced_stress_test_{method}',
                parameters={
                    'n_observations': len(portfolio_returns),
                    'n_factors': len(factor_names),
                    'n_scenarios': len(stress_scenarios) if stress_scenarios else 0
                },
                metadata={
                    'factor_names': factor_names,
                    'interpretation': 'Negative stressed returns indicate portfolio losses'
                }
            )

        except Exception as e:
            if isinstance(e, (DataValidationError, ConfigurationError, InsufficientDataError)):
                raise
            raise CalculationError(str(e), calculation_type='Advanced Stress Test')

    def _estimate_factor_sensitivities(self,
                                       portfolio_returns: np.ndarray,
                                       risk_factors: np.ndarray,
                                       factor_names: List[str]) -> Dict[str, float]:
        """
        Estimate portfolio sensitivities to risk factors using linear regression.

        Returns:
            Dictionary of factor sensitivities (betas)
        """
        from scipy.linalg import lstsq

        # Add constant term for regression
        X = np.column_stack([np.ones(len(risk_factors)), risk_factors])

        # Solve least squares: portfolio_returns = alpha + beta1*factor1 + ... + error
        coefficients, _, _, _ = lstsq(X, portfolio_returns)

        # Extract betas (skip intercept)
        betas = coefficients[1:]

        return {factor_names[i]: float(betas[i]) for i in range(len(factor_names))}

    def _single_factor_stress(self,
                             portfolio_returns: np.ndarray,
                             risk_factors: np.ndarray,
                             factor_names: List[str],
                             sensitivities: Dict[str, float],
                             scenarios: List[StressScenario]) -> Dict[str, Any]:
        """
        Perform single-factor stress testing.

        Tests the impact of shocking one factor at a time.
        """
        baseline_return = np.mean(portfolio_returns)
        baseline_volatility = np.std(portfolio_returns, ddof=1)

        scenario_results = []

        for scenario in scenarios:
            for factor_name, shock in scenario.factor_shocks.items():
                if factor_name not in sensitivities:
                    self.logger.warning(f"Factor {factor_name} not found in sensitivities")
                    continue

                # Calculate stressed return: baseline + beta * shock
                beta = sensitivities[factor_name]
                stressed_return = baseline_return + beta * shock

                # Estimate stressed volatility (simplified)
                factor_idx = factor_names.index(factor_name)
                factor_vol = np.std(risk_factors[:, factor_idx], ddof=1)
                stressed_volatility = np.sqrt(baseline_volatility**2 + (beta * factor_vol * abs(shock))**2)

                loss = stressed_return - baseline_return
                loss_percentage = (loss / abs(baseline_return)) * 100 if baseline_return != 0 else 0

                scenario_results.append({
                    'scenario_name': f"{scenario.name} - {factor_name}",
                    'factor': factor_name,
                    'shock': float(shock),
                    'sensitivity': float(beta),
                    'stressed_return': float(stressed_return),
                    'stressed_volatility': float(stressed_volatility),
                    'loss_vs_baseline': float(loss),
                    'loss_percentage': float(loss_percentage),
                    'severity': scenario.severity
                })

        # Find worst case
        worst_case = min(scenario_results, key=lambda x: x['stressed_return'])

        return {
            'baseline_return': float(baseline_return),
            'baseline_volatility': float(baseline_volatility),
            'scenarios': scenario_results,
            'worst_case': worst_case,
            'factor_sensitivities': sensitivities
        }

    def _multi_factor_stress(self,
                            portfolio_returns: np.ndarray,
                            risk_factors: np.ndarray,
                            factor_names: List[str],
                            sensitivities: Dict[str, float],
                            scenarios: List[StressScenario]) -> Dict[str, Any]:
        """
        Perform multi-factor stress testing.

        Tests the impact of shocking multiple factors simultaneously.
        """
        baseline_return = np.mean(portfolio_returns)
        baseline_volatility = np.std(portfolio_returns, ddof=1)

        # Calculate factor covariance matrix
        factor_cov = np.cov(risk_factors.T)

        scenario_results = []

        for scenario in scenarios:
            # Calculate total impact from all factor shocks
            total_impact = 0.0
            factor_contributions = {}

            for factor_name, shock in scenario.factor_shocks.items():
                if factor_name not in sensitivities:
                    continue

                beta = sensitivities[factor_name]
                contribution = beta * shock
                total_impact += contribution
                factor_contributions[factor_name] = float(contribution)

            stressed_return = baseline_return + total_impact

            # Estimate stressed volatility considering correlations
            shock_vector = np.array([
                scenario.factor_shocks.get(name, 0.0) for name in factor_names
            ])
            beta_vector = np.array([sensitivities.get(name, 0.0) for name in factor_names])

            # Stressed variance = beta' * Cov * beta * shock_magnitude^2
            shock_magnitude = np.linalg.norm(shock_vector)
            stressed_var = baseline_volatility**2 + np.dot(beta_vector, np.dot(factor_cov, beta_vector)) * shock_magnitude**2
            stressed_volatility = np.sqrt(max(0, stressed_var))

            loss = stressed_return - baseline_return
            loss_percentage = (loss / abs(baseline_return)) * 100 if baseline_return != 0 else 0

            scenario_results.append({
                'scenario_name': scenario.name,
                'description': scenario.description,
                'stressed_return': float(stressed_return),
                'stressed_volatility': float(stressed_volatility),
                'loss_vs_baseline': float(loss),
                'loss_percentage': float(loss_percentage),
                'factor_contributions': factor_contributions,
                'probability': scenario.probability,
                'severity': scenario.severity
            })

        # Find worst case and calculate probability-weighted loss
        worst_case = min(scenario_results, key=lambda x: x['stressed_return'])

        total_prob = sum(s.probability for s in scenarios)
        weighted_loss = sum(
            r['loss_vs_baseline'] * scenarios[i].probability / total_prob
            for i, r in enumerate(scenario_results)
        )

        return {
            'baseline_return': float(baseline_return),
            'baseline_volatility': float(baseline_volatility),
            'scenarios': scenario_results,
            'worst_case': worst_case,
            'weighted_expected_loss': float(weighted_loss),
            'factor_sensitivities': sensitivities
        }

    def _reverse_stress_test(self,
                            portfolio_returns: np.ndarray,
                            risk_factors: np.ndarray,
                            factor_names: List[str],
                            sensitivities: Dict[str, float],
                            target_loss: float = -0.20) -> Dict[str, Any]:
        """
        Perform reverse stress testing.

        Finds the combination of factor shocks that would cause a specific loss level.

        Args:
            target_loss: Target loss level (e.g., -0.20 for 20% loss)
        """
        baseline_return = np.mean(portfolio_returns)

        # Convert sensitivities to array
        beta_vector = np.array([sensitivities.get(name, 0.0) for name in factor_names])

        # Objective: find shocks that produce target loss
        # loss = sum(beta_i * shock_i) = target_loss

        def objective(shocks):
            """Minimize squared error from target loss."""
            predicted_loss = np.dot(beta_vector, shocks)
            return (predicted_loss - target_loss)**2

        def constraint_magnitude(shocks):
            """Constraint: total shock magnitude should be reasonable."""
            return 2.0 - np.linalg.norm(shocks)  # Max 200% combined shock

        # Initial guess: distribute shock proportionally to betas
        x0 = np.zeros(len(factor_names))
        if np.sum(np.abs(beta_vector)) > 0:
            x0 = target_loss * beta_vector / np.sum(beta_vector**2)

        # Optimize
        constraints = {'type': 'ineq', 'fun': constraint_magnitude}
        bounds = [(-1.0, 1.0) for _ in range(len(factor_names))]  # Max ±100% shock per factor

        result = optimize.minimize(
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )

        if not result.success:
            self.logger.warning(f"Reverse stress test optimization did not converge: {result.message}")

        optimal_shocks = result.x
        achieved_loss = np.dot(beta_vector, optimal_shocks)

        # Create scenario from optimal shocks
        reverse_scenario = {
            'target_loss': float(target_loss),
            'achieved_loss': float(achieved_loss),
            'optimization_success': bool(result.success),
            'factor_shocks': {
                factor_names[i]: float(optimal_shocks[i])
                for i in range(len(factor_names))
            },
            'stressed_return': float(baseline_return + achieved_loss),
            'baseline_return': float(baseline_return)
        }

        # Find most critical factors (largest shocks)
        shock_magnitudes = [(factor_names[i], abs(optimal_shocks[i]))
                           for i in range(len(factor_names))]
        shock_magnitudes.sort(key=lambda x: x[1], reverse=True)

        reverse_scenario['critical_factors'] = [
            {'factor': name, 'shock': float(optimal_shocks[factor_names.index(name)])}
            for name, _ in shock_magnitudes[:5]  # Top 5
        ]

        return {
            'reverse_stress_scenario': reverse_scenario,
            'factor_sensitivities': sensitivities,
            'interpretation': 'Shows factor shocks needed to cause target loss'
        }

    def factor_sensitivity_analysis(self,
                                   portfolio_returns: Union[np.ndarray, pd.Series],
                                   risk_factors: Union[pd.DataFrame, np.ndarray],
                                   shock_range: Tuple[float, float] = (-0.50, 0.50),
                                   n_points: int = 21,
                                   factor_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyze portfolio sensitivity to each risk factor.

        Args:
            portfolio_returns: Historical portfolio returns
            risk_factors: Risk factor returns
            shock_range: Range of shocks to test (min, max)
            n_points: Number of points in shock range
            factor_names: Optional factor names

        Returns:
            Dictionary with sensitivity analysis results
        """
        portfolio_returns = self._validate_returns(portfolio_returns, 'portfolio_returns')

        if isinstance(risk_factors, pd.DataFrame):
            factor_names = factor_names or risk_factors.columns.tolist()
            risk_factors_matrix = risk_factors.values
        else:
            risk_factors_matrix = np.array(risk_factors)
            factor_names = factor_names or [f'Factor_{i+1}' for i in range(risk_factors_matrix.shape[1])]

        # Estimate sensitivities
        sensitivities = self._estimate_factor_sensitivities(
            portfolio_returns,
            risk_factors_matrix,
            factor_names
        )

        baseline_return = np.mean(portfolio_returns)
        shocks = np.linspace(shock_range[0], shock_range[1], n_points)

        sensitivity_results = {}

        for factor_name, beta in sensitivities.items():
            stressed_returns = [baseline_return + beta * shock for shock in shocks]

            sensitivity_results[factor_name] = {
                'beta': float(beta),
                'shocks': shocks.tolist(),
                'stressed_returns': stressed_returns,
                'sensitivity_score': float(abs(beta)),  # Higher = more sensitive
                'impact_range': float(max(stressed_returns) - min(stressed_returns))
            }

        # Rank factors by sensitivity
        ranked_factors = sorted(
            sensitivity_results.items(),
            key=lambda x: x[1]['sensitivity_score'],
            reverse=True
        )

        return self._create_result_dict(
            value={
                'sensitivity_by_factor': sensitivity_results,
                'ranked_factors': [
                    {'factor': name, 'sensitivity': data['sensitivity_score']}
                    for name, data in ranked_factors
                ],
                'baseline_return': float(baseline_return)
            },
            method='factor_sensitivity_analysis',
            parameters={
                'shock_range': shock_range,
                'n_points': n_points,
                'n_factors': len(factor_names)
            }
        )

    def _define_predefined_scenarios(self) -> List[StressScenario]:
        """
        Define predefined stress scenarios.
        """
        return [
            StressScenario(
                name='2008 Financial Crisis',
                description='Global financial crisis with equity crash and credit freeze',
                factor_shocks={
                    'equity': -0.40,
                    'credit_spread': 0.05,
                    'volatility': 0.80,
                    'liquidity': -0.50
                },
                probability=0.02,
                severity='extreme'
            ),
            StressScenario(
                name='2020 COVID-19 Pandemic',
                description='Pandemic-induced market crash',
                factor_shocks={
                    'equity': -0.35,
                    'volatility': 1.00,
                    'credit_spread': 0.03,
                    'liquidity': -0.30
                },
                probability=0.03,
                severity='severe'
            ),
            StressScenario(
                name='Interest Rate Shock',
                description='Sudden 200bp rate increase',
                factor_shocks={
                    'interest_rate': 0.02,
                    'equity': -0.15,
                    'credit_spread': 0.02,
                    'real_estate': -0.20
                },
                probability=0.10,
                severity='moderate'
            ),
            StressScenario(
                name='Inflation Surge',
                description='Rapid inflation acceleration',
                factor_shocks={
                    'inflation': 0.05,
                    'interest_rate': 0.03,
                    'equity': -0.10,
                    'bonds': -0.15
                },
                probability=0.15,
                severity='moderate'
            ),
            StressScenario(
                name='Geopolitical Crisis',
                description='Major geopolitical event',
                factor_shocks={
                    'equity': -0.25,
                    'volatility': 0.60,
                    'commodities': 0.30,
                    'safe_haven': 0.10
                },
                probability=0.08,
                severity='severe'
            )
        ]

    def get_supported_methods(self) -> List[str]:
        """Return list of supported calculation methods."""
        return ['single_factor', 'multi_factor', 'reverse']
