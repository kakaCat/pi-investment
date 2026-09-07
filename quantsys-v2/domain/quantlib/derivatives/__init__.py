"""
Derivatives Pricing Module
===========================

Comprehensive derivatives pricing and analytics for QuantSys V2.

Modules:
    - black_scholes: Black-Scholes option pricing model
    - greeks: Greeks calculations (Delta, Gamma, Theta, Vega, Rho)
    - implied_volatility: Implied volatility solver
    - binomial_tree: Binomial tree pricing for American options
    - monte_carlo: Monte Carlo simulation for path-dependent options
    - exotic_options: Exotic options (barrier, Asian, lookback, digital)

Usage:
    from domain.quantlib.derivatives import BlackScholesCalculator, GreeksCalculator

    bs = BlackScholesCalculator()
    result = bs.calculate(S=100, K=100, T=1, r=0.05, sigma=0.2, option_type='call')
    print(result['value'])  # Option price
"""

from .black_scholes import BlackScholesCalculator
from .greeks import GreeksCalculator
from .implied_volatility import ImpliedVolatilityCalculator
from .binomial_tree import BinomialTreeCalculator
from .monte_carlo import MonteCarloCalculator
from .exotic_options import ExoticOptionsCalculator
from .advanced_greeks import AdvancedGreeksCalculator
from .volatility_surface import VolatilitySurfaceCalculator
from .stochastic_vol import StochasticVolCalculator
from .option_strategies import OptionStrategiesCalculator, OptionLeg
from .forward_futures import ForwardFuturesCalculator
from .rate_derivatives import RateDerivativesCalculator
from .arbitrage import ArbitrageCalculator

__all__ = [
    'BlackScholesCalculator',
    'GreeksCalculator',
    'ImpliedVolatilityCalculator',
    'BinomialTreeCalculator',
    'MonteCarloCalculator',
    'ExoticOptionsCalculator',
    'AdvancedGreeksCalculator',
    'VolatilitySurfaceCalculator',
    'StochasticVolCalculator',
    'OptionStrategiesCalculator',
    'OptionLeg',
    'ForwardFuturesCalculator',
    'RateDerivativesCalculator',
    'ArbitrageCalculator',
]

__version__ = '1.0.0'
