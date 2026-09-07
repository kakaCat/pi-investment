"""
Quantitative Rate Calculations Module
======================================

Interest rate and yield calculations for fixed income analysis.

Provides basic rate conversion and calculation utilities.

Author: Migrated from FinceptTerminal
Date: 2026-05-24
"""

import numpy as np
from typing import Union


def simple_to_compound(simple_rate: float, periods: int = 1) -> float:
    """
    Convert simple interest rate to compound rate.

    Args:
        simple_rate: Simple interest rate (e.g., 0.05 for 5%)
        periods: Number of compounding periods per year

    Returns:
        Compound interest rate
    """
    return (1 + simple_rate / periods) ** periods - 1


def compound_to_simple(compound_rate: float, periods: int = 1) -> float:
    """
    Convert compound interest rate to simple rate.

    Args:
        compound_rate: Compound interest rate
        periods: Number of compounding periods per year

    Returns:
        Simple interest rate
    """
    return periods * ((1 + compound_rate) ** (1 / periods) - 1)
