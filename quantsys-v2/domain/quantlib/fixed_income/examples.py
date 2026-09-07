"""
Fixed Income Analysis Examples
==============================

Practical examples demonstrating the use of fixed income analysis module.

Author: QuantSys V2
Date: 2026-05-24
"""

from domain.quantlib.fixed_income import (
    BondPricingCalculator,
    DurationConvexityCalculator,
    YieldCurveCalculator,
    CreditAnalysisCalculator,
    BondPortfolioCalculator
)


def example_bond_pricing():
    """Example: Bond pricing calculations."""
    print("=" * 60)
    print("Bond Pricing Examples")
    print("=" * 60)

    calc = BondPricingCalculator()

    # Example 1: Zero coupon bond
    print("\n1. Zero Coupon Bond Pricing")
    result = calc.calculate_price(
        face_value=1000,
        coupon_rate=0,
        ytm=0.05,
        years_to_maturity=10,
        frequency=0,
        bond_type='zero'
    )
    print(f"   Price: ${result['value']:.2f}")
    print(f"   Discount: ${1000 - result['value']:.2f}")

    # Example 2: Coupon bond at par
    print("\n2. Coupon Bond at Par")
    result = calc.calculate_price(
        face_value=1000,
        coupon_rate=0.05,
        ytm=0.05,
        years_to_maturity=10,
        frequency=2
    )
    print(f"   Price: ${result['value']:.2f}")
    print(f"   Current Yield: {result['metadata']['current_yield']*100:.2f}%")

    # Example 3: YTM calculation
    print("\n3. Yield to Maturity Calculation")
    result = calc.calculate_ytm(
        price=950,
        face_value=1000,
        coupon_rate=0.05,
        years_to_maturity=10,
        frequency=2
    )
    print(f"   YTM: {result['value']*100:.2f}%")
    print(f"   Current Yield: {result['metadata']['current_yield']*100:.2f}%")
    print(f"   Bond Equivalent Yield: {result['metadata']['bond_equivalent_yield']*100:.2f}%")


def example_duration_convexity():
    """Example: Duration and convexity calculations."""
    print("\n" + "=" * 60)
    print("Duration and Convexity Examples")
    print("=" * 60)

    calc = DurationConvexityCalculator()

    # Example 1: Macaulay duration
    print("\n1. Macaulay Duration")
    result = calc.calculate_macaulay_duration(
        face_value=1000,
        coupon_rate=0.05,
        years_to_maturity=10,
        ytm=0.05,
        frequency=2
    )
    print(f"   Macaulay Duration: {result['value']:.2f} years")
    print(f"   Bond Price: ${result['metadata']['price']:.2f}")

    # Example 2: Modified duration
    print("\n2. Modified Duration")
    result = calc.calculate_modified_duration(
        face_value=1000,
        coupon_rate=0.05,
        years_to_maturity=10,
        ytm=0.05,
        frequency=2
    )
    print(f"   Modified Duration: {result['value']:.2f}")
    print(f"   DV01: ${result['metadata']['dv01']:.2f}")
    print(f"   Price change for 1% yield increase: ${result['metadata']['price_change_1pct_yield']:.2f}")

    # Example 3: Convexity
    print("\n3. Convexity")
    result = calc.calculate_convexity(
        face_value=1000,
        coupon_rate=0.05,
        years_to_maturity=10,
        ytm=0.05,
        frequency=2
    )
    print(f"   Convexity: {result['value']:.2f}")
    print(f"   Convexity adjustment (1% yield change): ${result['metadata']['convexity_adjustment_1pct']:.2f}")


def example_yield_curve():
    """Example: Yield curve construction and analysis."""
    print("\n" + "=" * 60)
    print("Yield Curve Examples")
    print("=" * 60)

    calc = YieldCurveCalculator()

    # Example 1: Bootstrap spot curve
    print("\n1. Bootstrap Spot Curve")
    bonds = [
        {'price': 980, 'coupon_rate': 0.04, 'maturity': 1, 'face_value': 1000},
        {'price': 970, 'coupon_rate': 0.045, 'maturity': 2, 'face_value': 1000},
        {'price': 960, 'coupon_rate': 0.05, 'maturity': 3, 'face_value': 1000},
        {'price': 950, 'coupon_rate': 0.052, 'maturity': 5, 'face_value': 1000},
    ]
    result = calc.bootstrap_spot_curve(bonds, frequency=1)
    print("   Spot Rates:")
    for point in result['metadata']['spot_curve']:
        print(f"   {point['maturity']}Y: {point['spot_rate_pct']:.2f}%")

    # Example 2: Forward rates
    print("\n2. Forward Rate Curve")
    spot_rates = [(p['maturity'], p['spot_rate']) for p in result['metadata']['spot_curve']]
    result = calc.calculate_forward_curve(spot_rates)
    print("   Forward Rates:")
    for fr in result['metadata']['forward_curve'][:3]:
        print(f"   {fr['period']}: {fr['forward_rate_pct']:.2f}%")

    # Example 3: Nelson-Siegel fitting
    print("\n3. Nelson-Siegel Model Fitting")
    maturities = [0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30]
    yields = [0.02, 0.025, 0.03, 0.035, 0.038, 0.04, 0.042, 0.043, 0.044, 0.045]
    result = calc.fit_nelson_siegel(maturities, yields)
    print(f"   Beta0 (long-term): {result['value']['beta0']:.4f}")
    print(f"   Beta1 (slope): {result['value']['beta1']:.4f}")
    print(f"   Beta2 (curvature): {result['value']['beta2']:.4f}")
    print(f"   Tau: {result['value']['tau']:.4f}")
    print(f"   R-squared: {result['metadata']['fit_statistics']['r_squared']:.4f}")


def example_credit_analysis():
    """Example: Credit analysis calculations."""
    print("\n" + "=" * 60)
    print("Credit Analysis Examples")
    print("=" * 60)

    calc = CreditAnalysisCalculator()

    # Example 1: Expected loss
    print("\n1. Expected Loss Calculation")
    result = calc.calculate_expected_loss(
        probability_of_default=0.02,
        exposure=1000000,
        recovery_rate=0.40
    )
    print(f"   Expected Loss: ${result['value']:,.2f}")
    print(f"   Unexpected Loss: ${result['metadata']['unexpected_loss']:,.2f}")
    print(f"   Loss Given Default: {result['metadata']['lgd']*100:.1f}%")

    # Example 2: Cumulative default probability
    print("\n2. Cumulative Default Probability")
    result = calc.calculate_cumulative_pd(
        annual_pd=0.02,
        years=5,
        method='hazard'
    )
    print("   Cumulative PD by year:")
    for cpd in result['metadata']['cumulative_pds']:
        print(f"   Year {cpd['year']}: {cpd['cumulative_pd_pct']:.2f}%")

    # Example 3: PD from credit spread
    print("\n3. Implied PD from Credit Spread")
    result = calc.pd_from_credit_spread(
        credit_spread=0.02,
        recovery_rate=0.40,
        risk_free_rate=0.03
    )
    print(f"   Credit Spread: {result['metadata']['credit_spread_bps']:.0f} bps")
    print(f"   Implied PD: {result['value']*100:.2f}%")

    # Example 4: Merton model
    print("\n4. Merton Structural Model")
    result = calc.pd_from_merton_model(
        asset_value=100_000_000,
        asset_volatility=0.25,
        debt_face_value=80_000_000,
        risk_free_rate=0.03,
        time_horizon=1.0
    )
    print(f"   Default Probability: {result['value']*100:.2f}%")
    print(f"   Distance to Default: {result['metadata']['distance_to_default']:.2f}σ")
    print(f"   Leverage Ratio: {result['metadata']['leverage_ratio']:.2f}")

    # Example 5: Historical default rates
    print("\n5. Historical Default Rates by Rating")
    for rating in ['AAA', 'A', 'BBB', 'BB', 'B']:
        result = calc.get_historical_pd(rating=rating, years=1)
        print(f"   {rating}: {result['metadata']['annual_pd_pct']:.2f}%")


def example_bond_portfolio():
    """Example: Bond portfolio management."""
    print("\n" + "=" * 60)
    print("Bond Portfolio Examples")
    print("=" * 60)

    calc = BondPortfolioCalculator()

    # Example 1: Portfolio duration
    print("\n1. Portfolio Duration and Convexity")
    bonds = [
        {'weight': 0.3, 'duration': 4, 'convexity': 25, 'price': 980, 'ytm': 0.04},
        {'weight': 0.5, 'duration': 7, 'convexity': 55, 'price': 1000, 'ytm': 0.045},
        {'weight': 0.2, 'duration': 10, 'convexity': 90, 'price': 1020, 'ytm': 0.05},
    ]
    result = calc.calculate_portfolio_duration(bonds)
    print(f"   Portfolio Duration: {result['value']:.2f} years")
    print(f"   Portfolio Convexity: {result['metadata']['portfolio_convexity']:.2f}")
    print(f"   Portfolio YTM: {result['metadata']['portfolio_ytm']*100:.2f}%")
    print(f"   DV01: ${result['metadata']['dv01']:.2f}")

    # Example 2: Immunization strategy
    print("\n2. Immunization Strategy")
    available_bonds = [
        {'duration': 3, 'convexity': 15, 'price': 980, 'ytm': 0.04},
        {'duration': 10, 'convexity': 80, 'price': 1020, 'ytm': 0.045},
    ]
    result = calc.calculate_immunization(
        liability_amount=10_000_000,
        liability_duration=6,
        available_bonds=available_bonds,
        strategy='duration_match'
    )
    print(f"   Short Bond Weight: {result['metadata']['short_bond']['weight']*100:.1f}%")
    print(f"   Long Bond Weight: {result['metadata']['long_bond']['weight']*100:.1f}%")
    print(f"   Portfolio Duration: {result['metadata']['portfolio_duration']:.2f} years")

    # Example 3: Risk contribution
    print("\n3. Risk Contribution Analysis")
    result = calc.calculate_risk_contribution(bonds)
    print("   Risk Contributions:")
    for i, rc in enumerate(result['value']):
        print(f"   Bond {i+1}: {rc['risk_contribution_pct']:.1f}% (Duration: {rc['duration']:.1f})")


def run_all_examples():
    """Run all examples."""
    example_bond_pricing()
    example_duration_convexity()
    example_yield_curve()
    example_credit_analysis()
    example_bond_portfolio()
    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)


if __name__ == '__main__':
    run_all_examples()
