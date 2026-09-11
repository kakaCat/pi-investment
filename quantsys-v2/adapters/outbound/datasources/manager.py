"""Unified data provider manager with automatic failover."""
import logging
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta
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
from adapters.outbound.datasources.providers.dividend.eastmoney import EastmoneyDividendProvider
from adapters.outbound.datasources.providers.market.akshare import AkshareMarketProvider
from adapters.outbound.datasources.providers.market.ths import ThsMarketProvider
from adapters.outbound.datasources.providers.market.sina import SinaMarketProvider
from adapters.outbound.datasources.providers.kline.database import DatabaseKlineProvider
from adapters.outbound.datasources.providers.kline.sina import SinaKlineProvider
from adapters.outbound.datasources.providers.kline.tencent import TencentKlineProvider
from adapters.outbound.datasources.providers.kline.baostock import BaostockKlineProvider
from adapters.outbound.datasources.providers.kline.akshare import AkshareKlineProvider
from adapters.outbound.datasources.providers.minute_kline.database import DatabaseMinuteKlineProvider
from adapters.outbound.datasources.providers.minute_kline.tencent import TencentMinuteKlineProvider
from adapters.outbound.datasources.providers.minute_kline.sina import SinaMinuteKlineProvider
from adapters.outbound.datasources.providers.industry_chain.curated import CuratedChainProvider
from adapters.outbound.datasources.providers.industry_chain.eastmoney_revenue import (
    EastmoneyRevenueProvider, ThsRevenueProvider,
)
from adapters.outbound.datasources.providers.industry_chain.akshare_concept import AkshareConceptProvider
from adapters.outbound.datasources.providers.industry_chain.database import DatabaseChainProvider
from adapters.outbound.datasources.providers.sector.eastmoney import EastmoneySectorProvider
from adapters.outbound.datasources.providers.sector.akshare import AkshareSectorProvider
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
        # 2026-09-11（REQ-cf627b，w-f436d4ea）：分红源由单源（akshare，且其字段映射曾错致
        # 全 0）改为多源故障转移——akshare（已修列名映射）优先、东财 datacenter 兜底
        # （可补 akshare 缺失的股息率）。
        self.dividend_providers = [
            AkshareDividendProvider(),
            EastmoneyDividendProvider(),
        ]
        self.market_providers = [
            AkshareMarketProvider(),
            ThsMarketProvider(),   # 2026-09-01 备用：东财 WAF 封禁时的板块资金流（同花顺）
            SinaMarketProvider(),  # 2026-09-01 备用：东财龙虎榜异常时的 failover（新浪）
        ]
        self.sector_providers = [
            EastmoneySectorProvider(),
            AkshareSectorProvider(),  # 备选：新浪行业 + 同花顺概念（独立通道 failover，2026-09-01）
        ]
        self.stock_providers = [
            AkshareStockProvider(),
        ]
        self.index_providers = [
            AkshareIndexProvider(),
        ]
        # Kline providers: database first (fast), sina 为网络首选（稳定可靠，
        # 2026-09-02 验证可用），baostock 黑名单、tencent 501、eastmoney 代理故障均已失效
        self.kline_providers = []
        from adapters.shared.services import get_kline_repo
        self.kline_providers.append(DatabaseKlineProvider(get_kline_repo()))
        self.kline_providers.append(SinaKlineProvider())
        self.kline_providers.append(BaostockKlineProvider())  # 黑名单，但保留作为备选
        self.kline_providers.append(TencentKlineProvider())   # 501 错误，保留作为备选
        self.kline_providers.append(AkshareKlineProvider())   # 代理故障，保留作为备选

        # 分钟线 providers（RFC 015 §4.3 / §1.5，2026-09-11 REQ-cf627b）：
        # 要求 ≥2 个**独立上游通道** + 本地 DB 兜底（DB 必须放最后）。
        # - tencent_minute：ifzq.gtimg.cn（实测 200，支持 m1~m60）
        # - sina_minute：quotes.sina.cn（实测 200，支持 5/15/30/60）
        # - eastmoney_minute：**未注册** —— push2his.eastmoney.com 本机不可达
        #   （直连/代理/编号子域全部失败，打样记录见该 provider 模块 docstring）；
        #   按 §1.5 硬约束 3，未经真实响应打样的 provider 不得进注册表。
        # - database_minute：quant.minute_klines 兜底（stale，实测只到 2026-05-29）
        # name 与日线 provider 刻意区分（tencent/sina/database），避免共用熔断器与健康统计。
        self.minute_kline_providers = []
        from adapters.outbound.repositories.minute_kline_repository import get_minute_kline_repo
        self.minute_kline_providers.append(TencentMinuteKlineProvider())
        self.minute_kline_providers.append(SinaMinuteKlineProvider())
        self.minute_kline_providers.append(DatabaseMinuteKlineProvider(get_minute_kline_repo()))

        # 产业链图谱 providers（RFC 015 §2.3 / §1.5，2026-09-11 REQ-cf627b P2）
        # 三条子链路刻意分开（每类的上游通道与降级策略不同）：
        # - 拓扑：curated（人工策展 seed，**权威且不可降级**）→ database_chain（stale 兜底）
        #   说明：本节数据的"多源"要求不适用——无现成产业链接口，拓扑必须人工策展
        #   （RFC §2.3/§7：禁止 LLM 自动生成拓扑），故仍是"权威源 + DB 兜底"两段。
        # - 归位证据：eastmoney_revenue（东财 F10 主营构成，带占比）→ ths_revenue（同花顺 F10
        #   产品构成，独立通道、无占比）→ database_chain（上次落库值，stale）。**≥2 独立通道**。
        # - 候选/补全：akshare_concept（新浪行业成分，低置信，只作候选与交叉校验）
        from adapters.outbound.repositories.industry_chain_repository import get_industry_chain_repo
        self.curated_chain_provider = CuratedChainProvider()
        self.eastmoney_revenue_provider = EastmoneyRevenueProvider()
        self.ths_revenue_provider = ThsRevenueProvider()
        self.concept_chain_provider = AkshareConceptProvider()
        self.database_chain_provider = DatabaseChainProvider(get_industry_chain_repo())
        self.industry_chain_topology_providers = [
            self.curated_chain_provider,      # 放最前：权威拓扑
            self.database_chain_provider,     # 放最后：stale 兜底
        ]
        self.industry_chain_revenue_providers = [
            self.eastmoney_revenue_provider,
            self.ths_revenue_provider,
            self.database_chain_provider,
        ]
        self.industry_chain_concept_providers = [
            self.concept_chain_provider,
        ]
        self.industry_chain_providers = (
            self.industry_chain_topology_providers +
            self.industry_chain_revenue_providers +
            self.industry_chain_concept_providers
        )

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
            self.kline_providers +
            self.minute_kline_providers +
            self.industry_chain_providers
        )
        seen_names = set()
        for provider in all_providers:
            # 同一实例可挂在多个子链路上（如 database_chain 同时做拓扑/归位兜底），
            # 统计与熔断器按 name 只登记一次，避免重复初始化把计数清零。
            if provider.name in seen_names:
                continue
            seen_names.add(provider.name)
            self.provider_stats[provider.name] = {
                'success': 0,
                'failure': 0,
                # 2026-09-11（w-f436d4ea）：「空结果」独立计数——语义上 provider 是**健康**的
                # （它成功回答了这一问，只是该查询无数据），不得与 failure 混计。
                'empty': 0,
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
                        'source': provider.name,
                        # 成功路径同样透出「实际尝试过的源」（2026-09-11，RFC 015 §1.5.3）：
                        # 之前只有全失败路径才带 attempted_sources，成功时调用方无法
                        # 如实回答「这个数据是哪次降级拿到的」。附加键，不影响既有消费者。
                        'attempted_sources': attempted_sources,
                    }

                # 2026-09-11（w-f436d4ea）：拆分「真故障」与「空结果」——
                # provider 自报 last_error 才是故障；否则视为该查询无数据（健康）。
                reason = getattr(provider, 'last_error', None)
                if reason:
                    provider_errors[provider.name] = reason
                    self._record_failure(provider.name)
                else:
                    provider_errors[provider.name] = '返回空数据（非故障：该查询无数据，不计入健康分）'
                    self._record_empty(provider.name)

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
        # 列表检查：必须有元素（提前到前面，避免被 source 检查拦截）
        if isinstance(data, list):
            if len(data) == 0:
                return False
            # 递归检查第一个元素
            if hasattr(data[0], 'source'):
                return bool(data[0].source)
            return True

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

        # 基础字段检查：必须有 source
        if not (hasattr(data, 'source') and data.source):
            return False

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
        """Record failed provider call

        仅用于**真故障**：异常 / 超时 / provider 自报 last_error。
        「返回空数据」不算失败——见 _record_empty。
        """
        import time
        if provider_name in self.provider_stats:
            self.provider_stats[provider_name]['failure'] += 1
            consecutive = self.provider_stats[provider_name].get('consecutive_failures', 0) + 1
            self.provider_stats[provider_name]['consecutive_failures'] = consecutive
            self.provider_stats[provider_name]['last_attempt_time'] = time.time()

    def _record_empty(self, provider_name: str):
        """Record an EMPTY result (provider healthy, query has no data)

        2026-09-11（w-f436d4ea）修复的真实缺陷：此前「返回空数据或数据校验未通过」
        在 _try_providers 里与真故障走同一条 _record_failure 分支，导致
        **某查询无数据把 provider 健康分打掉**。实测后果：东财主营构成遇到 1 只
        无数据标的即记一次连续失败，健康分被零失败的同花顺反超 →
        造船链 by_main_business 从 7 掉到 2（回退到弱证据源，归位质量下降）。

        语义：空结果 = provider 成功回答了「该查询」，只是结果为空 → 不计失败、
        不计连续失败、不影响熔断与排序；只单独计数供可观测性使用。
        （若未来要按「系统性空」降权，应基于 empty 比例另设阈值，
          绝不能与 failure 混计——那正是本次缺陷的成因。）
        """
        import time
        if provider_name in self.provider_stats:
            self.provider_stats.setdefault(provider_name, {})
            self.provider_stats[provider_name]['empty'] = self.provider_stats[provider_name].get('empty', 0) + 1
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

        覆盖度修复（2026-09-10）：数据库 provider 只要返回非空就被当作成功，
        导致"部分覆盖"被当成"已覆盖"——日更任务用 end_date=最近交易日查询，
        DB 返回更早的行后任务判 stale 却不再取实时源，市场级缺口（2026-09-03
        起 5150 只 K 线停在 09-02）被永久固化。现在：DB 结果未覆盖请求窗口
        尾部（最近应有 EOD 的交易日）时，继续走实时源并把两边按日期合并
        （实时优先），合并结果仍照常回写 DB。
        """
        result = self._try_providers(
            self.kline_providers,
            'get_klines',
            symbol,
            period,
            start_date,
            end_date
        )

        if period in ['daily', 'weekly', 'monthly'] and result.get('source') == 'database':
            expected_last = self._expected_last_bar_date(period, end_date)
            db_last = ''
            for k in (result.get('data') or []):
                d = str(getattr(k, 'date', ''))[:10]
                if d > db_last:
                    db_last = d
            if db_last < expected_last:
                network = self._try_providers(
                    self.kline_providers[1:],
                    'get_klines',
                    symbol,
                    period,
                    start_date,
                    end_date
                )
                if network.get('success') and network.get('data'):
                    merged: Dict[str, Any] = {}
                    for k in result.get('data') or []:
                        merged[str(getattr(k, 'date', ''))[:10]] = k
                    for k in network['data']:
                        merged[str(getattr(k, 'date', ''))[:10]] = k
                    result = {
                        'success': True,
                        'data': [merged[d] for d in sorted(merged)],
                        'source': f"database+{network.get('source')}",
                    }
                    logger.info(
                        f"Kline DB 覆盖不足({symbol}: db_last={db_last} < "
                        f"expected={expected_last})，已用实时源补齐至 "
                        f"{max(merged) if merged else db_last}")

        # Backfill: store network-fetched data back to DB
        if (result.get('success') and
            result.get('source') != 'database' and
            result.get('data') and
            period in ['daily', 'weekly', 'monthly']):
            self._backfill_klines_to_db(symbol, result['data'])

        # amount 兜底（2026-09-10）：数据源不返回成交额时上游会留 0
        # （新浪日线接口只有 volume 无 amount）。KlineData 契约要求 provider
        # 估算，个别 provider 未实现——在此统一兜底，防止 0 值流入成交额类
        # 因子/流动性判断（全库曾累积 44.7 万行 amount=0）。
        self._ensure_amount(symbol, result.get('data') or [])

        return result

    @staticmethod
    def _ensure_amount(symbol: str, klines: list) -> int:
        """为缺失成交额的 K 线按 volume×close 估算（与 tencent/baostock 同口径）。

        仅在 volume>0 且 close>0 时估算，避免制造伪值；返回补齐条数。

        指数/伪代码跳过（2026-09-10 w-23c70356）：指数行的 volume 是成分股聚合量，
        volume×close 与"成交额"无物理关系——实测 399001 2026-09-01 被估成
        949.86 万亿元（真实全市场单日约 2 万亿元量级），638 行累计 75,830 万亿元
        污染 daily_klines.amount 并被下游成交额/流动性因子读取。
        """
        from utils.symbol_classifier import is_pseudo_symbol
        if is_pseudo_symbol(symbol):
            logger.info(f"amount 估算跳过（指数/伪代码）: {symbol}")
            return 0
        filled = 0
        for k in klines:
            try:
                if getattr(k, 'amount', None):
                    continue
                volume = float(getattr(k, 'volume', 0) or 0)
                close = float(getattr(k, 'close', 0) or 0)
                if volume > 0 and close > 0:
                    k.amount = round(volume * close, 2)
                    filled += 1
            except (TypeError, ValueError):
                continue
        if filled:
            logger.info(f"amount 缺失按 volume×close 估算补齐 {filled} 条")
        return filled

    @staticmethod
    def _expected_last_bar_date(period: str, end_date: str) -> str:
        """请求窗口尾部"最近应当已有 EOD 数据"的日期（用于覆盖度判定）。

        规则：不晚于 min(end_date, 今天)，再回退到最近的工作日。
        无交易日历（节假日按工作日处理）——偏保守，最坏情况是多取一次实时源，
        不影响正确性；宁可多取，也不要把缺口当已覆盖。
        """
        try:
            if period in ('weekly', 'monthly'):
                # 周/月线只需覆盖到窗口内即可，不做工作日回退（由调用方按需取源）
                return end_date
            end = _datetime.strptime(end_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return end_date
        today = _date.today()
        if end > today:
            end = today
        while end.weekday() >= 5:
            end -= _timedelta(days=1)
        return end.strftime('%Y-%m-%d')

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
            from infrastructure.persistence.orm.models.stock import DailyKline, Stock
            from datetime import datetime
            from dateutil.parser import parse as parse_date

            session = get_session()
            
            # 确保股票元数据存在（防止外键约束错误）
            stock = session.query(Stock).filter(Stock.symbol == symbol).first()
            if not stock:
                # 自动创建股票元数据（market 必须可从代码推断，见 infer_market 说明）
                from adapters.shared.market_helpers import infer_market
                market = infer_market(symbol)
                if market is None:
                    logger.warning(
                        f"Skip kline backfill for {symbol}: 无法从代码推断 market"
                        f"（仅支持 A 股 6 位/港股 5 位），拒绝用非法占位值建 stocks 行")
                    return False
                stock = Stock(
                    symbol=symbol,
                    name=symbol,  # 临时使用代码作为名称
                    market=market
                )
                session.add(stock)
                session.flush()  # 立即写入，确保后续 K 线插入有外键
                logger.warning(f"Auto-created stock metadata for {symbol} (backfill K线时缺失, market={market})")
            
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
                    source=kline.source
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

    # ==================== 分钟线（RFC 015 §4.3，2026-09-11 REQ-cf627b） ====================

    def get_minute_klines(
        self,
        symbol: str,
        period: str = '5m',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 240,
    ) -> dict:
        """分钟线多源取数（复用 _try_providers：独立超时 + 熔断 + 动态优先级）

        Args:
            symbol: 股票代码
            period: '1m'/'5m'/'15m'/'30m'/'60m'（或裸数字）
            start_date/end_date: 'YYYY-MM-DD'（可空；上游为「最近 N 根」型接口）
            limit: 最大返回根数

        Returns:
            dict：
              success=True  → data(List[MinuteKline]) / source / attempted_sources
              success=False → error='All data providers failed' / attempted_sources /
                              provider_errors {源: 失败原因}（**显式失败**，不返回空数组）
        """
        result = self._try_providers(
            self.minute_kline_providers,
            'get_minute_klines',
            symbol,
            period,
            start_date,
            end_date,
            limit=limit,
        )
        # 把「provider 掌握的事实」（库内最后一根时间 / 推断粒度）透传给调用方，
        # 供应用层判定 stale 与粒度（不在这里替调用方下结论）
        if result.get('success'):
            provider = next(
                (p for p in self.minute_kline_providers if p.name == result.get('source')), None
            )
            if provider is not None:
                for attr in ('latest_bar_datetime', 'granularity'):
                    if hasattr(provider, attr):
                        result[attr] = getattr(provider, attr)
        return result

    def cross_check_minute_klines(
        self,
        symbol: str,
        period: str = '5m',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 240,
        max_sources: int = 2,
    ) -> dict:
        """跨源一致性校验（RFC 015 §1.5 硬约束 6）

        故障转移路径同一时刻只有 1 个源在服务，因此「≥2 源同时返回时的比对」
        必须显式触发：本方法按健康度顺序向最多 max_sources 个**网络源**分别取数，
        在共同时间戳上比对收盘价，超阈值（默认 0.5%）标 divergent + 给出
        cross_source_conflict 明细（取保守解释：数据不可直接采信）。
        DB 兜底源不参与实时比对（它是历史快照，天然与实时源不一致）。
        """
        from statistics import fmean

        results: Dict[str, list] = {}
        skipped: Dict[str, str] = {}
        for provider in self._sort_providers_by_health(self.minute_kline_providers):
            if len(results) >= int(max_sources):
                break
            if provider.name == 'database_minute':
                skipped[provider.name] = 'DB 为历史兜底源，不参与实时一致性比对'
                continue
            if self._is_circuit_broken(provider.name):
                skipped[provider.name] = '熔断中'
                continue
            try:
                data = provider.get_minute_klines(symbol, period, start_date, end_date, limit=limit)
            except Exception as e:
                skipped[provider.name] = f"{type(e).__name__}: {e}"
                continue
            if data:
                results[provider.name] = data
            else:
                skipped[provider.name] = getattr(provider, 'last_error', None) or '返回空结果'

        as_of = _datetime.now().isoformat()
        if len(results) < 2:
            return {
                'success': False,
                'error': f'不足 2 个独立通道同时返回数据（{len(results)} 个），无法交叉校验',
                'sources_returned': {k: len(v) for k, v in results.items()},
                'skipped': skipped,
                'as_of': as_of,
            }

        names = list(results)
        left, right = results[names[0]], results[names[1]]
        left_map = {str(b.trade_datetime): b.close for b in left}
        diffs = []
        for bar in right:
            ref = left_map.get(str(bar.trade_datetime))
            if ref:
                diffs.append(abs(bar.close - ref) / ref * 100)
        if not diffs:
            return {
                'success': False,
                'error': '两源无共同时间戳，无法比对（时间戳口径可能不一致）',
                'sources_returned': {k: len(v) for k, v in results.items()},
                'as_of': as_of,
            }

        threshold = 0.5
        avg_diff = fmean(diffs)
        max_diff = max(diffs)
        diverged = avg_diff > threshold
        return {
            'success': True,
            'verdict': 'divergent' if diverged else 'consistent',
            'sources_returned': {k: len(v) for k, v in results.items()},
            'compared_sources': names[:2],
            'common_bars': len(diffs),
            'avg_close_diff_pct': round(avg_diff, 4),
            'max_close_diff_pct': round(max_diff, 4),
            'threshold_pct': threshold,
            'cross_source_conflict': ({
                'type': 'minute_kline_close_divergence',
                'sources': names[:2],
                'avg_close_diff_pct': round(avg_diff, 4),
                'max_close_diff_pct': round(max_diff, 4),
                'threshold_pct': threshold,
                'resolution': 'conservative: 该窗口分钟线不直接采信，需人工/多源复核',
            } if diverged else None),
            'skipped': skipped,
            'as_of': as_of,
        }

    def get_stock_base_status(self, symbol: str) -> dict:
        """stocks 表基础交易状态（is_st / is_suspended / is_delisted + 最近日线昨收）

        说明：这是**本地 DB 单源事实**，不是可故障转移的外部数据源，
        因此不走 _try_providers（没有第二个通道可以顶替 stocks 表）。
        实时维度由调用方叠加行情通道（get_quote）后交给
        domain.trading.services.TradingStatusPolicy 做保守裁决。
        """
        try:
            from adapters.outbound.repositories.trading_status_repository import get_trading_status_repo
            status = get_trading_status_repo().get_stock_status(symbol)
        except Exception as e:
            logger.warning(f"get_stock_base_status failed for {symbol}: {e}")
            return {
                'success': False,
                'data': None,
                'source': 'stocks_table',
                'error': f'stocks 表查询失败: {type(e).__name__}: {e}',
            }
        if status is None:
            return {
                'success': False,
                'data': None,
                'source': 'stocks_table',
                'error': f'stocks 表无 {symbol}（未入库/非 A 股代码）——无法确认基础交易状态',
            }
        return {'success': True, 'data': status, 'source': 'stocks_table'}

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

    # ---------------------------------------------------------------- 产业链图谱
    # RFC 015 §2.3 / §1.5（2026-09-11 REQ-cf627b P2）。返回值沿用 _try_providers 的统一结构：
    #   {success, data, source, attempted_sources} / {success=False, error, attempted_sources, provider_errors}
    # 契约：全部源失败 → success=False（**显式失败**）；某源返回空 → 继续下一源；
    # 禁止用空数组冒充成功（失败与空结果语义分离，§1.5.2 硬约束 5）。

    def list_industry_chains(self) -> dict:
        """产业链清单（人工策展 → DB 兜底）"""
        return self._try_providers(self.industry_chain_topology_providers, 'list_chains')

    def get_industry_chain(self, chain_id_or_name: str) -> dict:
        """单链环节 + 成员（人工策展 → DB 兜底，DB 命中即 stale）"""
        return self._try_providers(
            self.industry_chain_topology_providers, 'get_chain', chain_id_or_name,
        )

    def get_industry_chain_topology(self, chain_id_or_name: str) -> dict:
        """**仅人工策展源**取拓扑（不可降级）

        为什么单独开一个口子：拓扑错了，整条链的成员归位全错（比无数据更危险）。
        故 build_chain 必须走本方法——策展源取不到就显式失败，不允许任何下游源"补"拓扑。
        """
        return self._try_providers(
            [self.curated_chain_provider], 'get_chain', chain_id_or_name,
        )

    def get_industry_chain_revenue(self, symbol: str) -> dict:
        """个股主营/产品构成（东财 F10 带占比 → 同花顺 F10 文本 → DB 缓存）

        多源矩阵（§1.5.2 硬约束 1）：东财与同花顺是**不同上游通道**；DB 为最后一级兜底
        （返回行带 stale=True，调用方必须标注）。

        **为什么分两段调用而不是一个列表**：`_try_providers` 内部按健康分排序（动态降权），
        实测（2026-09-11，造船链 8 只标的）同花顺会因"零失败"被排到东财之前——东财只要遇到
        一只没有主营构成数据的标的（如中国重工 601989 返回空）即计一次失败，健康分被反超，
        后续标的全部降级到同花顺，**白丢带营收占比的硬证据**（占比是成员归位的唯一硬证据）。
        两段调用 = 显式表达"权威通道优先、文本通道兜底"，同时仍复用 _try_providers 的
        超时/熔断/attempted_sources 机制，不另起链路。
        """
        primary = self._try_providers([self.eastmoney_revenue_provider], 'get_revenue_exposure', symbol)
        if primary.get('success'):
            return primary
        fallback = self._try_providers(
            [self.ths_revenue_provider, self.database_chain_provider], 'get_revenue_exposure', symbol,
        )
        fallback['attempted_sources'] = (
            (primary.get('attempted_sources') or []) + (fallback.get('attempted_sources') or [])
        )
        merged_errors = dict(primary.get('provider_errors') or {})
        merged_errors.update(fallback.get('provider_errors') or {})
        fallback['provider_errors'] = merged_errors
        return fallback

    def get_industry_chain_candidates(self, sector_name: str) -> dict:
        """行业板块成员（低置信候选源：新浪行业，经 akshare）"""
        return self._try_providers(self.industry_chain_concept_providers, 'get_chain', sector_name)

    def list_industry_chain_candidates(self) -> dict:
        """候选板块清单（新浪行业）"""
        return self._try_providers(self.industry_chain_concept_providers, 'list_chains')

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
