"""
Risk Management Module - Usage Examples
========================================

Comprehensive examples demonstrating all risk management calculators.

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Import risk calculators
from domain.quantlib.risk import (
    VaRCalculator,
    CVaRCalculator,
    DrawdownCalculator,
    MarketRiskCalculator,
    RiskAttributionCalculator,
    StressTestCalculator
)
from domain.quantlib.risk.stress_test import Scenario


def example_var_calculation():
    """Example: Calculate Value at Risk (VaR)"""
    print("\n" + "="*60)
    print("Example 1: Value at Risk (VaR) Calculation")
    print("="*60)

    # Generate sample returns
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 252)  # Daily returns for 1 year

    # Initialize calculator
    var_calc = VaRCalculator(precision=4)

    # Calculate VaR using different methods
    print("\n1. Historical VaR (95% confidence):")
    result = var_calc.calculate(returns, confidence_level=0.95, method='historical')
    print(f"   VaR: {result['value']:.4f} ({result['value']*100:.2f}%)")
    print(f"   Interpretation: {result['metadata']['interpretation']}")

    print("\n2. Parametric VaR (95% confidence):")
    result = var_calc.calculate(returns, confidence_level=0.95, method='parametric')
    print(f"   VaR: {result['value']:.4f}")

    print("\n3. Monte Carlo VaR (95% confidence):")
    result = var_calc.calculate(returns, confidence_level=0.95, method='monte_carlo', n_simulations=10000)
    print(f"   VaR: {result['value']:.4f}")

    print("\n4. Multiple confidence levels:")
    result = var_calc.calculate_multiple_confidence_levels(
        returns,
        confidence_levels=[0.90, 0.95, 0.99]
    )
    for key, value in result['value'].items():
        print(f"   {key}: {value:.4f}")


def example_cvar_calculation():
    """Example: Calculate Conditional Value at Risk (CVaR)"""
    print("\n" + "="*60)
    print("Example 2: Conditional Value at Risk (CVaR)")
    print("="*60)

    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 252)

    cvar_calc = CVaRCalculator(precision=4)

    print("\n1. CVaR vs VaR comparison:")
    result = cvar_calc.calculate_with_var(returns, confidence_level=0.95)
    print(f"   VaR (95%):  {result['value']['var']:.4f}")
    print(f"   CVaR (95%): {result['value']['cvar']:.4f}")
    print(f"   CVaR/VaR Ratio: {result['value']['cvar_var_ratio']:.2f}")
    print(f"\n   {result['metadata']['interpretation']}")


def example_drawdown_analysis():
    """Example: Drawdown Analysis"""
    print("\n" + "="*60)
    print("Example 3: Drawdown Analysis")
    print("="*60)

    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 252)

    dd_calc = DrawdownCalculator(precision=4)

    print("\n1. Comprehensive drawdown metrics:")
    result = dd_calc.calculate(returns)
    print(f"   Maximum Drawdown: {result['value']['max_drawdown']:.4f} ({result['value']['max_drawdown']*100:.2f}%)")
    print(f"   Average Drawdown: {result['value']['average_drawdown']:.4f}")
    print(f"   Current Drawdown: {result['value']['current_drawdown']:.4f}")
    print(f"   Ulcer Index: {result['value']['ulcer_index']:.4f}")
    print(f"   Calmar Ratio: {result['value']['calmar_ratio']:.4f}")
    print(f"   Number of Drawdown Periods: {result['value']['n_drawdown_periods']}")

    print("\n2. Calmar Ratio (Return/Max Drawdown):")
    result = dd_calc.calculate_calmar_ratio(returns)
    print(f"   Calmar Ratio: {result['value']:.4f}")
    print(f"   Annualized Return: {result['parameters']['annualized_return']:.4f}")
    print(f"   Max Drawdown: {result['parameters']['max_drawdown']:.4f}")


def example_market_risk():
    """Example: Market Risk Analysis"""
    print("\n" + "="*60)
    print("Example 4: Market Risk Analysis")
    print("="*60)

    np.random.seed(42)
    portfolio_returns = np.random.normal(0.001, 0.02, 252)
    benchmark_returns = np.random.normal(0.0008, 0.015, 252)

    market_calc = MarketRiskCalculator(risk_free_rate=0.02, precision=4)

    print("\n1. Comprehensive market risk metrics:")
    result = market_calc.calculate(portfolio_returns, benchmark_returns)
    print(f"   Beta: {result['value']['beta']:.4f}")
    print(f"   Alpha (annualized): {result['value']['alpha']:.4f}")
    print(f"   Correlation: {result['value']['correlation']:.4f}")
    print(f"   R-squared: {result['value']['r_squared']:.4f}")
    print(f"   Tracking Error: {result['value']['tracking_error']:.4f}")
    print(f"   Information Ratio: {result['value']['information_ratio']:.4f}")

    print("\n2. Risk decomposition:")
    result = market_calc.decompose_risk(portfolio_returns, benchmark_returns)
    print(f"   Total Volatility: {result['value']['total_volatility']:.4f}")
    print(f"   Systematic Volatility: {result['value']['systematic_volatility']:.4f} ({result['value']['systematic_percentage']:.1f}%)")
    print(f"   Idiosyncratic Volatility: {result['value']['idiosyncratic_volatility']:.4f} ({result['value']['idiosyncratic_percentage']:.1f}%)")


def example_risk_attribution():
    """Example: Risk Attribution"""
    print("\n" + "="*60)
    print("Example 5: Risk Attribution")
    print("="*60)

    np.random.seed(42)
    n_assets = 5
    n_observations = 252

    # Generate correlated returns
    returns = pd.DataFrame(
        np.random.normal(0.001, 0.02, (n_observations, n_assets)),
        columns=[f'Asset_{i+1}' for i in range(n_assets)]
    )
    weights = np.array([0.3, 0.25, 0.2, 0.15, 0.1])

    attr_calc = RiskAttributionCalculator(precision=4)

    print("\n1. Asset-level risk attribution:")
    result = attr_calc.calculate(returns, weights)
    print(f"   Portfolio Volatility: {result['value']['portfolio_volatility']:.4f}")
    print("\n   Individual Asset Contributions:")
    for asset, contrib in result['value']['contributions'].items():
        print(f"   {asset}:")
        print(f"      Weight: {contrib['weight']:.2%}")
        print(f"      Risk Contribution: {contrib['percentage_contribution']:.2f}%")

    print("\n2. Group attribution (by sector):")
    groups = ['Equity', 'Equity', 'Bond', 'Bond', 'Commodity']
    result = attr_calc.calculate_group_attribution(returns, weights, groups)
    print("\n   Group Risk Contributions:")
    for group, contrib in result['value']['group_contributions'].items():
        print(f"   {group}:")
        print(f"      Weight: {contrib['weight']:.2%}")
        print(f"      Risk Contribution: {contrib['percentage_contribution']:.2f}%")
        print(f"      Number of Assets: {contrib['n_assets']}")

    print("\n3. Concentration metrics:")
    result = attr_calc.calculate_concentration_metrics(returns, weights)
    print(f"   Herfindahl Index: {result['value']['herfindahl_index']:.4f}")
    print(f"   Effective Number of Assets: {result['value']['effective_n_assets']:.2f}")
    print(f"   Max Contributor: {result['value']['max_contributor']} ({result['value']['max_contribution']:.2f}%)")
    print(f"   Top 3 Contribution: {result['value']['top_3_contribution']:.2f}%")


def example_stress_testing():
    """Example: Stress Testing"""
    print("\n" + "="*60)
    print("Example 6: Stress Testing")
    print("="*60)

    np.random.seed(42)
    n_assets = 5
    returns = pd.DataFrame(
        np.random.normal(0.001, 0.02, (252, n_assets)),
        columns=[f'Asset_{i+1}' for i in range(n_assets)]
    )
    weights = np.array([0.3, 0.25, 0.2, 0.15, 0.1])

    stress_calc = StressTestCalculator(precision=4)

    print("\n1. Custom stress scenarios:")
    scenarios = [
        Scenario(
            name='Market Crash',
            description='Severe equity market downturn',
            shocks={'Asset_1': -0.30, 'Asset_2': -0.25, 'Asset_3': -0.20, 'Asset_4': -0.10, 'Asset_5': -0.35},
            probability=0.05
        ),
        Scenario(
            name='Mild Correction',
            description='Moderate market correction',
            shocks={'Asset_1': -0.10, 'Asset_2': -0.08, 'Asset_3': -0.05, 'Asset_4': -0.03, 'Asset_5': -0.12},
            probability=0.15
        ),
        Scenario(
            name='Recovery Rally',
            description='Strong market recovery',
            shocks={'Asset_1': 0.20, 'Asset_2': 0.15, 'Asset_3': 0.10, 'Asset_4': 0.08, 'Asset_5': 0.25},
            probability=0.10
        )
    ]

    result = stress_calc.calculate(returns, weights, scenarios)
    print(f"   Baseline Return: {result['value']['baseline_return']:.4f}")
    print(f"\n   Scenario Results:")
    for scenario in result['value']['scenarios']:
        print(f"   {scenario['scenario_name']}:")
        print(f"      Portfolio Return: {scenario['portfolio_return']:.4f}")
        print(f"      Loss vs Baseline: {scenario['loss_vs_baseline']:.4f} ({scenario['loss_percentage']:.2f}%)")

    print(f"\n   Worst Case: {result['value']['worst_case']:.4f}")
    print(f"   Best Case: {result['value']['best_case']:.4f}")

    print("\n2. Sensitivity analysis:")
    result = stress_calc.sensitivity_analysis(returns, weights, shock_range=(-0.30, 0.30), n_points=7)
    print("   Asset sensitivities (volatility of portfolio returns to shocks):")
    for asset, data in result['value'].items():
        print(f"   {asset}: {data['sensitivity']:.4f} (weight: {data['weight']:.2%})")


def example_integrated_risk_report():
    """Example: Integrated Risk Report"""
    print("\n" + "="*60)
    print("Example 7: Integrated Risk Report")
    print("="*60)

    np.random.seed(42)
    portfolio_returns = np.random.normal(0.001, 0.02, 252)
    benchmark_returns = np.random.normal(0.0008, 0.015, 252)

    print("\n=== Portfolio Risk Summary ===\n")

    # VaR
    var_calc = VaRCalculator()
    var_result = var_calc.calculate(portfolio_returns, confidence_level=0.95)
    print(f"VaR (95%): {var_result['value']:.4f}")

    # CVaR
    cvar_calc = CVaRCalculator()
    cvar_result = cvar_calc.calculate(portfolio_returns, confidence_level=0.95)
    print(f"CVaR (95%): {cvar_result['value']:.4f}")

    # Drawdown
    dd_calc = DrawdownCalculator()
    dd_result = dd_calc.calculate(portfolio_returns)
    print(f"Max Drawdown: {dd_result['value']['max_drawdown']:.4f}")
    print(f"Calmar Ratio: {dd_result['value']['calmar_ratio']:.4f}")

    # Market Risk
    market_calc = MarketRiskCalculator(risk_free_rate=0.02)
    market_result = market_calc.calculate(portfolio_returns, benchmark_returns)
    print(f"Beta: {market_result['value']['beta']:.4f}")
    print(f"Alpha: {market_result['value']['alpha']:.4f}")
    print(f"Information Ratio: {market_result['value']['information_ratio']:.4f}")

    print("\n=== Risk Assessment ===")
    print(f"Tail Risk (CVaR/VaR): {cvar_result['value']/var_result['value']:.2f}x")
    print(f"Market Sensitivity: {'High' if abs(market_result['value']['beta']) > 1.2 else 'Moderate' if abs(market_result['value']['beta']) > 0.8 else 'Low'}")
    print(f"Drawdown Risk: {'High' if dd_result['value']['max_drawdown'] > 0.20 else 'Moderate' if dd_result['value']['max_drawdown'] > 0.10 else 'Low'}")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("QuantLib Risk Management Module - Usage Examples")
    print("="*60)

    example_var_calculation()
    example_cvar_calculation()
    example_drawdown_analysis()
    example_market_risk()
    example_risk_attribution()
    example_stress_testing()
    example_integrated_risk_report()

    print("\n" + "="*60)
    print("All examples completed successfully!")
    print("="*60 + "\n")
