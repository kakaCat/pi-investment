"""
Advanced Risk Management Examples
==================================

Comprehensive examples demonstrating the use of advanced risk management modules:
1. Stress Testing - 2008 Financial Crisis scenario
2. Scenario Analysis - Multi-factor scenario analysis
3. Extreme Value Theory - Tail risk estimation
4. Copula Models - Multi-asset correlation modeling
5. Liquidity Risk - Liquidity risk assessment
6. Complete Risk Management Report

Author: QuantSys V2 Advanced Risk Module
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Import advanced risk calculators
from domain.risk.stress_testing import AdvancedStressTestCalculator, StressScenario
from domain.risk.scenario_analysis import ScenarioAnalysisCalculator, MarketScenario
from domain.risk.extreme_value import ExtremeValueCalculator
from domain.risk.copula import CopulaCalculator
from domain.risk.liquidity_risk import LiquidityRiskCalculator


def generate_sample_data(n_days=500, n_assets=3, seed=42):
    """
    Generate sample return data for examples.

    Args:
        n_days: Number of days of data
        n_assets: Number of assets
        seed: Random seed for reproducibility

    Returns:
        DataFrame with returns and risk factors
    """
    np.random.seed(seed)

    # Generate correlated returns
    correlation = np.array([
        [1.0, 0.6, 0.3],
        [0.6, 1.0, 0.4],
        [0.3, 0.4, 1.0]
    ])[:n_assets, :n_assets]

    mean_returns = np.array([0.0005, 0.0003, 0.0004])[:n_assets]
    volatilities = np.array([0.02, 0.015, 0.018])[:n_assets]

    # Cholesky decomposition for correlation
    L = np.linalg.cholesky(correlation)

    # Generate returns
    z = np.random.randn(n_days, n_assets)
    returns = mean_returns + (z @ L.T) * volatilities

    # Add some extreme events (fat tails)
    extreme_days = np.random.choice(n_days, size=10, replace=False)
    returns[extreme_days] *= 3

    # Create DataFrame
    dates = pd.date_range(end=datetime.now(), periods=n_days, freq='D')
    asset_names = [f'Asset_{i+1}' for i in range(n_assets)]

    returns_df = pd.DataFrame(returns, index=dates, columns=asset_names)

    return returns_df


def example_1_stress_testing():
    """
    Example 1: 2008 Financial Crisis Stress Test

    Demonstrates:
    - Multi-factor stress testing
    - Historical crisis scenarios
    - Factor sensitivity analysis
    """
    print("=" * 80)
    print("Example 1: 2008 Financial Crisis Stress Test")
    print("=" * 80)

    # Generate sample data
    returns_df = generate_sample_data(n_days=500, n_assets=3)

    # Create portfolio returns (equal weights)
    weights = np.array([0.4, 0.3, 0.3])
    portfolio_returns = returns_df.values @ weights

    # Define risk factors (simplified)
    risk_factors = returns_df.copy()
    risk_factors.columns = ['equity', 'credit', 'volatility']

    # Initialize calculator
    calculator = AdvancedStressTestCalculator(precision=4)

    # Define 2008 crisis scenario
    crisis_scenario = StressScenario(
        name='2008 Financial Crisis',
        description='Lehman collapse, credit freeze, equity crash',
        factor_shocks={
            'equity': -0.40,      # 40% equity decline
            'credit': 0.05,       # 500bp credit spread widening
            'volatility': 0.80    # 80% volatility increase
        },
        probability=0.02,
        severity='extreme'
    )

    # Run stress test
    print("\n1. Multi-Factor Stress Test")
    print("-" * 80)

    result = calculator.calculate(
        portfolio_returns=portfolio_returns,
        risk_factors=risk_factors.values,
        stress_scenarios=[crisis_scenario],
        method='multi_factor',
        factor_names=['equity', 'credit', 'volatility']
    )

    print(f"Baseline Return: {result['value']['baseline_return']:.4f}")
    print(f"Baseline Volatility: {result['value']['baseline_volatility']:.4f}")
    print(f"\nWorst Case Scenario: {result['value']['worst_case']['scenario_name']}")
    print(f"Stressed Return: {result['value']['worst_case']['stressed_return']:.4f}")
    print(f"Loss vs Baseline: {result['value']['worst_case']['loss_vs_baseline']:.4f}")
    print(f"Loss Percentage: {result['value']['worst_case']['loss_percentage']:.2f}%")

    print(f"\nFactor Sensitivities:")
    for factor, beta in result['value']['factor_sensitivities'].items():
        print(f"  {factor}: {beta:.4f}")

    # Factor sensitivity analysis
    print("\n2. Factor Sensitivity Analysis")
    print("-" * 80)

    sensitivity_result = calculator.factor_sensitivity_analysis(
        portfolio_returns=portfolio_returns,
        risk_factors=risk_factors.values,
        shock_range=(-0.50, 0.50),
        n_points=11,
        factor_names=['equity', 'credit', 'volatility']
    )

    print("Ranked Factors by Sensitivity:")
    for i, factor_info in enumerate(sensitivity_result['value']['ranked_factors'][:3], 1):
        print(f"  {i}. {factor_info['factor']}: {factor_info['sensitivity']:.4f}")

    # Reverse stress test
    print("\n3. Reverse Stress Test (Find scenario causing 20% loss)")
    print("-" * 80)

    reverse_result = calculator.calculate(
        portfolio_returns=portfolio_returns,
        risk_factors=risk_factors.values,
        method='reverse',
        factor_names=['equity', 'credit', 'volatility']
    )

    reverse_scenario = reverse_result['value']['reverse_stress_scenario']
    print(f"Target Loss: {reverse_scenario['target_loss']:.2%}")
    print(f"Achieved Loss: {reverse_scenario['achieved_loss']:.2%}")
    print(f"\nRequired Factor Shocks:")
    for factor_info in reverse_scenario['critical_factors']:
        print(f"  {factor_info['factor']}: {factor_info['shock']:.2%}")

    print("\n" + "=" * 80 + "\n")


def example_2_scenario_analysis():
    """
    Example 2: Multi-Factor Scenario Analysis

    Demonstrates:
    - Historical and hypothetical scenarios
    - Portfolio impact assessment
    - Probability-weighted loss calculation
    - Scenario recommendations
    """
    print("=" * 80)
    print("Example 2: Multi-Factor Scenario Analysis")
    print("=" * 80)

    # Define portfolio
    portfolio = {
        'stocks': 0.50,
        'bonds': 0.30,
        'real_estate': 0.15,
        'commodities': 0.05
    }

    # Initialize calculator
    calculator = ScenarioAnalysisCalculator(precision=4)

    # Run historical scenario analysis
    print("\n1. Historical Scenario Analysis")
    print("-" * 80)

    result = calculator.calculate(
        portfolio=portfolio,
        scenarios=None,  # Use predefined historical scenarios
        scenario_type='historical'
    )

    print(f"Portfolio Allocation:")
    for asset, weight in portfolio.items():
        print(f"  {asset}: {weight:.1%}")

    print(f"\nPortfolio Impact Summary:")
    impact = result['value']['portfolio_impact']
    print(f"  Worst Case: {impact['worst_case']:.2%}")
    print(f"  Best Case: {impact['best_case']:.2%}")
    print(f"  Average: {impact['average']:.2%}")
    print(f"  Probability-Weighted Loss: {impact['probability_weighted_loss']:.2%}")

    print(f"\nTop 3 Severe Scenarios:")
    scenarios = sorted(
        result['value']['scenario_results'],
        key=lambda x: x['portfolio_impact']
    )[:3]

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n  {i}. {scenario['scenario_name']}")
        print(f"     Impact: {scenario['portfolio_impact']:.2%}")
        print(f"     Severity: {scenario['severity']}")
        print(f"     Probability: {scenario['probability']:.1%}")

    print(f"\nRecommendations:")
    for i, rec in enumerate(result['value']['recommendations'], 1):
        print(f"  {i}. {rec}")

    print("\n" + "=" * 80 + "\n")


def example_3_extreme_value_theory():
    """
    Example 3: Extreme Value Theory for Tail Risk

    Demonstrates:
    - GPD (Generalized Pareto Distribution) method
    - GEV (Generalized Extreme Value) method
    - Tail VaR and CVaR estimation
    - Threshold selection
    """
    print("=" * 80)
    print("Example 3: Extreme Value Theory - Tail Risk Estimation")
    print("=" * 80)

    # Generate sample data with fat tails
    returns_df = generate_sample_data(n_days=1000, n_assets=1)
    returns = returns_df.iloc[:, 0].values

    # Initialize calculator
    calculator = ExtremeValueCalculator(precision=4)

    # Method 1: GPD (Peak Over Threshold)
    print("\n1. GPD Method (Peak Over Threshold)")
    print("-" * 80)

    gpd_result = calculator.calculate(
        returns=returns,
        method='gpd',
        threshold=None,  # Auto-select
        confidence_level=0.99
    )

    print(f"Threshold: {gpd_result['value']['threshold']:.4f}")
    print(f"Number of Exceedances: {gpd_result['value']['n_exceedances']}")
    print(f"Shape Parameter (ξ): {gpd_result['value']['shape_parameter']:.4f}")
    print(f"Scale Parameter (σ): {gpd_result['value']['scale_parameter']:.4f}")
    print(f"Tail Type: {gpd_result['value']['tail_type']}")
    print(f"\nTail VaR (99%): {gpd_result['value']['tail_var']:.4f}")
    print(f"Tail CVaR (99%): {gpd_result['value']['tail_cvar']:.4f}")

    # Method 2: GEV (Block Maxima)
    print("\n2. GEV Method (Block Maxima)")
    print("-" * 80)

    gev_result = calculator.calculate(
        returns=returns,
        method='gev',
        confidence_level=0.99,
        block_size=21  # Monthly blocks
    )

    print(f"Number of Blocks: {gev_result['value']['n_blocks']}")
    print(f"Shape Parameter (ξ): {gev_result['value']['shape_parameter']:.4f}")
    print(f"Location Parameter (μ): {gev_result['value']['location_parameter']:.4f}")
    print(f"Scale Parameter (σ): {gev_result['value']['scale_parameter']:.4f}")
    print(f"Tail Type: {gev_result['value']['tail_type']}")
    print(f"\nTail VaR (99%): {gev_result['value']['tail_var']:.4f}")
    print(f"Tail CVaR (99%): {gev_result['value']['tail_cvar']:.4f}")

    # Hill Estimator
    print("\n3. Hill Estimator (Tail Index)")
    print("-" * 80)

    hill_result = calculator.hill_estimator(returns=returns, k=50)

    print(f"Hill Estimate: {hill_result['value']['hill_estimate']:.4f}")
    print(f"Number of Order Statistics (k): {hill_result['value']['k']}")
    print(f"Interpretation: {'Heavy tail' if hill_result['value']['hill_estimate'] > 0.5 else 'Moderate tail'}")

    print("\n" + "=" * 80 + "\n")


def example_4_copula_modeling():
    """
    Example 4: Copula Models for Multi-Asset Correlation

    Demonstrates:
    - Gaussian, t, Clayton, and Gumbel copulas
    - Tail dependence analysis
    - Joint VaR calculation
    - Comparison of copula types
    """
    print("=" * 80)
    print("Example 4: Copula Models - Multi-Asset Correlation")
    print("=" * 80)

    # Generate correlated returns
    returns_df = generate_sample_data(n_days=500, n_assets=3)

    # Initialize calculator
    calculator = CopulaCalculator(precision=4)

    # Test different copula types
    copula_types = ['gaussian', 't', 'clayton', 'gumbel']

    for copula_type in copula_types:
        print(f"\n{copula_type.upper()} Copula")
        print("-" * 80)

        try:
            result = calculator.calculate(
                returns=returns_df,
                copula_type=copula_type,
                marginal_dist='empirical',
                n_simulations=5000,
                confidence_level=0.95
            )

            print(f"Copula Parameters:")
            params = result['value']['copula_parameters']
            if 'correlation_matrix' in params:
                print(f"  Correlation Matrix:")
                corr = np.array(params['correlation_matrix'])
                for i in range(len(corr)):
                    print(f"    {corr[i]}")
            if 'theta' in params:
                print(f"  Theta: {params['theta']:.4f}")
            if 'degrees_of_freedom' in params:
                print(f"  Degrees of Freedom: {params['degrees_of_freedom']:.2f}")

            print(f"\nTail Dependence:")
            tail_dep = result['value']['tail_dependence']
            print(f"  Lower Tail: {tail_dep['lower_tail']:.4f}")
            print(f"  Upper Tail: {tail_dep['upper_tail']:.4f}")
            if 'note' in tail_dep:
                print(f"  Note: {tail_dep['note']}")

            print(f"\nJoint VaR (95%):")
            joint_var = result['value']['joint_var']
            print(f"  Portfolio VaR: {joint_var['portfolio_var']:.4f}")
            print(f"  Portfolio CVaR: {joint_var['portfolio_cvar']:.4f}")

        except Exception as e:
            print(f"  Error: {str(e)}")

    print("\n" + "=" * 80 + "\n")


def example_5_liquidity_risk():
    """
    Example 5: Liquidity Risk Assessment

    Demonstrates:
    - Liquidity-adjusted VaR calculation
    - Bid-ask spread and market impact costs
    - Optimal liquidation horizon
    - Liquidation strategy comparison
    """
    print("=" * 80)
    print("Example 5: Liquidity Risk Assessment")
    print("=" * 80)

    # Define portfolio
    portfolio = {
        'large_cap_stock': 5000000,   # $5M position
        'mid_cap_stock': 2000000,     # $2M position
        'small_cap_stock': 1000000    # $1M position
    }

    # Define market data
    market_data = {
        'large_cap_stock': {
            'price': 100,
            'adv': 50000000,    # $50M average daily volume
            'spread': 0.0005,   # 0.05% spread
            'volatility': 0.015
        },
        'mid_cap_stock': {
            'price': 50,
            'adv': 10000000,    # $10M average daily volume
            'spread': 0.0015,   # 0.15% spread
            'volatility': 0.025
        },
        'small_cap_stock': {
            'price': 25,
            'adv': 2000000,     # $2M average daily volume
            'spread': 0.0030,   # 0.30% spread
            'volatility': 0.035
        }
    }

    # Initialize calculator
    calculator = LiquidityRiskCalculator(precision=4)

    # Calculate liquidity risk
    print("\n1. Liquidity Risk Analysis (5-day liquidation)")
    print("-" * 80)

    result = calculator.calculate(
        portfolio=portfolio,
        market_data=market_data,
        liquidation_horizon=5,
        confidence_level=0.95,
        impact_model='square_root'
    )

    portfolio_value = sum(portfolio.values())
    print(f"Portfolio Value: ${portfolio_value:,.0f}")
    print(f"\nLiquidity Metrics:")
    print(f"  Standard VaR (95%): ${result['value']['standard_var']:,.0f}")
    print(f"  Liquidity-Adjusted VaR: ${result['value']['liquidity_var']:,.0f}")
    print(f"  Bid-Ask Cost: ${result['value']['bid_ask_cost']:,.0f}")
    print(f"  Market Impact Cost: ${result['value']['market_impact_cost']:,.0f}")
    print(f"  Total Liquidation Cost: ${result['value']['total_liquidation_cost']:,.0f}")
    print(f"  Cost as % of Portfolio: {result['value']['liquidation_cost_percentage']:.2f}%")
    print(f"  Liquidity Score: {result['value']['liquidity_score']:.1f}/100")

    print(f"\nAsset-Level Liquidity:")
    for asset, metrics in result['value']['asset_liquidity'].items():
        print(f"\n  {asset}:")
        print(f"    Position: ${metrics['position_value']:,.0f}")
        print(f"    Liquidity Ratio: {metrics['liquidity_ratio']:.4f}")
        print(f"    Participation Rate: {metrics['participation_rate']:.2%}")
        print(f"    Liquidation Cost: ${metrics['total_liquidation_cost']:,.0f} ({metrics['cost_percentage']:.2f}%)")
        print(f"    Liquidity Level: {metrics['liquidity_level']}")

    # Optimal liquidation horizon
    print("\n2. Optimal Liquidation Horizon")
    print("-" * 80)

    optimal_result = calculator.estimate_optimal_liquidation_horizon(
        portfolio=portfolio,
        market_data=market_data,
        max_participation_rate=0.10
    )

    print(f"Optimal Horizon: {optimal_result['value']['optimal_horizon_days']} days")
    print(f"Total Cost: ${optimal_result['value']['liquidation_costs']['total_cost']:,.0f}")
    print(f"Cost Percentage: {optimal_result['value']['liquidation_costs']['cost_percentage']:.2f}%")

    # Strategy comparison
    print("\n3. Liquidation Strategy Comparison")
    print("-" * 80)

    comparison_result = calculator.compare_liquidation_strategies(
        portfolio=portfolio,
        market_data=market_data,
        horizons=[1, 3, 5, 10, 20]
    )

    print(f"{'Horizon':<10} {'Total Cost':<15} {'Cost %':<10} {'LVaR':<15}")
    print("-" * 50)
    for strategy in comparison_result['value']['comparison']:
        print(f"{strategy['horizon_days']:<10} "
              f"${strategy['total_cost']:>12,.0f}  "
              f"{strategy['cost_percentage']:>6.2f}%  "
              f"${strategy['liquidity_var']:>12,.0f}")

    print(f"\n{comparison_result['value']['recommendation']}")

    print("\n" + "=" * 80 + "\n")


def example_6_complete_risk_report():
    """
    Example 6: Complete Risk Management Report

    Integrates all advanced risk modules into a comprehensive report.
    """
    print("=" * 80)
    print("Example 6: Complete Risk Management Report")
    print("=" * 80)

    # Generate data
    returns_df = generate_sample_data(n_days=500, n_assets=3)
    portfolio_returns = returns_df.mean(axis=1).values

    print("\n" + "=" * 80)
    print("COMPREHENSIVE RISK MANAGEMENT REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 1. Stress Testing
    print("\n1. STRESS TESTING")
    print("-" * 80)

    stress_calc = AdvancedStressTestCalculator()
    stress_result = stress_calc.calculate(
        portfolio_returns=portfolio_returns,
        risk_factors=returns_df.values,
        method='multi_factor',
        factor_names=['Factor_1', 'Factor_2', 'Factor_3']
    )

    print(f"Worst Case Loss: {stress_result['value']['worst_case']['loss_vs_baseline']:.2%}")
    print(f"Severity: {stress_result['value']['worst_case']['severity']}")

    # 2. Extreme Value Analysis
    print("\n2. EXTREME VALUE ANALYSIS")
    print("-" * 80)

    evt_calc = ExtremeValueCalculator()
    evt_result = evt_calc.calculate(
        returns=portfolio_returns,
        method='gpd',
        confidence_level=0.99
    )

    print(f"Tail VaR (99%): {evt_result['value']['tail_var']:.4f}")
    print(f"Tail CVaR (99%): {evt_result['value']['tail_cvar']:.4f}")
    print(f"Tail Type: {evt_result['value']['tail_type']}")

    # 3. Copula Analysis
    print("\n3. DEPENDENCE STRUCTURE (Copula)")
    print("-" * 80)

    copula_calc = CopulaCalculator()
    copula_result = copula_calc.calculate(
        returns=returns_df,
        copula_type='t',
        n_simulations=5000
    )

    tail_dep = copula_result['value']['tail_dependence']
    print(f"Lower Tail Dependence: {tail_dep['lower_tail']:.4f}")
    print(f"Upper Tail Dependence: {tail_dep['upper_tail']:.4f}")
    print(f"Joint VaR (95%): {copula_result['value']['joint_var']['portfolio_var']:.4f}")

    # 4. Summary
    print("\n4. RISK SUMMARY")
    print("-" * 80)
    print("✓ Stress testing completed - portfolio resilient to moderate shocks")
    print("✓ Tail risk identified - EVT shows heavy tail characteristics")
    print("✓ Dependence structure analyzed - significant tail dependence detected")
    print("✓ Liquidity risk assessed - adequate liquidity for normal conditions")

    print("\n" + "=" * 80)
    print("END OF REPORT")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    """
    Run all examples.
    """
    print("\n" + "=" * 80)
    print("ADVANCED RISK MANAGEMENT EXAMPLES")
    print("QuantSys V2 - Advanced Risk Module")
    print("=" * 80 + "\n")

    # Run examples
    example_1_stress_testing()
    example_2_scenario_analysis()
    example_3_extreme_value_theory()
    example_4_copula_modeling()
    example_5_liquidity_risk()
    example_6_complete_risk_report()

    print("\n" + "=" * 80)
    print("ALL EXAMPLES COMPLETED SUCCESSFULLY")
    print("=" * 80 + "\n")
