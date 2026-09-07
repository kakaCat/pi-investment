"""
Broker abstraction layer for QuantSys V2.

This module provides a unified interface for integrating multiple brokers and data sources,
inspired by FinceptTerminal's broker abstraction architecture.

Key components:
- BaseBroker: Abstract base class defining the broker interface
- BrokerRegistry: Singleton registry for broker discovery and instantiation
- Unified types: Common data structures for orders, positions, quotes, etc.
"""

from .base_broker import BaseBroker
from .broker_registry import BrokerRegistry
from .trading_types import (
    OrderSide,
    OrderType,
    ProductType,
    UnifiedOrder,
    BrokerProfile,
    BrokerCredentials,
    ApiResponse,
    BrokerQuote,
    BrokerCandle,
    BrokerPosition,
    BrokerHolding,
)

__all__ = [
    "BaseBroker",
    "BrokerRegistry",
    "OrderSide",
    "OrderType",
    "ProductType",
    "UnifiedOrder",
    "BrokerProfile",
    "BrokerCredentials",
    "ApiResponse",
    "BrokerQuote",
    "BrokerCandle",
    "BrokerPosition",
    "BrokerHolding",
]

__version__ = "1.0.0"
