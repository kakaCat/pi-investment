"""Unified data provider manager with automatic failover."""
import logging
from typing import List, Dict, Any, Optional

from domain.exceptions import ExternalServiceError
from domain.ports.datasource_ports import IDataProviderManager
from domain.models.market_data import QuoteData, FinancialData, DividendData, MarketData, StockData

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
from adapters.outbound.datasources.providers.financial.akshare import AkshareFinancialStatementProvider
from adapters.outbound.datasources.providers.hk.akshare import AkshareHKProvider

logger = logging.getLogger(__name__)


class DataProviderManager(IDataProviderManager):
    """Unified data provider manager

    实现 IDataProviderManager 接口

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
        self.financial_statement_providers = [
            AkshareFinancialStatementProvider(),
        ]
        self.hk_providers = [
            AkshareHKProvider(),
        ]
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
            self.kline_providers
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

    def get_lhb_detail(self, symbol: str, start_date: str, end_date: str) -> dict:
        """获取指定股票在日期区间内的龙虎榜明细"""
        return self._try_providers(
            self.market_providers,
            'get_lhb_detail',
            symbol,
            start_date,
            end_date
        )

    def get_zt_pool(self, date: str) -> dict:
        """获取涨停池"""
        return self._try_providers(
            self.market_providers,
            'get_zt_pool',
            date
        )

    def get_hk_market_overview(self) -> dict:
        """港股市场概览（恒指现货 + 港股通持股）"""
        return self._try_providers(self.hk_providers, 'get_hk_market_overview')

    def get_south_flow(self) -> dict:
        """南向资金流向"""
        return self._try_providers(self.hk_providers, 'get_south_flow')

    def get_hk_hot_rank(self) -> dict:
        """港股人气排行"""
        return self._try_providers(self.hk_providers, 'get_hk_hot_rank')

    def get_hk_daily(self, symbol: str) -> dict:
        """港股日K（前复权）"""
        return self._try_providers(self.hk_providers, 'get_hk_daily', symbol)

    def get_hk_financials(self, symbol: str) -> dict:
        """港股财务指标"""
        return self._try_providers(self.hk_providers, 'get_hk_financials', symbol)

    def get_sina_financial_statements(self, clean_symbol: str) -> dict:
        """新浪三大报表全量原始记录（策略沙箱财务注入用，不截断）"""
        return self._try_providers(self.financial_statement_providers, 'get_sina_statements', clean_symbol)

    def get_financial_analysis_indicator(self, clean_symbol: str) -> dict:
        """东财财务分析指标全量原始记录（策略沙箱用，不截断）"""
        return self._try_providers(self.financial_statement_providers, 'get_financial_analysis_indicator', clean_symbol)

    def get_cash_flow_sheet(self, symbol: str) -> dict:
        """现金流量表（symbol 为东财格式如 SH600519）"""
        return self._try_providers(self.financial_statement_providers, 'get_cash_flow_sheet', symbol)

    def get_profit_sheet(self, symbol: str) -> dict:
        """利润表（symbol 为东财格式如 SH600519）"""
        return self._try_providers(self.financial_statement_providers, 'get_profit_sheet', symbol)

    def get_insider_trades(self, symbol: str) -> dict:
        """股东增减持数据（内幕交易替代指标）"""
        return self._try_providers(self.market_providers, 'get_insider_trades', symbol)

    def get_market_margin(self) -> dict:
        """全市场融资融券余额（sh 历史 + sz 当日）"""
        return self._try_providers(self.market_providers, 'get_market_margin')

    def get_sector_fund_flow(self, indicator: str = '今日') -> dict:
        """行业资金流向排行（indicator: 今日/5日/10日）"""
        return self._try_providers(self.market_providers, 'get_sector_fund_flow', indicator)

    def get_macro_data(self) -> dict:
        """宏观经济数据（GDP/CPI/PMI 最新值）"""
        return self._try_providers(self.market_providers, 'get_macro_data')

    def get_market_news(self) -> dict:
        """全市场财经新闻（区别于 get_news 的个股新闻）"""
        return self._try_providers(self.market_providers, 'get_market_news')

    def get_index_daily(self, symbol: str) -> dict:
        """指数历史日K（symbol 如 sh000300）"""
        return self._try_providers(self.market_providers, 'get_index_daily', symbol)

    def get_market_spot(self) -> dict:
        """获取全市场快照（含 PE/PB/市值等字段）

        Returns:
            Result dict with success, data (MarketData, .data={'records': [...], 'total': n}), source
        """
        return self._try_providers(
            self.market_providers,
            'get_market_spot'
        )

    def get_index_constituents(self, index_code: str) -> dict:
        """获取指数成分股代码列表（csindex 优先 + sina 兜底）

        Args:
            index_code: 指数裸代码（如 '000300' 沪深300、'000688' 科创50、'399006' 创业板指）

        Returns:
            Result dict with success, data (StockData, .data=[{'symbol': '600519'}, ...]), source
        """
        return self._try_providers(
            self.index_providers,
            'get_index_constituents',
            index_code
        )

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

    # ==================== 接口适配方法 ====================
    # 实现 IDataProviderManager 抽象方法，适配到现有实现

    def get_batch_quotes(
        self,
        symbols: List[str],
        timeout: Optional[float] = None
    ) -> Dict[str, QuoteData]:
        """批量获取实时行情（IDataProviderManager 接口方法）"""
        result = self.get_quotes(symbols)
        if result.get('success'):
            return result.get('data', {})
        return {}

    def get_kline(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str = 'daily',
        timeout: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """获取K线数据（IDataProviderManager 接口方法）"""
        result = self.get_klines(symbol, period, start_date, end_date)
        if result.get('success'):
            return result.get('data', [])
        return []

    def get_dividend(
        self,
        symbol: str,
        timeout: Optional[float] = None
    ) -> Optional[DividendData]:
        """获取分红数据（IDataProviderManager 接口方法）"""
        result = self.get_dividends(symbol)
        if result.get('success'):
            data = result.get('data')
            # 转换为 DividendData 对象
            if data:
                return DividendData(**data) if isinstance(data, dict) else data
        return None

    def get_market_data(
        self,
        data_type: str,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Optional[MarketData]:
        """获取市场数据（IDataProviderManager 接口方法）"""
        # 根据 data_type 路由到对应方法
        method_map = {
            'spot': self.get_market_spot,
            'news': self.get_market_news,
            'macro': self.get_macro_data,
        }
        method = method_map.get(data_type)
        if method:
            result = method()
            if result.get('success'):
                data = result.get('data')
                return MarketData(**data) if isinstance(data, dict) else data
        return None

    def get_stock_data(
        self,
        symbol: str,
        data_type: str,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Optional[StockData]:
        """获取股票基础数据（IDataProviderManager 接口方法）"""
        # 根据 data_type 路由到对应方法
        method_map = {
            'info': lambda: self.get_stock_info(symbol),
            'news': lambda: self.get_news(symbol),
        }
        method = method_map.get(data_type)
        if method:
            result = method()
            if result.get('success'):
                data = result.get('data')
                return StockData(**data) if isinstance(data, dict) else data
        return None

    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有 provider 的健康状态（IDataProviderManager 接口方法）"""
        stats = {}
        for name, stat in self.provider_stats.items():
            total = stat['success'] + stat['failure']
            success_rate = stat['success'] / total if total > 0 else 0.0
            stats[name] = {
                'success': stat['success'],
                'failure': stat['failure'],
                'success_rate': success_rate,
                'is_healthy': stat['consecutive_failures'] < self._failure_threshold
            }
        return stats


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
