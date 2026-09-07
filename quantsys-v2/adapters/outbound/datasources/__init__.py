"""Unified data provider infrastructure."""
from adapters.outbound.datasources.manager import (
    DataProviderManager,
    get_data_provider_manager
)
from adapters.outbound.datasources.models import (
    QuoteData,
    FinancialData,
    DividendData,
    MarketData,
    StockData
)
from adapters.outbound.datasources.base import (
    QuoteProvider,
    FinancialProvider,
    DividendProvider,
    MarketProvider,
    StockProvider
)

__all__ = [
    'DataProviderManager',
    'get_data_provider_manager',
    'QuoteData',
    'FinancialData',
    'DividendData',
    'MarketData',
    'StockData',
    'QuoteProvider',
    'FinancialProvider',
    'DividendProvider',
    'MarketProvider',
    'StockProvider',
]
