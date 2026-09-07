"""
Portfolio Optimization Examples
================================

Comprehensive examples demonstrating portfolio optimization techniques.

Examples:
    1. Basic Markowitz optimization
    2. Black-Litterman with subjective views
    3. Risk parity portfolio
    4. Efficient frontier analysis
    5. Portfolio optimization with constraints
    6. Complete portfolio construction workflow

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from typing import Dict, Any

from domain.quantlib.portfolio import (
    MarkowitzOptimizer,
    BlackLittermanOptimizer,
    RiskParityOptimizer,
    EfficientFrontierCalculator,
    ConstraintManager
)


def example_1_basic_markowitz():
    """
    Example 1: Basic Markowitz Mean-Variance Optimization

    Demonstrates three optimization objectives:
    - Minimum variance
    - Maximum Sharpe ratio
    - Target return
    """
    print("=" * 80)
    print("Example 1: Basic Markowitz Optimization")
    print("=" * 80)

    # Sample data: 5 assets
    asset_names = ['Stock A', 'Stock B', 'Stock C', 'Bond D', 'Bond E']
    n_assets = len(asset_names)

    # Expected annual returns
    expected_returns = np.array([0.12, 0.10, 0.15, 0.05, 0.06])

    # Covariance matrix (annualized)
    cov_matrix = np.array([
        [0.04, 0.02, 0.03, 0.01, 0.01],
        [0.02, 0.03, 0.02, 0.01, 0.01],
        [0.03, 0.02, 0.06, 0.01, 0.01],
        [0.01, 0.01, 0.01, 0.01, 0.005],
        [0.01, 0.01, 0.01, 0.005, 0.01]
    ])

    risk_free_rate = 0.03

    # Create optimizer
    optimizer = MarkowitzOptimizer(precision=4, risk_free_rate=risk_free_rate)

    # 1. Minimum variance portfolio
    print("\n1. Minimum Variance Portfolio")
    print("-" * 40)
    result_min_var = optimizer.optimize(
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        objective='min_variance'
    )

    weights_min_var = result_min_var['value']['weights']
    print(f"Expected Return: {result_min_var['value']['expected_return']:.4f}")
    print(f"Risk (Std Dev):  {result_min_var['value']['risk']:.4f}")
    print(f"Sharpe Ratio:    {result_min_var['value']['sharpe_ratio']:.4f}")
    print("\nWeights:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {weights_min_var[i]:.4f}")

    # 2. Maximum Sharpe ratio portfolio
    print("\n2. Maximum Sharpe Ratio Portfolio")
    print("-" * 40)
    result_max_sharpe = optimizer.optimize(
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        objective='max_sharpe',
        risk_free_rate=risk_free_rate
    )

    weights_max_sharpe = result_max_sharpe['value']['weights']
    print(f"Expected Return: {result_max_sharpe['value']['expected_return']:.4f}")
    print(f"Risk (Std Dev):  {result_max_sharpe['value']['risk']:.4f}")
    print(f"Sharpe Ratio:    {result_max_sharpe['value']['sharpe_ratio']:.4f}")
    print("\nWeights:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {weights_max_sharpe[i]:.4f}")

    # 3. Target return portfolio
    print("\n3. Target Return Portfolio (10% return)")
    print("-" * 40)
    result_target = optimizer.optimize(
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        objective='target_return',
        target_return=0.10
    )

    weights_target = result_target['value']['weights']
    print(f"Expected Return: {result_target['value']['expected_return']:.4f}")
    print(f"Risk (Std Dev):  {result_target['value']['risk']:.4f}")
    print(f"Sharpe Ratio:    {result_target['value']['sharpe_ratio']:.4f}")
    print("\nWeights:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {weights_target[i]:.4f}")

    return {
        'min_variance': result_min_var,
        'max_sharpe': result_max_sharpe,
        'target_return': result_target
    }


def example_2_black_litterman():
    """
    Example 2: Black-Litterman Model with Subjective Views

    Demonstrates how to incorporate investor views into portfolio optimization.
    """
    print("\n" + "=" * 80)
    print("Example 2: Black-Litterman Model")
    print("=" * 80)

    # Sample data: 4 assets
    asset_names = ['US Stocks', 'EU Stocks', 'Bonds', 'Commodities']
    n_assets = len(asset_names)

    # Market capitalization weights (equilibrium)
    market_weights = np.array([0.40, 0.30, 0.20, 0.10])

    # Covariance matrix
    cov_matrix = np.array([
        [0.04, 0.02, 0.01, 0.015],
        [0.02, 0.05, 0.01, 0.02],
        [0.01, 0.01, 0.01, 0.005],
        [0.015, 0.02, 0.005, 0.06]
    ])

    risk_aversion = 2.5
    risk_free_rate = 0.02

    # Create optimizer
    optimizer = BlackLittermanOptimizer(precision=4, risk_free_rate=risk_free_rate)

    # 1. No views (equilibrium portfolio)
    print("\n1. Equilibrium Portfolio (No Views)")
    print("-" * 40)
    result_no_views = optimizer.optimize(
        market_weights=market_weights,
        cov_matrix=cov_matrix,
        views=None,
        risk_aversion=risk_aversion
    )

    print("Equilibrium Returns:")
    eq_returns = result_no_views['value']['equilibrium_returns']
    for i, name in enumerate(asset_names):
        print(f"  {name}: {eq_returns[i]:.4f}")

    print("\nOptimal Weights:")
    weights_no_views = result_no_views['value']['weights']
    for i, name in enumerate(asset_names):
        print(f"  {name}: {weights_no_views[i]:.4f}")

    # 2. With subjective views
    print("\n2. Portfolio with Subjective Views")
    print("-" * 40)

    # Define views
    views = [
        # Absolute view: US Stocks will return 12%
        {'assets': [0], 'return': 0.12, 'confidence': 0.7},

        # Relative view: EU Stocks will outperform Bonds by 5%
        {'assets': [1, 2], 'return': 0.05, 'confidence': 0.5},

        # Absolute view: Commodities will return 8%
        {'assets': [3], 'return': 0.08, 'confidence': 0.6}
    ]

    print("Views:")
    print("  1. US Stocks will return 12% (confidence: 70%)")
    print("  2. EU Stocks will outperform Bonds by 5% (confidence: 50%)")
    print("  3. Commodities will return 8% (confidence: 60%)")

    result_with_views = optimizer.optimize(
        market_weights=market_weights,
        cov_matrix=cov_matrix,
        views=views,
        risk_aversion=risk_aversion,
        tau=0.025
    )

    print("\nPosterior Returns:")
    post_returns = result_with_views['value']['posterior_returns']
    for i, name in enumerate(asset_names):
        print(f"  {name}: {post_returns[i]:.4f} (change: {post_returns[i] - eq_returns[i]:+.4f})")

    print("\nOptimal Weights:")
    weights_with_views = result_with_views['value']['weights']
    for i, name in enumerate(asset_names):
        change = weights_with_views[i] - market_weights[i]
        print(f"  {name}: {weights_with_views[i]:.4f} (change: {change:+.4f})")

    print(f"\nPortfolio Expected Return: {result_with_views['value']['expected_return']:.4f}")
    print(f"Portfolio Risk: {result_with_views['value']['risk']:.4f}")

    return {
        'no_views': result_no_views,
        'with_views': result_with_views
    }


def example_3_risk_parity():
    """
    Example 3: Risk Parity Portfolio

    Demonstrates equal risk contribution portfolio construction.
    """
    print("\n" + "=" * 80)
    print("Example 3: Risk Parity Portfolio")
    print("=" * 80)

    # Sample data: 3 asset classes
    asset_names = ['Stocks', 'Bonds', 'Commodities']
    n_assets = len(asset_names)

    # Covariance matrix
    cov_matrix = np.array([
        [0.04, 0.01, 0.02],
        [0.01, 0.01, 0.005],
        [0.02, 0.005, 0.06]
    ])

    # Create optimizer
    optimizer = RiskParityOptimizer(precision=4)

    # 1. Equal risk contribution
    print("\n1. Equal Risk Contribution Portfolio")
    print("-" * 40)
    result_equal = optimizer.optimize(cov_matrix=cov_matrix)

    weights_equal = result_equal['value']['weights']
    risk_contrib = result_equal['value']['risk_contributions']

    print("Weights:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {weights_equal[i]:.4f}")

    print("\nRisk Contributions:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {risk_contrib[i]:.4f} ({risk_contrib[i]*100:.2f}%)")

    print(f"\nPortfolio Volatility: {result_equal['value']['portfolio_volatility']:.4f}")

    # 2. Custom target risk contributions
    print("\n2. Custom Target Risk Contributions")
    print("-" * 40)
    print("Target: Stocks 50%, Bonds 30%, Commodities 20%")

    target_risk = np.array([0.50, 0.30, 0.20])
    result_custom = optimizer.optimize(
        cov_matrix=cov_matrix,
        target_risk=target_risk
    )

    weights_custom = result_custom['value']['weights']
    risk_contrib_custom = result_custom['value']['risk_contributions']

    print("\nWeights:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {weights_custom[i]:.4f}")

    print("\nRisk Contributions:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {risk_contrib_custom[i]:.4f} (target: {target_risk[i]:.4f})")

    print(f"\nPortfolio Volatility: {result_custom['value']['portfolio_volatility']:.4f}")

    # 3. With target volatility (leverage)
    print("\n3. Risk Parity with Target Volatility (10%)")
    print("-" * 40)

    result_leveraged = optimizer.optimize(
        cov_matrix=cov_matrix,
        target_volatility=0.10
    )

    weights_leveraged = result_leveraged['value']['weights']
    leverage = result_leveraged['value']['leverage']

    print("Weights (leveraged):")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {weights_leveraged[i]:.4f}")

    print(f"\nLeverage Ratio: {leverage:.4f}")
    print(f"Portfolio Volatility: {result_leveraged['value']['portfolio_volatility']:.4f}")

    return {
        'equal_risk': result_equal,
        'custom_risk': result_custom,
        'leveraged': result_leveraged
    }


def example_4_efficient_frontier():
    """
    Example 4: Efficient Frontier Analysis

    Demonstrates efficient frontier calculation and optimal portfolio identification.
    """
    print("\n" + "=" * 80)
    print("Example 4: Efficient Frontier Analysis")
    print("=" * 80)

    # Sample data: 4 assets
    asset_names = ['Stock A', 'Stock B', 'Bond C', 'Bond D']
    n_assets = len(asset_names)

    # Expected returns
    expected_returns = np.array([0.12, 0.10, 0.05, 0.06])

    # Covariance matrix
    cov_matrix = np.array([
        [0.04, 0.02, 0.01, 0.01],
        [0.02, 0.03, 0.01, 0.01],
        [0.01, 0.01, 0.01, 0.005],
        [0.01, 0.01, 0.005, 0.01]
    ])

    risk_free_rate = 0.03

    # Create calculator
    calculator = EfficientFrontierCalculator(precision=4, risk_free_rate=risk_free_rate)

    # Calculate efficient frontier
    print("\nCalculating Efficient Frontier (30 points)...")
    result = calculator.calculate(
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        risk_free_rate=risk_free_rate,
        n_points=30
    )

    # Display key portfolios
    print("\n1. Minimum Variance Portfolio")
    print("-" * 40)
    min_var = result['value']['min_variance_portfolio']
    print(f"Expected Return: {min_var['return']:.4f}")
    print(f"Risk (Std Dev):  {min_var['risk']:.4f}")
    print(f"Sharpe Ratio:    {min_var['sharpe_ratio']:.4f}")
    print("\nWeights:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {min_var['weights'][i]:.4f}")

    print("\n2. Maximum Sharpe Ratio Portfolio (Tangency)")
    print("-" * 40)
    max_sharpe = result['value']['max_sharpe_portfolio']
    print(f"Expected Return: {max_sharpe['return']:.4f}")
    print(f"Risk (Std Dev):  {max_sharpe['risk']:.4f}")
    print(f"Sharpe Ratio:    {max_sharpe['sharpe_ratio']:.4f}")
    print("\nWeights:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {max_sharpe['weights'][i]:.4f}")

    print("\n3. Capital Market Line (CML)")
    print("-" * 40)
    cml_slope = result['value']['cml_slope']
    cml_intercept = result['value']['cml_intercept']
    print(f"CML Equation: E[R] = {cml_intercept:.4f} + {cml_slope:.4f} * σ")
    print(f"Slope (Sharpe Ratio): {cml_slope:.4f}")

    # Display frontier points
    print("\n4. Efficient Frontier Points (sample)")
    print("-" * 40)
    print(f"{'Return':<10} {'Risk':<10} {'Sharpe':<10}")
    print("-" * 30)
    frontier = result['value']['frontier']
    for i in range(0, len(frontier), 5):  # Show every 5th point
        point = frontier[i]
        print(f"{point['return']:<10.4f} {point['risk']:<10.4f} {point['sharpe_ratio']:<10.4f}")

    # Calculate CML portfolio for target risk
    print("\n5. Portfolio on CML with Target Risk (12%)")
    print("-" * 40)
    cml_result = calculator.calculate_cml_portfolio(
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        target_risk=0.12,
        risk_free_rate=risk_free_rate
    )

    print(f"Expected Return: {cml_result['value']['expected_return']:.4f}")
    print(f"Risk (Std Dev):  {cml_result['value']['risk']:.4f}")
    print(f"Sharpe Ratio:    {cml_result['value']['sharpe_ratio']:.4f}")
    print(f"Risk-Free Weight: {cml_result['value']['risk_free_weight']:.4f}")
    print(f"Leverage: {cml_result['value']['leverage']:.4f}")

    return result


def example_5_constrained_optimization():
    """
    Example 5: Portfolio Optimization with Constraints

    Demonstrates various constraint types:
    - Weight bounds
    - Sector constraints
    - Risk constraints
    """
    print("\n" + "=" * 80)
    print("Example 5: Constrained Portfolio Optimization")
    print("=" * 80)

    # Sample data: 6 assets across 3 sectors
    asset_names = ['Tech A', 'Tech B', 'Finance C', 'Finance D', 'Energy E', 'Energy F']
    n_assets = len(asset_names)

    # Expected returns
    expected_returns = np.array([0.15, 0.12, 0.10, 0.09, 0.11, 0.10])

    # Covariance matrix
    cov_matrix = np.array([
        [0.06, 0.03, 0.01, 0.01, 0.02, 0.02],
        [0.03, 0.05, 0.01, 0.01, 0.02, 0.02],
        [0.01, 0.01, 0.03, 0.02, 0.01, 0.01],
        [0.01, 0.01, 0.02, 0.03, 0.01, 0.01],
        [0.02, 0.02, 0.01, 0.01, 0.07, 0.04],
        [0.02, 0.02, 0.01, 0.01, 0.04, 0.06]
    ])

    risk_free_rate = 0.03

    # Sector mapping
    sector_map = {
        0: 'Tech', 1: 'Tech',
        2: 'Finance', 3: 'Finance',
        4: 'Energy', 5: 'Energy'
    }

    # 1. Unconstrained optimization
    print("\n1. Unconstrained Maximum Sharpe Portfolio")
    print("-" * 40)

    optimizer = MarkowitzOptimizer(precision=4, risk_free_rate=risk_free_rate)
    result_unconstrained = optimizer.optimize(
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        objective='max_sharpe'
    )

    weights_unconstrained = result_unconstrained['value']['weights']
    print("Weights:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {weights_unconstrained[i]:.4f}")

    print(f"\nExpected Return: {result_unconstrained['value']['expected_return']:.4f}")
    print(f"Risk: {result_unconstrained['value']['risk']:.4f}")
    print(f"Sharpe Ratio: {result_unconstrained['value']['sharpe_ratio']:.4f}")

    # 2. With position limits
    print("\n2. With Position Limits (max 25% per asset)")
    print("-" * 40)

    result_bounded = optimizer.optimize(
        expected_returns=expected_returns,
        cov_matrix=cov_matrix,
        objective='max_sharpe',
        upper_bound=0.25
    )

    weights_bounded = result_bounded['value']['weights']
    print("Weights:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {weights_bounded[i]:.4f}")

    print(f"\nExpected Return: {result_bounded['value']['expected_return']:.4f}")
    print(f"Risk: {result_bounded['value']['risk']:.4f}")
    print(f"Sharpe Ratio: {result_bounded['value']['sharpe_ratio']:.4f}")

    # 3. With sector constraints
    print("\n3. With Sector Constraints")
    print("-" * 40)
    print("Constraints: Tech <= 40%, Finance <= 40%, Energy <= 30%")

    # Note: Sector constraints require custom implementation with ConstraintManager
    # For this example, we'll demonstrate the constraint setup

    constraint_mgr = ConstraintManager(n_assets=n_assets)
    constraint_mgr.add_weight_constraint(lower_bound=0.0, upper_bound=0.25)
    constraint_mgr.add_sector_constraint(
        sector_map=sector_map,
        sector_limits={'Tech': 0.40, 'Finance': 0.40, 'Energy': 0.30}
    )

    print("\nConstraint Summary:")
    summary = constraint_mgr.get_constraint_summary()
    print(f"  Total constraints: {summary['n_constraints']}")
    print(f"  Has bounds: {summary['has_bounds']}")
    print(f"  Constraint types: {summary['constraint_types']}")

    # Validate unconstrained portfolio against constraints
    validation = constraint_mgr.validate_weights(weights_unconstrained)
    print(f"\nUnconstrained portfolio satisfies sector constraints: {validation['satisfied']}")
    if not validation['satisfied']:
        print(f"  Violations: {validation['n_violations']}")
        for violation in validation['violations']:
            print(f"    - {violation}")

    return {
        'unconstrained': result_unconstrained,
        'bounded': result_bounded,
        'constraint_manager': constraint_mgr
    }


def example_6_complete_workflow():
    """
    Example 6: Complete Portfolio Construction Workflow

    Demonstrates end-to-end portfolio construction:
    1. Calculate expected returns using factor model
    2. Estimate covariance matrix
    3. Apply Black-Litterman with views
    4. Optimize with constraints
    5. Analyze risk decomposition
    """
    print("\n" + "=" * 80)
    print("Example 6: Complete Portfolio Construction Workflow")
    print("=" * 80)

    # Sample data: 5 assets
    asset_names = ['Large Cap', 'Small Cap', 'International', 'Bonds', 'Real Estate']
    n_assets = len(asset_names)

    # Step 1: Market equilibrium
    print("\nStep 1: Market Equilibrium")
    print("-" * 40)

    market_weights = np.array([0.35, 0.15, 0.25, 0.20, 0.05])
    cov_matrix = np.array([
        [0.04, 0.025, 0.02, 0.01, 0.015],
        [0.025, 0.06, 0.03, 0.01, 0.02],
        [0.02, 0.03, 0.05, 0.01, 0.015],
        [0.01, 0.01, 0.01, 0.01, 0.005],
        [0.015, 0.02, 0.015, 0.005, 0.04]
    ])

    print("Market Weights:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {market_weights[i]:.4f}")

    # Step 2: Black-Litterman with views
    print("\nStep 2: Incorporate Investor Views")
    print("-" * 40)

    views = [
        {'assets': [0], 'return': 0.10, 'confidence': 0.6},  # Large Cap: 10%
        {'assets': [1, 0], 'return': 0.03, 'confidence': 0.5},  # Small Cap outperforms Large Cap by 3%
        {'assets': [4], 'return': 0.08, 'confidence': 0.7}  # Real Estate: 8%
    ]

    print("Views:")
    print("  1. Large Cap will return 10% (confidence: 60%)")
    print("  2. Small Cap will outperform Large Cap by 3% (confidence: 50%)")
    print("  3. Real Estate will return 8% (confidence: 70%)")

    bl_optimizer = BlackLittermanOptimizer(precision=4, risk_free_rate=0.025)
    bl_result = bl_optimizer.optimize(
        market_weights=market_weights,
        cov_matrix=cov_matrix,
        views=views,
        risk_aversion=2.5,
        tau=0.025
    )

    posterior_returns = bl_result['value']['posterior_returns']
    print("\nPosterior Expected Returns:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {posterior_returns[i]:.4f}")

    # Step 3: Optimize with constraints
    print("\nStep 3: Optimize with Constraints")
    print("-" * 40)
    print("Constraints: No asset > 30%, No short selling")

    markowitz = MarkowitzOptimizer(precision=4, risk_free_rate=0.025)
    optimal_result = markowitz.optimize(
        expected_returns=posterior_returns,
        cov_matrix=cov_matrix,
        objective='max_sharpe',
        upper_bound=0.30,
        allow_short=False
    )

    optimal_weights = optimal_result['value']['weights']
    print("\nOptimal Weights:")
    for i, name in enumerate(asset_names):
        change = optimal_weights[i] - market_weights[i]
        print(f"  {name}: {optimal_weights[i]:.4f} (change: {change:+.4f})")

    print(f"\nExpected Return: {optimal_result['value']['expected_return']:.4f}")
    print(f"Risk: {optimal_result['value']['risk']:.4f}")
    print(f"Sharpe Ratio: {optimal_result['value']['sharpe_ratio']:.4f}")

    # Step 4: Risk decomposition
    print("\nStep 4: Risk Decomposition")
    print("-" * 40)

    rp_optimizer = RiskParityOptimizer(precision=4)
    risk_decomp = rp_optimizer.calculate_risk_decomposition(
        weights=optimal_weights,
        cov_matrix=cov_matrix
    )

    risk_contrib = risk_decomp['value']['percentage_risk_contributions']
    print("Risk Contributions:")
    for i, name in enumerate(asset_names):
        print(f"  {name}: {risk_contrib[i]:.4f} ({risk_contrib[i]*100:.2f}%)")

    # Step 5: Summary
    print("\nStep 5: Portfolio Summary")
    print("-" * 40)
    print(f"Total Weight: {np.sum(optimal_weights):.4f}")
    print(f"Number of Holdings: {np.sum(optimal_weights > 0.01)}")
    print(f"Largest Position: {np.max(optimal_weights):.4f}")
    print(f"Smallest Position: {np.min(optimal_weights[optimal_weights > 0.01]):.4f}")
    print(f"Portfolio Concentration (HHI): {np.sum(optimal_weights**2):.4f}")

    return {
        'bl_result': bl_result,
        'optimal_portfolio': optimal_result,
        'risk_decomposition': risk_decomp
    }


def run_all_examples():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("PORTFOLIO OPTIMIZATION EXAMPLES")
    print("=" * 80)

    results = {}

    try:
        results['example_1'] = example_1_basic_markowitz()
    except Exception as e:
        print(f"\nExample 1 failed: {str(e)}")

    try:
        results['example_2'] = example_2_black_litterman()
    except Exception as e:
        print(f"\nExample 2 failed: {str(e)}")

    try:
        results['example_3'] = example_3_risk_parity()
    except Exception as e:
        print(f"\nExample 3 failed: {str(e)}")

    try:
        results['example_4'] = example_4_efficient_frontier()
    except Exception as e:
        print(f"\nExample 4 failed: {str(e)}")

    try:
        results['example_5'] = example_5_constrained_optimization()
    except Exception as e:
        print(f"\nExample 5 failed: {str(e)}")

    try:
        results['example_6'] = example_6_complete_workflow()
    except Exception as e:
        print(f"\nExample 6 failed: {str(e)}")

    print("\n" + "=" * 80)
    print("ALL EXAMPLES COMPLETED")
    print("=" * 80)

    return results


if __name__ == '__main__':
    # Run all examples
    results = run_all_examples()
