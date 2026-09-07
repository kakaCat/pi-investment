# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

"""Market data providers."""
from adapters.outbound.datasources.providers.market.akshare import AkshareMarketProvider

__all__ = [
    'AkshareMarketProvider',
]
