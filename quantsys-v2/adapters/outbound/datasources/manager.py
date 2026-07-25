"""Unified data provider manager with automatic failover."""
import logging
from typing import List, Dict, Any, Optional

from adapters.outbound.datasources.providers.quote.sina import SinaQuoteProvider
from adapters.outbound.datasources.providers.quote.eastmoney import EastmoneyQuoteProvider
from adapters.outbound.datasources.providers.quote.akshare import AkshareQuoteProvider
from adapters.outbound.datasources.providers.quote.tencent import TencentQuoteProvider
from adapters.outbound.datasources.providers.quote.netease import NeteaseQuoteProvider
from adapters.outbound.datasources.providers.stock.akshare import AkshareStockProvider
from adapters.outbound.datasources.providers.dividend.akshare import AkshareDividendProvider
from adapters.outbound.datasources.providers.market.akshare import AkshareMarketProvider
from adapters.outbound.datasources.providers.kline.database import DatabaseKlineProvider
from adapters.outbound.datasources.providers.kline.tencent import TencentKlineProvider
from adapters.outbound.datasources.providers.kline.akshare import AkshareKlineProvider
from adapters.outbound.datasources.providers.sector.eastmoney import EastmoneySectorProvider

logger = logging.getLogger(__name__)


class DataProviderManager:
    """Unified data provider manager

    Inspired by RealtimeQuoteService pattern, extended to all domains.
    Coordinates multiple providers per domain with automatic failover,
    health tracking, and source attribution.
    """

    def __init__(self, ds=None):
        # Provider priorities (optimized based on current network conditions)
        # Tencent is fast and reliable, prioritize it first
        # Sina and Eastmoney are currently timing out, moved to end as fallback
        # Akshare is very slow (75s), use as last resort before disabled sources
        self.quote_providers = [
            TencentQuoteProvider(),      # Fast and stable
            SinaQuoteProvider(),         # Currently slow (5s timeout)
            EastmoneyQuoteProvider(),    # Currently unstable (connection issues)
            AkshareQuoteProvider(),      # Very slow (75s) but reliable
            # NeteaseQuoteProvider(),    # Disabled: connection failures
        ]
        self.financial_providers = []
        self.dividend_providers = [
            AkshareDividendProvider(),
        ]
        self.market_providers = [
            AkshareMarketProvider(),
        ]
        self.sector_providers = [
            EastmoneySectorProvider(),
        ]
        self.stock_providers = [
            AkshareStockProvider(),
        ]
        # Kline providers: database first (fast), then tencent (eastmoney 被封后的
        # 主力网络源, 2026-07-23), akshare(eastmoney) 最后兜底
        self.kline_providers = []
        if ds and hasattr(ds, 'kline'):
            self.kline_providers.append(DatabaseKlineProvider(ds.kline))
        self.kline_providers.append(TencentKlineProvider())
        self.kline_providers.append(AkshareKlineProvider())

        # Health tracking (cache provider channel status)
        self.provider_stats: Dict[str, Dict[str, int]] = {}
        self._init_stats()

    def _init_stats(self):
        """Initialize provider statistics"""
        all_providers = (
            self.quote_providers +
            self.financial_providers +
            self.dividend_providers +
            self.market_providers +
            self.sector_providers +
            self.stock_providers +
            self.kline_providers
        )
        for provider in all_providers:
            self.provider_stats[provider.name] = {
                'success': 0,
                'failure': 0,
            }

    def _try_providers(self, providers: List, method_name: str, *args, **kwargs) -> dict:
        """Generic failover logic (inspired by RealtimeQuoteService)

        Args:
            providers: List of provider instances
            method_name: Method name to call on each provider
            *args, **kwargs: Arguments to pass to the method

        Returns:
            dict with keys:
                - success: bool
                - data: result data if success, None otherwise
                - source: provider name if success
                - error: error message if all providers failed
                - attempted_sources: list of attempted provider names if failed
        """
        for provider in providers:
            try:
                method = getattr(provider, method_name)
                result = method(*args, **kwargs)

                if result and self._is_valid(result):
                    self._record_success(provider.name)
                    return {
                        'success': True,
                        'data': result,
                        'source': provider.name
                    }

                self._record_failure(provider.name)

            except Exception as e:
                logger.warning(f"Provider {provider.name}.{method_name} failed: {e}")
                self._record_failure(provider.name)

        # All providers failed
        return {
            'success': False,
            'error': 'All data providers failed',
            'attempted_sources': [p.name for p in providers]
        }

    def _is_valid(self, data) -> bool:
        """Validate data completeness

        Args:
            data: Data object (QuoteData, FinancialData, etc.) or list of such objects

        Returns:
            True if data is valid, False otherwise
        """
        if hasattr(data, 'source') and hasattr(data, 'timestamp'):
            return bool(data.source and data.timestamp)
        if isinstance(data, list) and len(data) > 0:
            # For list results (e.g., dividend history), check first item
            return hasattr(data[0], 'source') and bool(data[0].source)
        return False

    def _record_success(self, provider_name: str):
        """Record successful provider call (cache channel health)"""
        if provider_name in self.provider_stats:
            self.provider_stats[provider_name]['success'] += 1

    def _record_failure(self, provider_name: str):
        """Record failed provider call (cache channel health)"""
        if provider_name in self.provider_stats:
            self.provider_stats[provider_name]['failure'] += 1

    def get_provider_health(self) -> Dict[str, Dict[str, int]]:
        """Get provider health status

        Returns:
            Dict mapping provider name to stats dict with 'success' and 'failure' counts
        """
        return self.provider_stats

    # API methods (minimal set for Phase 1, expanded in Phase 2-3)

    def get_quote(self, symbol: str) -> dict:
        """Get realtime quote

        Args:
            symbol: Stock symbol

        Returns:
            Result dict with success, data, source fields
        """
        return self._try_providers(self.quote_providers, 'get_quote', symbol)

    def get_announcements(self, symbol: str) -> dict:
        """Get stock announcements

        Args:
            symbol: Stock symbol

        Returns:
            Result dict with success, data, source fields
        """
        return self._try_providers(self.stock_providers, 'get_announcements', symbol)

    def get_news(self, symbol: str, num: int = 10) -> dict:
        """Get stock news

        Args:
            symbol: Stock symbol
            num: Number of news items

        Returns:
            Result dict with success, data, source fields
        """
        return self._try_providers(self.stock_providers, 'get_news', symbol, num=num)

    def get_trading_calendar(self, start_date: str, end_date: str) -> dict:
        """Get trading calendar

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Result dict with success, data, source fields
        """
        return self._try_providers(
            self.stock_providers,
            'get_trading_calendar',
            start_date,
            end_date
        )

    def get_dividends(self, symbol: str, years: int = 5) -> dict:
        """Get dividend history

        Args:
            symbol: Stock symbol
            years: Number of years

        Returns:
            Result dict with success, data, source fields
        """
        return self._try_providers(self.dividend_providers, 'get_dividends', symbol, years=years)

    def get_dividend_calendar(self, start_date: str, end_date: str) -> dict:
        """Get dividend calendar

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Result dict with success, data, source fields
        """
        return self._try_providers(
            self.dividend_providers,
            'get_dividend_calendar',
            start_date,
            end_date
        )

    def screen_high_dividend(self, min_yield: float = 3.0, min_years: int = 5) -> dict:
        """Screen high dividend stocks

        Args:
            min_yield: Minimum dividend yield (%)
            min_years: Minimum consecutive dividend years

        Returns:
            Result dict with success, data, source fields
        """
        return self._try_providers(
            self.dividend_providers,
            'screen_high_dividend',
            min_yield=min_yield,
            min_years=min_years
        )

    def get_financial(self, symbol: str, report_type: str = 'latest') -> dict:
        """Get financial data

        Args:
            symbol: Stock symbol
            report_type: 'latest' | 'quarterly' | 'annual'

        Returns:
            Result dict with success, data, source fields
        """
        return self._try_providers(
            self.financial_providers,
            'get_financial',
            symbol,
            report_type=report_type
        )

    def get_market_overview(self) -> dict:
        """Get market overview

        Returns:
            Result dict with success, data, source fields
        """
        return self._try_providers(self.market_providers, 'get_market_overview')

    def get_lhb_stock(self, symbol: str, date: str) -> dict:
        """Get dragon-tiger list for a stock

        Args:
            symbol: Stock symbol
            date: Date (YYYY-MM-DD)

        Returns:
            Result dict with success, data, source fields
        """
        return self._try_providers(self.market_providers, 'get_lhb_stock', symbol, date)

    def get_lhb_daily(self, date: str) -> dict:
        """Get daily dragon-tiger list

        Args:
            date: Date (YYYY-MM-DD)

        Returns:
            Result dict with success, data, source fields
        """
        return self._try_providers(self.market_providers, 'get_lhb_daily', date)

    def get_sector_stocks(self, sector: str) -> dict:
        """Get sector constituent stocks (行业/概念板块成分股)

        Args:
            sector: Sector name (e.g., '白酒', '电力')

        Returns:
            Result dict with success, data (MarketData.data: found/sector_code/stocks),
            source fields. data['found']=False 表示板块不存在（有效响应，非网络错误）。
        """
        return self._try_providers(self.sector_providers, 'get_sector_stocks', sector)

    def get_klines(self, symbol: str, period: str, start_date: str, end_date: str) -> dict:
        """Get kline data with automatic failover

        Args:
            symbol: Stock symbol
            period: Period (daily, weekly, monthly, 1m, 5m, 15m, 30m, 60m)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Result dict with success, data (list of KlineData), source fields
        """
        return self._try_providers(
            self.kline_providers,
            'get_klines',
            symbol,
            period,
            start_date,
            end_date
        )


# Singleton instance
_manager_instance = None


def get_data_provider_manager() -> DataProviderManager:
    """Get singleton DataProviderManager instance

    Returns:
        The singleton DataProviderManager instance
    """
    global _manager_instance
    if _manager_instance is None:
        # Import ds here to avoid circular import
        from adapters.inbound.api.shared import ds
        _manager_instance = DataProviderManager(ds=ds)
    return _manager_instance


# Alias for backward compatibility
get_data_source_manager = get_data_provider_manager
