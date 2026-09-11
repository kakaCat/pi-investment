"""Dividend data providers."""
from adapters.outbound.datasources.providers.dividend.akshare import AkshareDividendProvider
from adapters.outbound.datasources.providers.dividend.eastmoney import EastmoneyDividendProvider

__all__ = [
    'AkshareDividendProvider',
    'EastmoneyDividendProvider',
]
