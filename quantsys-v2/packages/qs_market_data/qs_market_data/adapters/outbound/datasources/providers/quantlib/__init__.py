"""
QuantLib market data adapters (migrated from domain/quantlib/adapters/).

These adapters bridge external data sources to the internal data model.
Location migrated 2026-08-19 as part of architecture audit P0-2 fix.
"""

from .factor_calculator_adapter import FactorCalculatorAdapter, get_factor_adapter
from .base_adapter import BaseMarketAdapter
from .akshare_adapter import AkShareAdapter
from .factory import get_adapter, register_adapter, list_adapters

__all__ = [
    "FactorCalculatorAdapter",
    "get_factor_adapter",
    "BaseMarketAdapter",
    "AkShareAdapter",
    "get_adapter",
    "register_adapter",
    "list_adapters",
]
