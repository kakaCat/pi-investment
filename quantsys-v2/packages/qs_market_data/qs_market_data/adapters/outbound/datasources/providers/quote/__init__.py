"""Quote providers for realtime stock data."""
from qs_market_data.adapters.outbound.datasources.providers.quote.sina import SinaQuoteProvider
from qs_market_data.adapters.outbound.datasources.providers.quote.eastmoney import EastmoneyQuoteProvider
from qs_market_data.adapters.outbound.datasources.providers.quote.akshare import AkshareQuoteProvider
from qs_market_data.adapters.outbound.datasources.providers.quote.tencent import TencentQuoteProvider
from qs_market_data.adapters.outbound.datasources.providers.quote.netease import NeteaseQuoteProvider

__all__ = [
    'SinaQuoteProvider',
    'EastmoneyQuoteProvider',
    'AkshareQuoteProvider',
    'TencentQuoteProvider',
    'NeteaseQuoteProvider',
]
