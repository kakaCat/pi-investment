"""
Factor Models Examples
======================

Comprehensive examples demonstrating the use of factor models:
    - Fama-French 3-factor and 5-factor models
    - Carhart 4-factor model
    - Barra risk model
    - Factor exposure analysis

Author: QuantSys V2
Date: 2026-05-24
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from domain.quantlib.factor_models import (
    FamaFrench3FactorCalculator,
    FamaFrench5FactorCalculator,
    FamaFrenchFactorBuilder,
    CarhartFourFactorCalculator,
    MomentumFactorBuilder,
    BarraRiskModelCalculator,
    BarraFactorBuilder,
    FactorExposureCalculator
)


def example_1_fama_french_3factor():
    """
    Example 1: Fama-French 3-Factor Model

    Analyze a mutual fund's performance using the Fama-French 3-factor model.
    """
    print("=" * 80)
    print("Example 1: Fama-French 3-Factor Model")
    print("=" * 80)

    # Generate sample data (in practice, load from database or API)
    np.random.seed(42)
    n_months = 120  # 10 years of monthly data
    dates = pd.date_range(start='2015-01-01', periods=n_months, freq='ME')

    # Fund returns (slightly outperforming market)
    fund_returns = pd.Series(
        np.random.normal(0.012, 0.05, n_months),
        index=dates,
        name='Fund Returns'
    )

    # Market returns
    market_returns = pd.Series(
        np.random.normal(0.010, 0.04, n_months),
        index=dates,
        name='Market Returns'
    )

    # Risk-free rate (annual 2%, monthly)
    risk_free_rate = 0.02 / 12

    # Factor returns
    smb_factor = pd.Series(np.random.normal(0.002, 0.03, n_months), index=dates, name='SMB')
    hml_factor = pd.Series(np.random.normal(0.001, 0.025, n_months), index=dates, name='HML')

    # Run 3-factor model
    calculator = FamaFrench3FactorCalculator(precision=4)
    result = calculator.calculate(
        asset_returns=fund_returns,
        market_returns=market_returns,
        risk_free_rate=risk_free_rate,
        smb_factor=smb_factor,
        hml_factor=hml_factor,
        return_residuals=False
    )

    # Display results
    print("\nFama-French 3-Factor Regression Results:")
    print("-" * 80)
    print(f"Alpha (Jensen's Alpha):     {result['value']['alpha']:.4f} ({result['value']['alpha']*12:.2%} annualized)")
    print(f"Market Beta (β_MKT):        {result['value']['beta_mkt']:.4f}")
    print(f"Size Beta (β_SMB):          {result['value']['beta_smb']:.4f}")
    print(f"Value Beta (β_HML):         {result['value']['beta_hml']:.4f}")
    print(f"\nR-squared:                  {result['value']['r_squared']:.4f}")
    print(f"Adjusted R-squared:         {result['value']['adj_r_squared']:.4f}")

    print("\nStatistical Significance:")
    print("-" * 80)
    for coef in ['alpha', 'beta_mkt', 'beta_smb', 'beta_hml']:
        t_stat = result['value']['t_stats'][coef]
        p_val = result['value']['p_values'][coef]
        sig = "***" if p_val < 0.01 else "**" if p_val < 0.05 else "*" if p_val < 0.1 else ""
        print(f"{coef:20s}: t-stat = {t_stat:7.3f}, p-value = {p_val:.4f} {sig}")

    print("\nInterpretation:")
    print("-" * 80)
    if result['value']['alpha'] > 0 and result['value']['p_values']['alpha'] < 0.05:
        print("✓ Positive and significant alpha - fund generates excess returns")
    else:
        print("✗ Alpha not significant - no evidence of skill")

    if result['value']['beta_mkt'] > 1:
        print(f"✓ Market beta > 1 ({result['value']['beta_mkt']:.2f}) - fund is more volatile than market")
    else:
        print(f"✓ Market beta < 1 ({result['value']['beta_mkt']:.2f}) - fund is less volatile than market")

    if abs(result['value']['beta_smb']) > 0.3:
        tilt = "small-cap" if result['value']['beta_smb'] > 0 else "large-cap"
        print(f"✓ Significant size tilt toward {tilt} stocks")

    if abs(result['value']['beta_hml']) > 0.3:
        tilt = "value" if result['value']['beta_hml'] > 0 else "growth"
        print(f"✓ Significant style tilt toward {tilt} stocks")

    print("\n")


def example_2_fama_french_5factor():
    """
    Example 2: Fama-French 5-Factor Model

    Compare 3-factor and 5-factor models.
    """
    print("=" * 80)
    print("Example 2: Fama-French 5-Factor Model Comparison")
    print("=" * 80)

    # Generate sample data
    np.random.seed(42)
    n_months = 120
    dates = pd.date_range(start='2015-01-01', periods=n_months, freq='ME')

    fund_returns = pd.Series(np.random.normal(0.012, 0.05, n_months), index=dates)
    market_returns = pd.Series(np.random.normal(0.010, 0.04, n_months), index=dates)
    risk_free_rate = 0.02 / 12

    # All 5 factors
    factors = pd.DataFrame({
        'SMB': np.random.normal(0.002, 0.03, n_months),
        'HML': np.random.normal(0.001, 0.025, n_months),
        'RMW': np.random.normal(0.0015, 0.02, n_months),
        'CMA': np.random.normal(0.001, 0.02, n_months)
    }, index=dates)

    # Run 3-factor model
    calc3 = FamaFrench3FactorCalculator()
    result3 = calc3.calculate(
        asset_returns=fund_returns,
        market_returns=market_returns,
        risk_free_rate=risk_free_rate,
        smb_factor=factors['SMB'],
        hml_factor=factors['HML']
    )

    # Run 5-factor model
    calc5 = FamaFrench5FactorCalculator()
    result5 = calc5.calculate(
        asset_returns=fund_returns,
        market_returns=market_returns,
        risk_free_rate=risk_free_rate,
        smb_factor=factors['SMB'],
        hml_factor=factors['HML'],
        rmw_factor=factors['RMW'],
        cma_factor=factors['CMA']
    )

    # Compare results
    print("\nModel Comparison:")
    print("-" * 80)
    print(f"{'Metric':<25} {'3-Factor':<15} {'5-Factor':<15} {'Difference':<15}")
    print("-" * 80)
    print(f"{'Alpha':<25} {result3['value']['alpha']:>14.4f} {result5['value']['alpha']:>14.4f} {result5['value']['alpha']-result3['value']['alpha']:>14.4f}")
    print(f"{'Market Beta':<25} {result3['value']['beta_mkt']:>14.4f} {result5['value']['beta_mkt']:>14.4f} {result5['value']['beta_mkt']-result3['value']['beta_mkt']:>14.4f}")
    print(f"{'R-squared':<25} {result3['value']['r_squared']:>14.4f} {result5['value']['r_squared']:>14.4f} {result5['value']['r_squared']-result3['value']['r_squared']:>14.4f}")
    print(f"{'Adj. R-squared':<25} {result3['value']['adj_r_squared']:>14.4f} {result5['value']['adj_r_squared']:>14.4f} {result5['value']['adj_r_squared']-result3['value']['adj_r_squared']:>14.4f}")

    print("\n5-Factor Additional Betas:")
    print("-" * 80)
    print(f"Profitability Beta (β_RMW): {result5['value']['beta_rmw']:.4f}")
    print(f"Investment Beta (β_CMA):    {result5['value']['beta_cma']:.4f}")

    print("\n")


def example_3_build_factors():
    """
    Example 3: Building Fama-French Factors from Stock Data

    Construct SMB and HML factors from a universe of stocks.
    """
    print("=" * 80)
    print("Example 3: Building Fama-French Factors")
    print("=" * 80)

    # Generate sample stock universe
    np.random.seed(42)
    n_stocks = 100
    n_periods = 60

    stocks = [f'STOCK_{i:03d}' for i in range(n_stocks)]
    dates = pd.date_range(start='2020-01-01', periods=n_periods, freq='ME')

    # Stock returns
    returns = pd.DataFrame(
        np.random.normal(0.01, 0.05, (n_stocks, n_periods)),
        index=stocks,
        columns=dates
    )

    # Market caps (log-normal distribution)
    market_caps = pd.DataFrame(
        np.random.lognormal(10, 2, (n_stocks, n_periods)),
        index=stocks,
        columns=dates
    )

    # Book-to-market ratios
    book_to_market = pd.DataFrame(
        np.random.lognormal(0, 0.5, (n_stocks, n_periods)),
        index=stocks,
        columns=dates
    )

    # Build factors
    builder = FamaFrenchFactorBuilder(
        size_breakpoint=0.5,  # Median split
        value_breakpoints=(0.3, 0.7)  # 30th and 70th percentiles
    )

    print("\nBuilding SMB and HML factors...")
    smb, hml = builder.build_smb_hml(returns, market_caps, book_to_market)

    print(f"\nFactor Statistics (last 60 months):")
    print("-" * 80)
    print(f"{'Factor':<10} {'Mean':<12} {'Std Dev':<12} {'Sharpe':<12} {'Min':<12} {'Max':<12}")
    print("-" * 80)

    for name, factor in [('SMB', smb), ('HML', hml)]:
        factor_clean = factor.dropna()
        mean = factor_clean.mean()
        std = factor_clean.std()
        sharpe = mean / std * np.sqrt(12) if std > 0 else 0
        print(f"{name:<10} {mean:>11.4f} {std:>11.4f} {sharpe:>11.4f} {factor_clean.min():>11.4f} {factor_clean.max():>11.4f}")

    print("\n")


def example_4_carhart_momentum():
    """
    Example 4: Carhart 4-Factor Model with Momentum

    Analyze momentum strategy using Carhart model.
    """
    print("=" * 80)
    print("Example 4: Carhart 4-Factor Model (with Momentum)")
    print("=" * 80)

    # Generate sample data
    np.random.seed(42)
    n_months = 120
    dates = pd.date_range(start='2015-01-01', periods=n_months, freq='ME')

    # Momentum strategy returns (higher returns, higher volatility)
    strategy_returns = pd.Series(
        np.random.normal(0.015, 0.06, n_months),
        index=dates
    )

    market_returns = pd.Series(np.random.normal(0.010, 0.04, n_months), index=dates)
    risk_free_rate = 0.02 / 12

    # Factors
    smb = pd.Series(np.random.normal(0.002, 0.03, n_months), index=dates)
    hml = pd.Series(np.random.normal(0.001, 0.025, n_months), index=dates)
    mom = pd.Series(np.random.normal(0.005, 0.04, n_months), index=dates)  # Stronger momentum

    # Run Carhart 4-factor model
    calculator = CarhartFourFactorCalculator()
    result = calculator.calculate(
        asset_returns=strategy_returns,
        market_returns=market_returns,
        risk_free_rate=risk_free_rate,
        smb_factor=smb,
        hml_factor=hml,
        mom_factor=mom
    )

    print("\nCarhart 4-Factor Regression Results:")
    print("-" * 80)
    print(f"Alpha:                      {result['value']['alpha']:.4f}")
    print(f"Market Beta (β_MKT):        {result['value']['beta_mkt']:.4f}")
    print(f"Size Beta (β_SMB):          {result['value']['beta_smb']:.4f}")
    print(f"Value Beta (β_HML):         {result['value']['beta_hml']:.4f}")
    print(f"Momentum Beta (β_MOM):      {result['value']['beta_mom']:.4f}")
    print(f"\nR-squared:                  {result['value']['r_squared']:.4f}")

    print("\nMomentum Analysis:")
    print("-" * 80)
    mom_beta = result['value']['beta_mom']
    mom_pval = result['value']['p_values']['beta_mom']

    if mom_beta > 0.5 and mom_pval < 0.05:
        print(f"✓ Strong positive momentum exposure (β = {mom_beta:.2f}, p < 0.05)")
        print("  Strategy loads heavily on past winners")
    elif mom_beta > 0.2:
        print(f"✓ Moderate momentum exposure (β = {mom_beta:.2f})")
    else:
        print(f"✗ Low momentum exposure (β = {mom_beta:.2f})")

    print("\n")


def example_5_barra_risk_model():
    """
    Example 5: Barra Risk Model

    Decompose portfolio risk into factor and specific components.
    """
    print("=" * 80)
    print("Example 5: Barra Risk Model - Portfolio Risk Decomposition")
    print("=" * 80)

    # Generate sample portfolio
    np.random.seed(42)
    n_stocks = 30
    n_periods = 60

    stocks = [f'STOCK_{i:02d}' for i in range(n_stocks)]
    dates = pd.date_range(start='2020-01-01', periods=n_periods, freq='ME')

    # Stock returns (transpose: stocks x time)
    returns = pd.DataFrame(
        np.random.normal(0.01, 0.05, (n_stocks, n_periods)),
        index=stocks,
        columns=dates
    )

    # Factor exposures (current snapshot)
    factor_exposures = pd.DataFrame({
        'Size': np.random.normal(0, 1, n_stocks),
        'Value': np.random.normal(0, 1, n_stocks),
        'Momentum': np.random.normal(0, 1, n_stocks),
        'Volatility': np.random.normal(0, 1, n_stocks)
    }, index=stocks)

    # Portfolio weights (market-cap weighted)
    weights = pd.Series(np.random.dirichlet(np.ones(n_stocks)), index=stocks)

    # Run Barra risk model
    calculator = BarraRiskModelCalculator()
    result = calculator.calculate(
        returns=returns,  # Already stocks x time
        factor_exposures=factor_exposures,
        portfolio_weights=weights
    )

    print("\nPortfolio Risk Decomposition:")
    print("-" * 80)
    print(f"Total Risk:                 {result['value']['total_risk']:.4f} ({result['value']['total_risk']*np.sqrt(12):.2%} annualized)")
    print(f"Factor Risk:                {result['value']['factor_risk']:.4f} ({result['value']['factor_contribution_pct']:.1f}%)")
    print(f"Specific Risk:              {result['value']['specific_risk']:.4f} ({result['value']['specific_contribution_pct']:.1f}%)")

    print("\nPortfolio Factor Exposures:")
    print("-" * 80)
    for factor, exposure in result['value']['portfolio_exposures'].items():
        print(f"{factor:<15}: {exposure:>8.4f}")

    print("\nRisk Interpretation:")
    print("-" * 80)
    factor_pct = result['value']['factor_contribution_pct']
    if factor_pct > 70:
        print(f"✓ Factor risk dominates ({factor_pct:.1f}%) - well-diversified portfolio")
    elif factor_pct > 50:
        print(f"✓ Balanced risk profile ({factor_pct:.1f}% factor, {100-factor_pct:.1f}% specific)")
    else:
        print(f"⚠ High specific risk ({100-factor_pct:.1f}%) - consider more diversification")

    print("\n")


def example_6_factor_exposure_analysis():
    """
    Example 6: Factor Exposure Analysis

    Analyze factor exposures and contributions to returns.
    """
    print("=" * 80)
    print("Example 6: Factor Exposure Analysis")
    print("=" * 80)

    # Generate sample data
    np.random.seed(42)
    n_months = 120
    dates = pd.date_range(start='2015-01-01', periods=n_months, freq='ME')

    portfolio_returns = pd.Series(np.random.normal(0.012, 0.05, n_months), index=dates)

    # Factor returns
    factor_returns = pd.DataFrame({
        'Market': np.random.normal(0.010, 0.04, n_months),
        'Size': np.random.normal(0.002, 0.03, n_months),
        'Value': np.random.normal(0.001, 0.025, n_months),
        'Momentum': np.random.normal(0.003, 0.035, n_months)
    }, index=dates)

    calculator = FactorExposureCalculator()

    # Calculate exposures
    print("\n1. Factor Exposures (Regression Method):")
    print("-" * 80)

    exposure_result = calculator.calculate_exposure(
        asset_returns=portfolio_returns,
        factor_returns=factor_returns,
        method='regression'
    )

    print(f"Alpha: {exposure_result['value']['alpha']:.4f} (t = {exposure_result['value']['alpha_t_stat']:.2f})")
    print(f"R-squared: {exposure_result['value']['r_squared']:.4f}\n")

    for factor, beta in exposure_result['value']['exposures'].items():
        t_stat = exposure_result['value']['t_stats'][factor]
        p_val = exposure_result['value']['p_values'][factor]
        sig = "***" if p_val < 0.01 else "**" if p_val < 0.05 else "*" if p_val < 0.1 else ""
        print(f"{factor:<15}: β = {beta:>7.4f}, t = {t_stat:>7.3f}, p = {p_val:.4f} {sig}")

    # Calculate factor contributions
    print("\n2. Factor Contribution to Returns:")
    print("-" * 80)

    contrib_result = calculator.calculate_factor_contribution(
        portfolio_returns=portfolio_returns,
        factor_returns=factor_returns
    )

    total_return = contrib_result['value']['total_return']

    for factor, contrib in contrib_result['value']['average_contributions'].items():
        pct = contrib_result['value']['percentage_contributions'][factor]
        print(f"{factor:<15}: {contrib:>8.4f}/month ({pct:>6.1f}% of total return)")

    print(f"\nTotal Return:     {total_return:>8.4f}")
    print(f"Specific Return:  {contrib_result['value']['specific_return']:>8.4f}")

    # Calculate factor tilts
    print("\n3. Factor Tilts:")
    print("-" * 80)

    exposures = pd.Series(exposure_result['value']['exposures'])
    tilt_result = calculator.calculate_factor_tilts(exposures)

    for factor, tilt in tilt_result['value']['tilts'].items():
        classification = tilt_result['value']['classifications'][factor]
        print(f"{factor:<15}: {tilt:>7.4f} ({classification})")

    print("\n")


def example_7_active_vs_benchmark():
    """
    Example 7: Active Management Analysis

    Compare portfolio to benchmark using factor analysis.
    """
    print("=" * 80)
    print("Example 7: Active Management vs Benchmark")
    print("=" * 80)

    # Generate sample data
    np.random.seed(42)
    n_months = 120
    dates = pd.date_range(start='2015-01-01', periods=n_months, freq='ME')

    # Active portfolio (trying to beat benchmark)
    portfolio_returns = pd.Series(np.random.normal(0.012, 0.05, n_months), index=dates)

    # Benchmark (market index)
    benchmark_returns = pd.Series(np.random.normal(0.010, 0.04, n_months), index=dates)

    # Factor returns
    factor_returns = pd.DataFrame({
        'Size': np.random.normal(0.002, 0.03, n_months),
        'Value': np.random.normal(0.001, 0.025, n_months),
        'Momentum': np.random.normal(0.003, 0.035, n_months)
    }, index=dates)

    calculator = FactorExposureCalculator()

    # Calculate active exposures
    result = calculator.calculate_active_exposure(
        portfolio_returns=portfolio_returns,
        benchmark_returns=benchmark_returns,
        factor_returns=factor_returns
    )

    print("\nActive Management Analysis:")
    print("-" * 80)
    print(f"Average Active Return:      {result['value']['average_active_return']:.4f}/month")
    print(f"                            ({result['value']['average_active_return']*12:.2%}/year)")
    print(f"Tracking Error:             {result['value']['tracking_error']:.4f}")
    print(f"Information Ratio:          {result['value']['information_ratio']:.4f}")

    print("\nFactor Exposures:")
    print("-" * 80)
    print(f"{'Factor':<15} {'Portfolio':<12} {'Benchmark':<12} {'Active':<12}")
    print("-" * 80)

    for factor in factor_returns.columns:
        port_exp = result['value']['portfolio_exposures'][factor]
        bench_exp = result['value']['benchmark_exposures'][factor]
        active_exp = result['value']['active_exposures'][factor]
        print(f"{factor:<15} {port_exp:>11.4f} {bench_exp:>11.4f} {active_exp:>11.4f}")

    print("\nActive Positioning:")
    print("-" * 80)
    for factor, active_exp in result['value']['active_exposures'].items():
        if abs(active_exp) > 0.2:
            direction = "overweight" if active_exp > 0 else "underweight"
            print(f"✓ {direction.capitalize()} {factor} by {abs(active_exp):.2f}")
        else:
            print(f"  Neutral on {factor}")

    print("\n")


def run_all_examples():
    """Run all examples."""
    examples = [
        example_1_fama_french_3factor,
        example_2_fama_french_5factor,
        example_3_build_factors,
        example_4_carhart_momentum,
        example_5_barra_risk_model,
        example_6_factor_exposure_analysis,
        example_7_active_vs_benchmark
    ]

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"Error in {example.__name__}: {e}")
            import traceback
            traceback.print_exc()
        print("\n")


if __name__ == '__main__':
    run_all_examples()
