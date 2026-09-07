# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

# domain/trading/ports/__init__.py
from .IOrderRepository import IOrderRepository
from .ITradeRepository import ITradeRepository

__all__ = ['IOrderRepository', 'ITradeRepository']
