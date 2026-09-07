# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

"""Stock data providers."""
from adapters.outbound.datasources.providers.stock.akshare import AkshareStockProvider

__all__ = [
    'AkshareStockProvider',
]
