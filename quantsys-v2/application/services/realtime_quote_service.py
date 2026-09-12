"""
实时行情服务 - 委托给 DataProviderManager

这个服务现在是一个轻量级包装器，将所有逻辑委托给统一的 DataProviderManager。
这保持了向后兼容性，同时使用统一的数据提供者架构。
"""
import os
import time

import structlog
from typing import Optional
from domain.ports.datasource_ports import IDataProviderManager
from domain.models.market_data import QuoteData

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# 模块级行情 TTL 缓存（2026-09-13，w-adb088f2）
#
# 动机（实测）：账户持仓看板整页只依赖一个 host 接口 /dashboard/api/holdings，
# 而它内部会调 /api/simulation/accounts/{name} —— 该接口**每次请求都重新拉实时行情**
# （占整条链路 0.27s 中的 0.13-0.21s，是主项）。看板 15 秒轮询、多标签、并发访问时
# 全都在重复付这笔钱：实测并发 5 次 = 每次 0.98-1.03s（单发仅 0.20-0.29s）。
#
# 缓存必须是**模块级**的：simulation_service 每次调用都 new 一个 RealtimeQuoteService()
# 实例，实例级缓存在这条路径上等于没有。
#
# 口径与既有实现对齐：RealtimeQuoteServiceV2 早已是 5 秒 TTL（缓存 5 秒 + 熔断 60 秒），
# 本条 V1 读路径此前完全没有缓存。TTL 用 QUANTSYS_QUOTE_CACHE_TTL 覆盖，设 0 即关闭。
# 新鲜度可核验：QuoteData.timestamp 随行情一起返回，账户响应里的 price_updated_at
# 即来自它，调用方能如实判断数据时点（R-013）。
# ---------------------------------------------------------------------------
_QUOTE_CACHE: "dict[str, tuple]" = {}
_QUOTE_CACHE_TTL = float(os.environ.get("QUANTSYS_QUOTE_CACHE_TTL", "5"))


def _cache_get(symbol: str):
    entry = _QUOTE_CACHE.get(symbol)
    if entry is None:
        return None
    quote, ts = entry
    if _QUOTE_CACHE_TTL <= 0 or (time.monotonic() - ts) > _QUOTE_CACHE_TTL:
        _QUOTE_CACHE.pop(symbol, None)
        return None
    return quote


def _cache_put(symbol: str, quote) -> None:
    if _QUOTE_CACHE_TTL > 0:
        _QUOTE_CACHE[symbol] = (quote, time.monotonic())


def quote_cache_stats() -> dict:
    """缓存观测口径（供健康检查/测试断言）"""
    now = time.monotonic()
    fresh = sum(1 for _, (_, ts) in _QUOTE_CACHE.items() if (now - ts) <= _QUOTE_CACHE_TTL)
    return {'size': len(_QUOTE_CACHE), 'fresh': fresh, 'ttl_seconds': _QUOTE_CACHE_TTL}


def clear_quote_cache() -> None:
    _QUOTE_CACHE.clear()


class RealtimeQuoteService:
    """实时行情服务

    委托给 DataProviderManager，保持向后兼容的API。

    Attributes:
        provider_manager: 统一的数据提供者管理器
    """

    def __init__(self):
        """初始化服务"""
        # 延迟导入避免顶层依赖
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider_manager = get_data_provider_manager()
        logger.info("RealtimeQuoteService initialized (using DataProviderManager)")

    def get_realtime_quote(self, symbol: str) -> Optional[QuoteData]:
        """获取实时行情

        依次尝试各个数据源，返回第一个成功的结果。

        Args:
            symbol: 股票代码

        Returns:
            QuoteData 或 None（所有数据源都失败时）
        """
        logger.info(f"Fetching quote for {symbol}")

        result = self.provider_manager.get_quote(symbol)

        if result['success']:
            quote_data = result['data']
            logger.info(
                f"Successfully fetched quote for {symbol} from {quote_data.source} "
                f"(price={quote_data.price})"
            )
            return quote_data

        logger.warning(f"Failed to fetch quote for {symbol}: {result.get('error')}")
        return None

    def get_realtime_quotes(self, symbols) -> dict:
        """批量实时行情（2026-09-13，w-adb088f2）

        一次 provider 调用取回多只，返回 {symbol: QuoteData}；整批失败返回 {}（不透传异常，
        与 get_realtime_quote 返回 None 的既有约定一致）。缺口由调用方按 len(prices) 判定。
        """
        wanted = list(dict.fromkeys(symbols or []))
        if not wanted:
            return {}

        # 1) 先吃缓存：只把**未命中**的标的送去 provider（部分批量，不整批重取）
        out = {}
        for symbol in wanted:
            cached = _cache_get(symbol)
            if cached is not None:
                out[symbol] = cached
        pending = [s for s in wanted if s not in out]

        if not pending:
            logger.debug(f"Batch quotes all cache-hit: {len(wanted)} symbols")
            return out

        logger.info(f"Fetching batch quotes: {len(pending)}/{len(wanted)} symbols (缓存命中 {len(out)})")
        result = self.provider_manager.get_quotes(pending)
        if result.get('success'):
            fetched = dict(result.get('data') or {})
            for symbol, quote in fetched.items():
                _cache_put(symbol, quote)
            out.update(fetched)
            gap = result.get('missing_symbols') or []
            if gap:
                logger.warning(f"Batch quote partial: missing {gap}")
            return out
        logger.warning(f"Failed to fetch batch quotes: {result.get('error')}")
        return out

    def get_provider_health(self):
        """获取数据源健康状态

        Returns:
            Dict[str, Dict[str, int]]: 各数据源的统计信息
        """
        return self.provider_manager.get_provider_health()
