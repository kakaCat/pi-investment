"""Unified data provider manager with automatic failover."""
import logging
from typing import List, Dict, Any, Optional

from domain.exceptions import ExternalServiceError
from domain.ports.datasource_ports import IDataProviderManager
from domain.models.market_data import QuoteData, FinancialData, DividendData, MarketData, StockData

from adapters.outbound.datasources.circuit_breaker import CircuitBreaker
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
from adapters.outbound.datasources.providers.financial.sina import SinaFinancialProvider
from adapters.outbound.datasources.providers.financial.eastmoney import EastmoneyFinancialProvider
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
        # Quote providers: Tencent > Sina > Eastmoney > Akshare (by stability)
        self.quote_providers = [
            TencentQuoteProvider(),      # Fast and stable
            SinaQuoteProvider(),         # Stable, slight delay
            EastmoneyQuoteProvider(),    # Unstable, connection issues
            AkshareQuoteProvider(),      # Very slow (75s), last resort
        ]
        # Financial providers: SinaWeb > Eastmoney > Akshare (by stability)
        self.financial_providers = [
            SinaFinancialProvider(),       # Sina web scraping, generally stable
            EastmoneyFinancialProvider(),  # Eastmoney direct API, sometimes slow
            AkshareFinancialStatementProvider(),  # Akshare fallback
        ]
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
        from adapters.shared.services import get_kline_repo
        self.kline_providers.append(DatabaseKlineProvider(get_kline_repo()))
        self.kline_providers.append(BaostockKlineProvider())
        self.kline_providers.append(TencentKlineProvider())
        self.kline_providers.append(AkshareKlineProvider())

        # Health tracking (cache provider channel status)
        self.provider_stats: Dict[str, Dict[str, int]] = {}
        # Dynamic priority: providers with high failure rate get temporarily deprioritized
        self._failure_threshold = 3  # 连续失败阈值，超过则降级
        self._recovery_window = 5    # 成功次数达到此值则恢复优先级
        # Circuit breaker: 使用 pybreaker 标准三态熔断器 (CLOSED/OPEN/HALF_OPEN)
        self._circuit_breaker_threshold = 10  # 连续失败10次触发熔断
        self._circuit_breaker_duration = 300  # 熔断持续时间（秒）- 5分钟
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._init_stats()

    def _init_stats(self):
        """Initialize provider statistics and circuit breakers"""
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
                'last_attempt_time': 0,
            }
            self._circuit_breakers[provider.name] = CircuitBreaker(
                failure_threshold=self._circuit_breaker_threshold,
                timeout=self._circuit_breaker_duration,
                name=provider.name
            )

    def _is_circuit_broken(self, provider_name: str) -> bool:
        """Check if provider should be skipped (circuit broken AND timeout not expired)"""
        cb = self._circuit_breakers.get(provider_name)
        if cb:
            return not cb.should_allow_call()
        return False

    def _try_providers(self, providers: List, method_name: str, *args, **kwargs) -> dict:
        """Generic failover logic with dynamic priority and circuit breaker

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
                - attempted_sources: list of actually attempted provider names
                - provider_errors: {provider_name: failure reason}
        """
        sorted_providers = self._sort_providers_by_health(providers)

        provider_errors: Dict[str, str] = {}
        attempted_sources: List[str] = []

        for provider in sorted_providers:
            if self._is_circuit_broken(provider.name):
                cb = self._circuit_breakers.get(provider.name)
                state = cb.get_state() if cb else {}
                provider_errors[provider.name] = f'熔断中（{state.get("state", "open")}）'
                continue

            if not hasattr(provider, method_name):
                continue

            attempted_sources.append(provider.name)
            try:
                method = getattr(provider, method_name)
                import concurrent.futures
                guard = concurrent.futures.ThreadPoolExecutor(max_workers=1)

                def _guarded_call():
                    try:
                        return method(*args, **kwargs)
                    finally:
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

                if result is not None and self._is_valid(result):
                    self._record_success(provider.name)
                    return {
                        'success': True,
                        'data': result,
                        'source': provider.name
                    }

                reason = getattr(provider, 'last_error', None) or '返回空数据或数据校验未通过'
                provider_errors[provider.name] = reason
                self._record_failure(provider.name)

            except Exception as e:
                logger.warning(f"Provider {provider.name}.{method_name} failed: {e}")
                provider_errors[provider.name] = f"{type(e).__name__}: {e}"
                self._record_failure(provider.name)

        return {
            'success': False,
            'error': 'All data providers failed',
            'attempted_sources': attempted_sources,
            'provider_errors': provider_errors,
        }

    def _is_valid(self, data) -> bool:
        """Validate data completeness (P0 Enhanced)

        检查：
        1. 基础字段存在（source）
        2. 数据非空（DataFrame/list有实际内容）
        3. 关键字段非NaN（price等）

        Args:
            data: Data object (QuoteData, FinancialData, etc.) or list of such objects

        Returns:
            True if data is valid, False otherwise
        """
        # 基础字段检查：必须有 source
        if not (hasattr(data, 'source') and data.source):
            return False

        # DataFrame检查：必须有行且非空
        if hasattr(data, '__class__') and 'DataFrame' in data.__class__.__name__:
            import pandas as pd
            if hasattr(pd, 'DataFrame') and isinstance(data, pd.DataFrame):
                # 空DataFrame无效（会阻止降级到备用源）
                if len(data) == 0 or data.empty:
                    return False
                # 检查是否所有值都是NaN（有毒数据）
                # 只检查数值列，排除date等字符串列
                numeric_cols = data.select_dtypes(include=[float, int]).columns
                if len(numeric_cols) > 0 and data[numeric_cols].dropna(how='all').empty:
                    return False
                return True

        # 列表检查：必须有元素
        if isinstance(data, list):
            if len(data) == 0:
                return False
            # 递归检查第一个元素
            if hasattr(data[0], 'source'):
                return bool(data[0].source)
            return True

        # QuoteData检查：price必须有效
        if hasattr(data, 'price'):
            import pandas as pd
            if data.price is None or (hasattr(pd, 'isna') and pd.isna(data.price)):
                return False

        # 其他数据类型：有source且有timestamp就认为有效
        if hasattr(data, 'timestamp'):
            return bool(data.timestamp)

        # 默认：有source就认为有效
        return True

    def _record_success(self, provider_name: str):
        """Record successful provider call - resets circuit breaker"""
        import time
        if provider_name in self.provider_stats:
            self.provider_stats[provider_name]['success'] += 1
            self.provider_stats[provider_name]['consecutive_failures'] = 0
            self.provider_stats[provider_name]['last_attempt_time'] = time.time()
        cb = self._circuit_breakers.get(provider_name)
        if cb and cb.is_open():
            cb.reset()

    def _record_failure(self, provider_name: str):
        """Record failed provider call"""
        import time
        if provider_name in self.provider_stats:
            self.provider_stats[provider_name]['failure'] += 1
            consecutive = self.provider_stats[provider_name].get('consecutive_failures', 0) + 1
            self.provider_stats[provider_name]['consecutive_failures'] = consecutive
            self.provider_stats[provider_name]['last_attempt_time'] = time.time()

    def reset_circuit_breakers(self):
        """Manually reset all circuit breakers to CLOSED state"""
        for name, cb in self._circuit_breakers.items():
            cb.reset()
            if name in self.provider_stats:
                self.provider_stats[name]['consecutive_failures'] = 0
        logger.info("All circuit breakers reset")

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
        """Get kline data with automatic failover + backfill to DB

        Args:
            symbol: Stock symbol
            period: Period (daily, weekly, monthly, 1m, 5m, 15m, 30m, 60m)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Result dict with success, data (list of KlineData), source fields

        Backfill: When network provider fetches data (not from DB),
        automatically stores it back to DB for future fast access.
        """
        result = self._try_providers(
            self.kline_providers,
            'get_klines',
            symbol,
            period,
            start_date,
            end_date
        )

        # Backfill: store network-fetched data back to DB
        if (result.get('success') and
            result.get('source') != 'database' and
            result.get('data') and
            period in ['daily', 'weekly', 'monthly']):
            self._backfill_klines_to_db(symbol, result['data'])

        return result

    def _backfill_klines_to_db(self, symbol: str, klines: list) -> bool:
        """Store kline data back to DB for future fast access

        Args:
            symbol: Stock symbol
            klines: List of KlineData objects from network provider

        Returns:
            True if backfill succeeded, False otherwise
        """
        try:
            from infrastructure.persistence.orm.config import get_session
            from infrastructure.persistence.orm.models.stock import DailyKline
            from datetime import datetime
            from dateutil.parser import parse as parse_date

            session = get_session()
            saved_count = 0

            for kline in klines:
                # Convert string date to date object for DB column
                if isinstance(kline.date, str):
                    trade_date = parse_date(kline.date).date()
                else:
                    trade_date = kline.date

                # Skip if already exists
                existing = session.query(DailyKline).filter_by(
                    symbol=symbol,
                    trade_date=trade_date
                ).first()
                if existing:
                    continue

                daily = DailyKline(
                    symbol=symbol,
                    trade_date=trade_date,
                    open=kline.open,
                    high=kline.high,
                    low=kline.low,
                    close=kline.close,
                    volume=kline.volume,
                    source=kline.source,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(daily)
                saved_count += 1

            if saved_count > 0:
                session.commit()
                logger.info(f"Backfilled {saved_count} klines for {symbol} to DB")

            return True

        except Exception as e:
            logger.error(f"Backfill klines to DB failed for {symbol}: {e}")
            try:
                session.rollback()
            except Exception:
                pass
            return False

    def get_data_completeness(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        data: Any = None
    ) -> Dict[str, Any]:
        """Check K-line data completeness against trading calendar

        对比实际K线数据与交易日历，识别缺失交易日

        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            data: Optional K-line data (DataFrame or list of KlineData)
                  If None, fetch from providers automatically

        Returns:
            {
                'completeness': 0.95,      # Percentage (0-1)
                'expected_days': 20,       # Expected trading days
                'actual_days': 19,         # Actual data days
                'missing_dates': ['2024-01-15'],  # Missing trading days
                'has_data': True,          # Whether any data exists
                'source': 'database'       # Data source if fetched
            }
        """
        try:
            # Step 1: Get expected trading days from calendar
            from application.services.trading_calendar_service import TradingCalendarService

            calendar_service = TradingCalendarService()
            expected_days = calendar_service.get_trading_days(start_date, end_date)
            expected_count = len(expected_days)

            if expected_count == 0:
                return {
                    'completeness': 0.0,
                    'expected_days': 0,
                    'actual_days': 0,
                    'missing_dates': [],
                    'has_data': False,
                    'error': 'No trading days in date range'
                }

            # Step 2: Get actual K-line data
            actual_dates = set()
            data_source = None

            if data is None:
                # Fetch from providers
                result = self.get_klines(symbol, 'daily', start_date, end_date)
                if result.get('success'):
                    data = result.get('data', [])
                    data_source = result.get('source')
                else:
                    return {
                        'completeness': 0.0,
                        'expected_days': expected_count,
                        'actual_days': 0,
                        'missing_dates': expected_days,
                        'has_data': False,
                        'error': result.get('error', 'Failed to fetch data')
                    }

            # Step 3: Extract dates from data
            if hasattr(data, '__class__') and 'DataFrame' in data.__class__.__name__:
                # pandas DataFrame
                import pandas as pd
                if isinstance(data, pd.DataFrame):
                    if 'date' in data.columns:
                        actual_dates = set(pd.to_datetime(data['date']).dt.strftime('%Y-%m-%d').tolist())
                    elif 'trade_date' in data.columns:
                        actual_dates = set(pd.to_datetime(data['trade_date']).dt.strftime('%Y-%m-%d').tolist())
            elif isinstance(data, list):
                # List of KlineData objects or dicts
                for item in data:
                    if hasattr(item, 'date'):
                        date_str = item.date if isinstance(item.date, str) else item.date.strftime('%Y-%m-%d')
                        actual_dates.add(date_str)
                    elif isinstance(item, dict) and 'date' in item:
                        actual_dates.add(item['date'])
                    elif isinstance(item, dict) and 'trade_date' in item:
                        actual_dates.add(item['trade_date'])

            # Step 4: Compare and calculate completeness
            actual_count = len(actual_dates)
            expected_set = set(expected_days)
            missing_dates = sorted(list(expected_set - actual_dates))

            completeness = actual_count / expected_count if expected_count > 0 else 0.0

            result = {
                'completeness': round(completeness, 4),
                'expected_days': expected_count,
                'actual_days': actual_count,
                'missing_dates': missing_dates,
                'has_data': actual_count > 0
            }

            if data_source:
                result['source'] = data_source

            return result

        except Exception as e:
            logger.error(f"Failed to check data completeness for {symbol}: {e}")
            return {
                'completeness': 0.0,
                'expected_days': 0,
                'actual_days': 0,
                'missing_dates': [],
                'has_data': False,
                'error': f'Completeness check failed: {str(e)}'
            }

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
        _manager_instance = DataProviderManager()
    return _manager_instance


# Alias for backward compatibility
get_data_source_manager = get_data_provider_manager
