"""Dividend data providers."""
from qs_market_data.adapters.outbound.datasources.providers.dividend.akshare import AkshareDividendProvider
from qs_market_data.adapters.outbound.datasources.providers.dividend.eastmoney import EastmoneyDividendProvider

__all__ = [
    'AkshareDividendProvider',
    'EastmoneyDividendProvider',
]
