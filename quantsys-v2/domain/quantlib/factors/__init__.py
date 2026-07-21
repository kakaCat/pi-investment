"""
Factor Calculation Module
==========================

Unified factor calculation framework based on BaseCalculator.
Includes both technical and fundamental factors.

Technical factors inherit from TechnicalFactorCalculator.
Fundamental factors inherit from BaseCalculator.

Migrated from quant/engine/technical_factors.py to the new framework.
"""

from domain.quantlib.factors.base import TechnicalFactorCalculator
from domain.quantlib.factors.fundamental import FScoreCalculator, EarningsQualityCalculator

__all__ = [
    'TechnicalFactorCalculator',
    'FScoreCalculator',
    'EarningsQualityCalculator',
]
