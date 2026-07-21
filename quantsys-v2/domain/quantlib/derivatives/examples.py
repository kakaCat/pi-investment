"""
Derivatives Pricing Module - Usage Examples
============================================

Comprehensive examples demonstrating all features of the derivatives pricing module.

Author: QuantSys V2
Date: 2026-05-24
"""

from domain.quantlib.derivatives import (
    BlackScholesCalculator,
    GreeksCalculator,
    ImpliedVolatilityCalculator,
    BinomialTreeCalculator,
    MonteCarloCalculator
)


def example_black_scholes():
    """Example: Black-Scholes option pricing."""
    print("=" * 60)
    print("Black-Scholes Option Pricing")
    print("=" * 60)

    calc = BlackScholesCalculator()

    # Price a call option
    result = calc.calculate(
        S=100,          # Spot price
        K=100,          # Strike price
        T=1.0,          # 1 year to maturity
        r=0.05,         # 5% risk-free rate
        sigma=0.2,      # 20% volatility
        option_type='call'
    )

    print(f"\nCall Option Price: ${result['value']:.4f}")
    print(f"Intrinsic Value: ${result['metadata']['intrinsic_value']:.4f}")
    print(f"Time Value: ${result['metadata']['time_value']:.4f}")
    print(f"d1: {result['metadata']['d1']:.4f}")
    print(f"d2: {result['metadata']['d2']:.4f}")

    # Price a put option
    put_result = calc.calculate_put(S=100, K=100, T=1.0, r=0.05, sigma=0.2)
    print(f"\nPut Option Price: ${put_result['value']:.4f}")

    # Verify put-call parity
    parity = calc.put_call_parity(
        call_price=result['value'],
        put_price=put_result['value'],
        S=100, K=100, T=1.0, r=0.05
    )
    print(f"\nPut-Call Parity Holds: {parity['parity_holds']}")
    print(f"Difference: ${parity['difference']:.6f}")


def example_greeks():
    """Example: Greeks calculations."""
    print("\n" + "=" * 60)
    print("Greeks Calculations")
    print("=" * 60)

    calc = GreeksCalculator()

    # Calculate all Greeks
    result = calc.calculate(
        S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type='call'
    )

    greeks = result['value']
    print(f"\nFirst-Order Greeks:")
    print(f"  Delta: {greeks['delta']:.4f} (price sensitivity)")
    print(f"  Gamma: {greeks['gamma']:.4f} (delta sensitivity)")
    print(f"  Theta: {greeks['theta']:.4f} (time decay per day)")
    print(f"  Vega:  {greeks['vega']:.4f} (volatility sensitivity)")
    print(f"  Rho:   {greeks['rho']:.4f} (rate sensitivity)")

    print(f"\nSecond-Order Greeks:")
    print(f"  Vanna: {greeks['vanna']:.4f}")
    print(f"  Volga: {greeks['volga']:.4f}")
    print(f"  Charm: {greeks['charm']:.4f}")

    # Delta hedging
    hedge = calc.delta_hedge_ratio(
        S=100, K=100, T=1.0, r=0.05, sigma=0.2,
        option_type='call', option_position=10  # Long 10 calls
    )
    print(f"\nDelta Hedge (10 long calls):")
    print(f"  {hedge['interpretation']}")
    print(f"  Shares to hedge: {hedge['shares_to_hedge']:.4f}")


def example_implied_volatility():
    """Example: Implied volatility calculation."""
    print("\n" + "=" * 60)
    print("Implied Volatility Calculation")
    print("=" * 60)

    bs_calc = BlackScholesCalculator()
    iv_calc = ImpliedVolatilityCalculator()

    # Market option price
    market_price = 10.45

    # Calculate implied volatility
    result = iv_calc.calculate(
        option_price=market_price,
        S=100, K=100, T=1.0, r=0.05,
        option_type='call',
        method='brent'
    )

    print(f"\nMarket Option Price: ${market_price:.2f}")
    print(f"Implied Volatility: {result['value']:.4f} ({result['value']*100:.2f}%)")
    print(f"Converged: {result['metadata']['converged']}")
    print(f"Iterations: {result['metadata']['iterations']}")
    print(f"Final Error: ${result['metadata']['final_error']:.6f}")

    # Verify by pricing with implied vol
    verify = bs_calc.calculate(S=100, K=100, T=1.0, r=0.05, sigma=result['value'], option_type='call')
    print(f"\nVerification - Calculated Price: ${verify['value']:.4f}")


def example_binomial_tree():
    """Example: Binomial tree pricing."""
    print("\n" + "=" * 60)
    print("Binomial Tree Option Pricing")
    print("=" * 60)

    calc = BinomialTreeCalculator()

    # Price American put option
    american_result = calc.calculate_american(
        S=100, K=100, T=1.0, r=0.05, sigma=0.2,
        option_type='put', steps=100
    )

    print(f"\nAmerican Put Option:")
    print(f"  Price: ${american_result['value']:.4f}")
    print(f"  Delta: {american_result['metadata']['delta']:.4f}")
    print(f"  Gamma: {american_result['metadata']['gamma']:.4f}")

    # Compare with European put
    european_result = calc.calculate_european(
        S=100, K=100, T=1.0, r=0.05, sigma=0.2,
        option_type='put', steps=100
    )

    print(f"\nEuropean Put Option:")
    print(f"  Price: ${european_result['value']:.4f}")

    # Early exercise premium
    premium = calc.early_exercise_premium(
        S=100, K=100, T=1.0, r=0.05, sigma=0.2,
        option_type='put', steps=100
    )

    print(f"\nEarly Exercise Premium:")
    print(f"  Premium: ${premium['early_exercise_premium']:.4f}")
    print(f"  Premium %: {premium['premium_percentage']:.2f}%")
    print(f"  Early Exercise Optimal: {premium['early_exercise_optimal']}")

    # Tree parameters
    params = american_result['metadata']['tree_parameters']
    print(f"\nTree Parameters:")
    print(f"  Up factor (u): {params['u']:.4f}")
    print(f"  Down factor (d): {params['d']:.4f}")
    print(f"  Risk-neutral prob (p): {params['p']:.4f}")
    print(f"  Time step (dt): {params['dt']:.4f}")


def example_monte_carlo():
    """Example: Monte Carlo simulation."""
    print("\n" + "=" * 60)
    print("Monte Carlo Option Pricing")
    print("=" * 60)

    calc = MonteCarloCalculator(seed=42)

    # European call option
    result = calc.calculate(
        S=100, K=100, T=1.0, r=0.05, sigma=0.2,
        option_type='call', simulations=50000
    )

    print(f"\nEuropean Call Option (50,000 simulations):")
    print(f"  Price: ${result['value']:.4f}")
    print(f"  Std Error: ${result['metadata']['std_error']:.4f}")
    ci = result['metadata']['confidence_interval_95']
    print(f"  95% CI: [${ci[0]:.4f}, ${ci[1]:.4f}]")

    # Asian option
    asian_result = calc.calculate_asian(
        S=100, K=100, T=1.0, r=0.05, sigma=0.2,
        option_type='call', simulations=10000,
        averaging_type='arithmetic'
    )

    print(f"\nAsian Call Option (arithmetic average):")
    print(f"  Price: ${asian_result['value']:.4f}")
    print(f"  Std Error: ${asian_result['metadata']['std_error']:.4f}")

    # Barrier option
    barrier_result = calc.calculate_barrier(
        S=100, K=100, T=1.0, r=0.05, sigma=0.2,
        barrier=90, barrier_type='down-and-out',
        option_type='call', simulations=10000
    )

    print(f"\nDown-and-Out Barrier Call (barrier=90):")
    print(f"  Price: ${barrier_result['value']:.4f}")
    print(f"  Barrier Crossed: {barrier_result['metadata']['barrier_crossed_pct']:.2f}%")
    print(f"  Active Paths: {barrier_result['metadata']['active_paths_pct']:.2f}%")

    # Lookback option
    lookback_result = calc.calculate_lookback(
        S=100, K=100, T=1.0, r=0.05, sigma=0.2,
        lookback_type='floating', option_type='call',
        simulations=10000
    )

    print(f"\nFloating Strike Lookback Call:")
    print(f"  Price: ${lookback_result['value']:.4f}")
    print(f"  Mean Max Price: ${lookback_result['metadata']['mean_max_price']:.2f}")
    print(f"  Mean Min Price: ${lookback_result['metadata']['mean_min_price']:.2f}")


def example_comparison():
    """Example: Compare different pricing methods."""
    print("\n" + "=" * 60)
    print("Comparison of Pricing Methods")
    print("=" * 60)

    # Common parameters
    S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.2

    # Black-Scholes
    bs_calc = BlackScholesCalculator()
    bs_result = bs_calc.calculate(S, K, T, r, sigma, 'call')

    # Binomial Tree
    tree_calc = BinomialTreeCalculator()
    tree_result = tree_calc.calculate_european(S, K, T, r, sigma, 'call', steps=200)

    # Monte Carlo
    mc_calc = MonteCarloCalculator(seed=42)
    mc_result = mc_calc.calculate(S, K, T, r, sigma, 'call', simulations=50000)

    print(f"\nEuropean Call Option (S=100, K=100, T=1, r=5%, σ=20%):")
    print(f"  Black-Scholes:  ${bs_result['value']:.4f}")
    print(f"  Binomial Tree:  ${tree_result['value']:.4f} (200 steps)")
    print(f"  Monte Carlo:    ${mc_result['value']:.4f} ± ${mc_result['metadata']['std_error']:.4f} (50k sims)")

    print(f"\nDifferences from Black-Scholes:")
    print(f"  Binomial Tree:  ${abs(tree_result['value'] - bs_result['value']):.4f}")
    print(f"  Monte Carlo:    ${abs(mc_result['value'] - bs_result['value']):.4f}")


if __name__ == '__main__':
    example_black_scholes()
    example_greeks()
    example_implied_volatility()
    example_binomial_tree()
    example_monte_carlo()
    example_comparison()

    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)
