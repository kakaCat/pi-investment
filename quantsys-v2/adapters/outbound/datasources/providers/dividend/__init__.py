# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

"""Dividend data providers."""
from adapters.outbound.datasources.providers.dividend.akshare import AkshareDividendProvider

__all__ = [
    'AkshareDividendProvider',
]
