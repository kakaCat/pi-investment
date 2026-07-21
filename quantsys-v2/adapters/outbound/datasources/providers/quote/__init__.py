"""Quote providers for realtime stock data."""
from adapters.outbound.datasources.providers.quote.sina import SinaQuoteProvider
from adapters.outbound.datasources.providers.quote.eastmoney import EastmoneyQuoteProvider
from adapters.outbound.datasources.providers.quote.akshare import AkshareQuoteProvider
from adapters.outbound.datasources.providers.quote.tencent import TencentQuoteProvider
from adapters.outbound.datasources.providers.quote.netease import NeteaseQuoteProvider

__all__ = [
    'SinaQuoteProvider',
    'EastmoneyQuoteProvider',
    'AkshareQuoteProvider',
    'TencentQuoteProvider',
    'NeteaseQuoteProvider',
]
