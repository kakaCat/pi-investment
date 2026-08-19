"""Unified data provider manager with automatic failover."""
import logging
from typing import List, Dict, Any, Optional

from domain.exceptions import ExternalServiceError

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
from adapters.outbound.datasources.providers.kline.baostock import BaostockKlineProvider
from adapters.outbound.datasources.providers.kline.akshare import AkshareKlineProvider
from adapters.outbound.datasources.providers.sector.eastmoney import EastmoneySectorProvider
from adapters.outbound.datasources.providers.index.akshare import AkshareIndexProvider
from adapters.outbound.datasources.providers.hk.akshare import AkshareHKProvider
from adapters.outbound.datasources.providers.financial.akshare import AkshareFinancialStatementProvider

logger = logging.getLogger(__name__)


class DataProviderManager:
    """Unified data provider manager

    Inspired by RealtimeQuoteService pattern, extended to all domains.
    Coordinates multiple providers per domain with automatic failover,
    health tracking, and source attribution.
    """

    def __init__(self, ds=None):
        # 单 provider 调用超时（秒）
        self.provider_timeout_seconds = 60
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
        self.index_providers = [
            AkshareIndexProvider(),
        ]
        self.hk_providers = [
            AkshareHKProvider(),
        ]
        # financial_providers 保留空列表（get_financial 已由 market provider 提供）
        # 这里的 AkshareFinancialStatementProvider 提供更细粒度的报表（利润表、现金流量表等）
        self.financial_detail_providers = [
            AkshareFinancialStatementProvider(),
        ]
        # Kline providers: database first (fast), baostock 为网络首选（独立 TCP
        # 体系，eastmoney/tencent 双双被封后的主力源, 2026-07-28），tencent 其次，
        # akshare(eastmoney) 最后兜底
        self.kline_providers = []
        if ds and hasattr(ds, 'kline'):
            self.kline_providers.append(DatabaseKlineProvider(ds.kline))
        self.kline_providers.append(BaostockKlineProvider())
        self.kline_providers.append(TencentKlineProvider())
        self.kline_providers.append(AkshareKlineProvider())

        # Health tracking (cache provider channel status)
        self.provider_stats: Dict[str, Dict[str, int]] = {}
        # Dynamic priority: providers with high failure rate get temporarily deprioritized
        self._failure_threshold = 3  # 连续失败阈值，超过则降级
        self._recovery_window = 5    # 成功次数达到此值则恢复优先级
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
            self.kline_providers +
            self.index_providers +
            self.hk_providers +
            self.financial_detail_providers
        )
        for provider in all_providers:
            self.provider_stats[provider.name] = {
                'success': 0,
                'failure': 0,
                'consecutive_failures': 0,
            }

    def _try_providers(self, providers: List, method_name: str, *args, **kwargs) -> dict:
        """Generic failover logic with dynamic priority (inspired by RealtimeQuoteService)

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
                - provider_errors: {provider_name: 具体失败原因} if failed，
                  供调用方（API 路由）返回可行动的错误提示
        """
        # Sort providers by health score before trying
        sorted_providers = self._sort_providers_by_health(providers)

        provider_errors: Dict[str, str] = {}
        for provider in sorted_providers:
            try:
                method = getattr(provider, method_name)
                # 单 provider 调用超时护栏（2026-08-05 评分挂死事故）：
                # provider 内部网络调用可能无超时（如 akshare 封装 requests），
                # 黑洞时永久阻塞会把调用方线程池拖死。超时即判失败降级下一个。
                # 挂死线程不等待回收（shutdown(wait=False)），由 OS 善后。
                import concurrent.futures
                guard = concurrent.futures.ThreadPoolExecutor(max_workers=1)

                def _guarded_call():
                    try:
                        return method(*args, **kwargs)
                    finally:
                        # 护栏线程里若建了 ORM scoped session（DatabaseKlineProvider
                        # 等查库 provider），线程 shutdown(wait=False) 后 session
                        # 无人回收，连接呈 idle in transaction 靠 GC 轮盘释放
                        # （WatchEngine 盯盘每轮每符号一次 get_klines，2026-08-18
                        # 实测稳态 7 条泄漏）。在同一护栏线程 finally 释放。
                        try:
                            from infrastructure.persistence.orm import close_session
                            close_session()
                        except Exception:
                            pass

                try:
                    fut = guard.submit(_guarded_call)
                    result = fut.result(timeout=self.provider_timeout_seconds)
                except concurrent.futures.TimeoutError:
                    logger.warning(f"Provider {provider.name}.{method_name} 超时（>{self.provider_timeout_seconds}s），降级下一个")
                    provider_errors[provider.name] = f'调用超时（>{self.provider_timeout_seconds}s）'
                    self._record_failure(provider.name)
                    continue
                finally:
                    guard.shutdown(wait=False)

                if result and self._is_valid(result):
                    self._record_success(provider.name)
                    return {
                        'success': True,
                        'data': result,
                        'source': provider.name
                    }

                # provider 可通过 self.last_error 暴露具体失败原因
                reason = getattr(provider, 'last_error', None) or '返回空数据或数据校验未通过'
                provider_errors[provider.name] = reason
                self._record_failure(provider.name)

            except Exception as e:
                logger.warning(f"Provider {provider.name}.{method_name} failed: {e}")
                provider_errors[provider.name] = f"{type(e).__name__}: {e}"
                self._record_failure(provider.name)

        # All providers failed
        return {
            'success': False,
            'error': 'All data providers failed',
            'attempted_sources': [p.name for p in providers],
            'provider_errors': provider_errors,
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
            # Reset consecutive failures on success
            self.provider_stats[provider_name]['consecutive_failures'] = 0

    def _record_failure(self, provider_name: str):
        """Record failed provider call (cache channel health)"""
        if provider_name in self.provider_stats:
            self.provider_stats[provider_name]['failure'] += 1
            self.provider_stats[provider_name]['consecutive_failures'] = (
                self.provider_stats[provider_name].get('consecutive_failures', 0) + 1
            )

    def _sort_providers_by_health(self, providers: List) -> List:
        """Sort providers by health score (success rate + consecutive failures)

        Providers with high consecutive failures are deprioritized.
        Providers with recent successes are prioritized.

        Args:
            providers: List of provider instances

        Returns:
            Sorted list of providers (healthiest first)
        """
        def health_score(provider):
            stats = self.provider_stats.get(provider.name, {})
            consecutive_failures = stats.get('consecutive_failures', 0)
            success = stats.get('success', 0)
            failure = stats.get('failure', 0)
            total = success + failure

            if total == 0:
                # No history: neutral score
                return 0

            # Base score: success rate (0-1)
            success_rate = success / total

            # Penalty for consecutive failures
            failure_penalty = min(consecutive_failures / self._failure_threshold, 1.0)

            # Bonus for proven reliability (many successes)
            reliability_bonus = min(success / self._recovery_window, 0.2)

            return success_rate - failure_penalty + reliability_bonus

        return sorted(providers, key=health_score, reverse=True)

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

    def get_sector_list(self) -> dict:
        """Get sector/industry list (行业板块 + 概念板块列表)

        Returns:
            Result dict with success, data (MarketData.data: industries/concepts/total),
            source fields.
        """
        return self._try_providers(self.sector_providers, 'get_sector_list')

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

    def get_stock_info(self, symbol: str) -> dict:
        """Get stock basic information (name, industry, listing date, etc.)

        Args:
            symbol: Stock symbol (e.g., '600000.SH')

        Returns:
            Result dict with success, data (stock info dict), source fields
        """
        # Market provider should provide stock info
        # If not available, return error
        return self._try_providers(
            self.market_providers,
            'get_stock_info',
            symbol
        )

    def get_index_data(self, index_code: str = '000001') -> dict:
        """Get index data (Shanghai, Shenzhen, ChiNext, etc.)

        Args:
            index_code: Index code (e.g., '000001' for Shanghai Composite)
                       Common codes: 000001 (上证), 399001 (深证成指), 399006 (创业板指)

        Returns:
            Result dict with success, data (index constituents or quotes), source fields
        """
        return self._try_providers(
            self.index_providers,
            'get_index_constituents',
            index_code
        )

    def get_north_flow(self) -> dict:
        """Get north-bound capital flow data (沪股通、深股通)

        Returns:
            Result dict with success, data (flow data), source fields
        """
        # HK provider provides south flow (香港资金南下)
        # For north flow (北向资金), market provider should have it
        # Try market providers first, then HK providers
        result = self._try_providers(
            self.market_providers,
            'get_north_flow'
        )
        if not result.get('success'):
            # Fallback to HK provider's south_flow (reciprocal perspective)
            result = self._try_providers(
                self.hk_providers,
                'get_south_flow'
            )
        return result


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
        from adapters.shared.services import ds
        _manager_instance = DataProviderManager(ds=ds)
    return _manager_instance


# Alias for backward compatibility
get_data_source_manager = get_data_provider_manager
