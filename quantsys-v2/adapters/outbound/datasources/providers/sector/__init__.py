# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

"""Sector data providers."""
from adapters.outbound.datasources.providers.sector.eastmoney import EastmoneySectorProvider

__all__ = [
    'EastmoneySectorProvider',
]
