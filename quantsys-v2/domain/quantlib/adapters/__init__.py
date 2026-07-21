"""
Adapters package for bridging new and legacy systems.
"""

from domain.quantlib.adapters.factor_calculator_adapter import (
    FactorCalculatorAdapter,
    get_factor_adapter
)
from domain.quantlib.adapters.base_adapter import BaseMarketAdapter
from domain.quantlib.adapters.akshare_adapter import AkShareAdapter
from domain.quantlib.adapters.factory import get_adapter, register_adapter, list_adapters

__all__ = [
    "FactorCalculatorAdapter",
    "get_factor_adapter",
    "BaseMarketAdapter",
    "AkShareAdapter",
    "get_adapter",
    "register_adapter",
    "list_adapters",
]
