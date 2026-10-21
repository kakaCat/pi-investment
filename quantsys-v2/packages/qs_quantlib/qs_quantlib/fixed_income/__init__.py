"""
Fixed Income Analysis Module
=============================

Comprehensive fixed income analytics for bond pricing, duration/convexity,
yield curve analysis, credit analysis, and portfolio management.

Migrated from FinceptTerminal with core algorithms adapted to QuantSys V2 architecture.

Author: QuantSys V2
Date: 2026-05-24
"""

from .bond_pricing import BondPricingCalculator
from .duration_convexity import DurationConvexityCalculator
from .yield_curve import YieldCurveCalculator
from .credit_analysis import CreditAnalysisCalculator
from .bond_portfolio import BondPortfolioCalculator

__all__ = [
    'BondPricingCalculator',
    'DurationConvexityCalculator',
    'YieldCurveCalculator',
    'CreditAnalysisCalculator',
    'BondPortfolioCalculator',
]

__version__ = '1.0.0'
