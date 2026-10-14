"""
交易日历服务

提供交易日历查询功能，支持多种数据源和缓存策略。

⚠️ 2026-10-04（REQ-261004154902-a7cd · FR-3）：**「工作日兜底」不再静默**。
此前 `get_trading_days` **先**按"周一~周五"生成结果、只有上游取数成功才替换 →
上游一挂就把法定节假日（如 2026 国庆 10-01~10-07）当成交易日，且**无任何标注**。
现在兜底会带出 `source=weekday_fallback` / `degraded=True`：既写一条 warning 日志，
也可经 `get_trading_days_with_meta()` 拿到标注后自行处置。
`get_trading_days` / `is_trading_day` **签名与返回类型不变**（既有调用方照常工作）。
"""
import structlog
from dataclasses import dataclass
from typing import Any, List, Optional
from datetime import datetime, timedelta, date
import json
from domain.ports.datasource_ports import IDataProviderManager
from domain.trading.ports.ITradingCalendar import ITradingCalendar

logger = structlog.get_logger(__name__)

# 交易日列表的来源（对外契约：降级必须可标注）
SOURCE_PROVIDER = 'provider'
#: 周一~周五兜底 —— 上游取数失败时的旧行为；`degraded=True`，休市期会把节假日当交易日
SOURCE_WEEKDAY_FALLBACK = 'weekday_fallback'
#: 来自缓存（Redis / 内存），来源沿用写入时标注
SOURCE_CACHE = 'cache'


@dataclass(frozen=True)
class TradingDaysResult:
    """交易日列表 + 来源标注（FR-3：兜底不许静默）。

    - `days`：交易日列表（`YYYY-MM-DD`，升序）——与 `get_trading_days` 的返回值逐字一致；
    - `source`：`provider` | `weekday_fallback` | `cache`；
    - `degraded`：是否走了周一~周五兜底（True 时休市期会把法定节假日当交易日，
      写入/统计类调用方必须自行处置或至少留痕）。
    """

    days: List[str]
    source: str
    degraded: bool


class TradingCalendarService(ITradingCalendar):
    """交易日历服务

    提供交易日历查询，数据源优先级：
    1. Redis 缓存（TTL 1天）- 最快
    2. 数据库 daily_klines（DISTINCT trade_date）- 次快
    3. AkShare API（tool_trade_date_hist_sina）- Fallback
    """

    def __init__(self, kline_repo=None, redis_client=None):
        """初始化交易日历服务

        Args:
            kline_repo: K线数据仓库实例
            redis_client: Redis客户端实例（可选）
        """
        from domain.ports import IKlineRepository

        self.kline_repo = kline_repo
        self.redis = redis_client
        self._cache = {}  # 内存缓存作为 Redis 的 fallback

    def get_trading_days(
        self,
        start_date: str,
        end_date: str,
        exchange: str = 'SSE'
    ) -> List[str]:
        """获取指定日期范围内的所有交易日

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            exchange: 交易所代码 ('SSE', 'SZSE', 'ALL')

        Returns:
            交易日列表（YYYY-MM-DD格式），按日期升序

        需要知道这份列表**是不是兜底来的**时请用 `get_trading_days_with_meta()`：
        兜底（`weekday_fallback`）会在这里留一条 warning，但返回值本身没有标注位。
        """
        return self.get_trading_days_with_meta(start_date, end_date, exchange).days

    def get_trading_days_with_meta(
        self,
        start_date: str,
        end_date: str,
        exchange: str = 'SSE'
    ) -> TradingDaysResult:
        """同 `get_trading_days`，但**带来源与降级标注**（FR-3）。

        返回 `TradingDaysResult`：`days` 与 `get_trading_days` 逐字一致，
        `source` / `degraded` 说明这份列表是上游取的还是周一~周五兜底的。
        """
        cache_key = f"trading_days:{exchange}:{start_date}:{end_date}"

        cached = self._read_cache(cache_key)
        if cached is not None:
            logger.debug(f"从缓存获取交易日历: {start_date} ~ {end_date}")
            return cached

        # 1. 先按"周一~周五"生成兜底（最可靠：不会因数据库没数据而把某天当成交易日）
        logger.info(f"使用工作日规则生成交易日历: {start_date} ~ {end_date}")
        weekdays = self._generate_weekdays(start_date, end_date)

        # 2. 尝试从 DataProviderManager 获取精确的交易日历（用于排除节假日）
        provider_days = self._read_provider_days(start_date, end_date)
        if provider_days:
            result = TradingDaysResult(provider_days, SOURCE_PROVIDER, False)
        else:
            # 2026-10-04（FR-3）：兜底不再静默 —— 带 source/degraded 且**升为 warning**
            # （原先只打 info，读日志的人根本不知道这份日历没排节假日）。
            logger.warning(
                'trading_calendar_weekday_fallback',
                start_date=start_date,
                end_date=end_date,
                exchange=exchange,
                days=len(weekdays),
                source=SOURCE_WEEKDAY_FALLBACK,
                degraded=True,
                note='上游交易日历不可用：已按周一~周五兜底，法定节假日会被当作交易日；'
                     '写入/统计类调用方请按 degraded 处置或改用 TradingDayGuard',
            )
            result = TradingDaysResult(weekdays, SOURCE_WEEKDAY_FALLBACK, True)

        self._cache_trading_days(cache_key, result)
        return result

    def _read_provider_days(self, start_date: str, end_date: str) -> List[str]:
        """向上游要精确日历；失败/空一律返回 `[]`（由调用方走兜底并标注），不抛异常。

        2026-09-10 修复（investor / w-8f2c4cc5）：此处曾调用裸名 `get_data_provider_manager()`，
        但本模块从未导入该名字（datasource 迁移只补了 IDataProviderManager 类型导入），
        每次调用都抛 NameError 并被 except 吞掉 → 永远静默降级为"周一~周五"，
        法定节假日（如 2026-10-01 国庆）被当成交易日（trade_guard / data_quality /
        signal_tracking / DataProviderManager 均走此路径）。
        统一经 ServiceFactory 解析（application 层不直接依赖 adapters），保留原降级路径。
        """
        try:
            from infrastructure.services.service_factory import ServiceFactory
            manager: IDataProviderManager = ServiceFactory.get_data_provider_manager()
            result = manager.get_trading_calendar(start_date, end_date)

            if result.get('success') and result.get('data'):
                stock_data = result['data']
                # StockData.data 是 list[dict]，每个 dict 有 trade_date 键
                calendar_records = stock_data.data if hasattr(stock_data, 'data') else stock_data
                if isinstance(calendar_records, list) and len(calendar_records) > 0:
                    # 提取 trade_date 字段
                    if isinstance(calendar_records[0], dict) and 'trade_date' in calendar_records[0]:
                        trading_days = [r['trade_date'] for r in calendar_records
                                        if start_date <= r['trade_date'] <= end_date]
                    else:
                        # fallback: 直接取字符串值
                        trading_days = [str(r) for r in calendar_records
                                        if start_date <= str(r) <= end_date]

                    if trading_days and len(trading_days) > 0:
                        logger.info(f"从 DataProviderManager 获取到 {len(trading_days)} 个交易日 (source: {result.get('source', 'unknown')})")
                        return trading_days
        except Exception as e:
            logger.warning(f"从 DataProviderManager 获取交易日历失败，使用工作日: {e}")
        return []

    def _read_cache(self, cache_key: str) -> Optional[TradingDaysResult]:
        """读缓存（Redis → 内存）；未命中返回 None。缓存里同样带着来源标注。"""
        if self.redis:
            try:
                cached = self.redis.get(cache_key)
            except Exception as e:
                logger.warning(f"Redis 缓存读取失败: {e}")
                cached = None
            decoded = self._decode_cache(cached) if cached else None
            if decoded is not None:
                return decoded

        entry = self._cache.get(cache_key)
        if entry and datetime.now() < entry['expires_at']:
            return TradingDaysResult(
                list(entry['data']),
                entry.get('source', SOURCE_CACHE),
                bool(entry.get('degraded', False)),
            )
        return None

    def _decode_cache(self, cached: Any) -> Optional[TradingDaysResult]:
        """解析缓存载荷：新格式 = `{data, source, degraded}`；旧格式 = 裸列表。"""
        try:
            payload = json.loads(cached) if isinstance(cached, (str, bytes, bytearray)) else cached
        except Exception as e:
            logger.warning(f"缓存载荷无法解析，忽略: {e}")
            return None
        if isinstance(payload, dict) and 'data' in payload:
            return TradingDaysResult(
                list(payload['data']),
                payload.get('source', SOURCE_CACHE),
                bool(payload.get('degraded', False)),
            )
        if isinstance(payload, list):
            # 旧格式（升级前写入的缓存，TTL 1 天）：来源未知 → 按降级标注，不许静默
            logger.warning('trading_calendar_cache_legacy_payload', note='缓存为旧格式（无来源标注），按 degraded 处置')
            return TradingDaysResult([str(d) for d in payload], SOURCE_CACHE, True)
        return None

    def _cache_trading_days(self, cache_key: str, result: TradingDaysResult):
        """缓存交易日历数据（连同来源标注一起存，命中时不丢 degraded）。

        Args:
            cache_key: 缓存键
            result: 带来源标注的交易日列表
        """
        # Redis 缓存（TTL 1天）
        if self.redis:
            try:
                self.redis.setex(cache_key, 86400, json.dumps(
                    {'data': result.days, 'source': result.source, 'degraded': result.degraded}
                ))
            except Exception as e:
                logger.warning(f"Redis 缓存写入失败: {e}")

        # 内存缓存
        self._cache[cache_key] = {
            'data': list(result.days),
            'source': result.source,
            'degraded': result.degraded,
            'expires_at': datetime.now() + timedelta(days=1)
        }

    def _generate_weekdays(self, start_date: str, end_date: str) -> List[str]:
        """生成工作日列表（排除周末）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            工作日列表
        """
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        weekdays = []
        current = start
        while current <= end:
            # 排除周六(5)和周日(6)
            if current.weekday() < 5:
                weekdays.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)

        return weekdays

    def is_trading_day(self, check_date: str, exchange: str = 'SSE') -> bool:
        """判断指定日期是否为交易日

        Args:
            check_date: 日期 (YYYY-MM-DD)
            exchange: 交易所代码

        Returns:
            True if 交易日，否则 False
        """
        # 获取前后一周的交易日历
        check_dt = datetime.strptime(check_date, '%Y-%m-%d').date()
        start_date = (check_dt - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = (check_dt + timedelta(days=7)).strftime('%Y-%m-%d')

        trading_days = self.get_trading_days(start_date, end_date, exchange)
        return check_date in trading_days

    def get_next_trading_day(
        self,
        from_date: str,
        exchange: str = 'SSE'
    ) -> Optional[str]:
        """获取下一个交易日

        Args:
            from_date: 起始日期 (YYYY-MM-DD)
            exchange: 交易所代码

        Returns:
            下一个交易日，如果没有返回 None
        """
        from_dt = datetime.strptime(from_date, '%Y-%m-%d').date()
        end_date = (from_dt + timedelta(days=30)).strftime('%Y-%m-%d')

        trading_days = self.get_trading_days(from_date, end_date, exchange)

        # 找到第一个大于 from_date 的交易日
        for day in trading_days:
            if day > from_date:
                return day

        return None

    def get_prev_trading_day(
        self,
        from_date: str,
        exchange: str = 'SSE'
    ) -> Optional[str]:
        """获取上一个交易日

        Args:
            from_date: 起始日期 (YYYY-MM-DD)
            exchange: 交易所代码

        Returns:
            上一个交易日，如果没有返回 None
        """
        from_dt = datetime.strptime(from_date, '%Y-%m-%d').date()
        start_date = (from_dt - timedelta(days=30)).strftime('%Y-%m-%d')

        trading_days = self.get_trading_days(start_date, from_date, exchange)

        # 找到最后一个小于 from_date 的交易日
        for day in reversed(trading_days):
            if day < from_date:
                return day

        return None

    def get_trading_days_count(
        self,
        start_date: str,
        end_date: str,
        exchange: str = 'SSE'
    ) -> int:
        """获取指定日期范围内的交易日数量

        Args:
            start_date: 开始日期
            end_date: 结束日期
            exchange: 交易所代码

        Returns:
            交易日数量
        """
        trading_days = self.get_trading_days(start_date, end_date, exchange)
        return len(trading_days)
