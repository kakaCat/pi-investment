"""
Portfolio Optimization Module
==============================

Comprehensive portfolio optimization tools for QuantSys V2.

Modules:
    - markowitz: Markowitz mean-variance optimization
    - black_litterman: Black-Litterman model with subjective views
    - risk_parity: Risk parity optimization (equal risk contribution)
    - efficient_frontier: Efficient frontier calculation and analysis
    - constraints: Constraint management for optimization

Author: QuantSys V2
Date: 2026-05-24
"""

from .markowitz import MarkowitzOptimizer
from .black_litterman import BlackLittermanOptimizer
from .risk_parity import RiskParityOptimizer
from .efficient_frontier import EfficientFrontierCalculator
from .constraints import ConstraintManager

__all__ = [
    'MarkowitzOptimizer',
    'BlackLittermanOptimizer',
    'RiskParityOptimizer',
    'EfficientFrontierCalculator',
    'ConstraintManager',
]

__version__ = '1.0.0'
