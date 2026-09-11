"""市场状态取数适配器（REQ-f08def P6，2026-09-11，w-c8cae280）

实现 domain/watch/ports.IMarketStateProvider：把指数/涨停家数/情绪/量能/板块拼成一份
MarketState 快照。按 ADR-001，所有 I/O 都收在适配器层。

诚实原则：任一数据源不可用时记入 state.degraded，**绝不用 0 冒充**——
"涨停家数=0" 会被市场规则判定成"情绪冰点"，那是用故障伪造事实。
"""
import time
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

INDEX_CODES = ("000300.SH", "000001.SH", "399006.SZ", "000852.SH")
CACHE_TTL_SEC = 60


class MarketStateProvider:

    def __init__(self, index_codes=INDEX_CODES, cache_ttl_sec: int = CACHE_TTL_SEC):
        self.index_codes = tuple(index_codes)
        self.cache_ttl_sec = cache_ttl_sec
        self._cache: Optional[tuple] = None   # (ts, MarketState)

    def get_state(self, force: bool = False):
        from domain.watch.models import MarketState
        now = time.time()
        if (not force) and self._cache and (now - self._cache[0]) < self.cache_ttl_sec:
            return self._cache[1]
        degraded = []
        indices = self._indices(degraded)
        sentiment = self._sentiment(degraded)
        limit_up = self._limit_up(degraded)
        sectors = self._sectors(degraded)
        state = MarketState(
            trade_date=datetime.now().strftime("%Y-%m-%d"),
            indices=indices,
            limit_up_count=limit_up.get("count"),
            max_streak=limit_up.get("max_streak"),
            sentiment_score=sentiment.get("score"),
            fear_greed_index=sentiment.get("fear_greed"),
            advance_decline_ratio=sentiment.get("ad_ratio"),
            volume_ratio=sentiment.get("volume_ratio"),
            sectors=sectors,
            degraded=degraded,
        )
        self._cache = (now, state)
        return state

    # ── 指数（quant.index_daily：最近两个交易日算涨跌幅）──
    def _indices(self, degraded) -> Dict[str, Dict[str, Any]]:
        from infrastructure.persistence.database.engine import get_engine
        from sqlalchemy import text
        out: Dict[str, Dict[str, Any]] = {}
        try:
            with get_engine().connect() as conn:
                for code in self.index_codes:
                    rows = conn.execute(text(
                        "SELECT trade_date, close FROM quant.index_daily "
                        "WHERE symbol = :s ORDER BY trade_date DESC LIMIT 2"
                    ), {"s": code}).fetchall()
                    if not rows:
                        continue
                    last_close = float(rows[0][1]) if rows[0][1] is not None else None
                    prev_close = float(rows[1][1]) if len(rows) > 1 and rows[1][1] is not None else None
                    chg = ((last_close - prev_close) / prev_close * 100) if (last_close and prev_close) else None
                    out[code] = {"close": last_close, "prev_close": prev_close,
                                 "change_pct": round(chg, 2) if chg is not None else None,
                                 "trade_date": str(rows[0][0])}
        except Exception as e:
            logger.warning("指数取数失败", error=str(e))
            degraded.append("index_daily")
        if not out:
            degraded.append("indices_empty")
        return out

    # ── 情绪/量能/涨跌家数（复用既有市场情绪服务）──
    def _sentiment(self, degraded) -> Dict[str, Any]:
        """情绪/量能/涨跌家数 —— 键名按 MarketSentimentService 真实返回结构，
        不按路由层的 camelCase 猜（2026-09-11 教训：猜结构必错）。"""
        try:
            from application.services.market_sentiment_service import MarketSentimentService
            d = MarketSentimentService().analyze_market_sentiment() or {}
            ind = d.get("indicators") or {}
            ad = ind.get("advance_decline")
            ad_ratio = None
            if isinstance(ad, dict):
                ad_ratio = ad.get("ratio") or ad.get("advance_decline_ratio")
            elif isinstance(ad, (int, float)):
                ad_ratio = float(ad)
            vol = ind.get("volume") or {}
            for dim in (d.get("degraded_dimensions") or []):
                degraded.append("sentiment:" + str(dim))
            return {"score": d.get("sentiment_score"),
                    "fear_greed": d.get("fear_greed_index"),
                    "ad_ratio": ad_ratio,
                    "volume_ratio": vol.get("volume_ratio")}
        except Exception as e:
            logger.warning("市场情绪取数失败", error=str(e))
            degraded.append("market_sentiment")
            return {}

    def _limit_up(self, degraded) -> Dict[str, Any]:
        """涨停家数/连板高度。provider 返回 MarketData(dataclass 带 .data) 或 dict，
        两种形态都归一（2026-09-11 实测报错 "'MarketData' object is not iterable"）。"""
        try:
            from adapters.outbound.datasources.manager import get_data_provider_manager
            res = get_data_provider_manager().get_zt_pool(datetime.now().strftime("%Y-%m-%d"))
            rows = _as_rows(res)
            if rows is None:
                raise RuntimeError("zt_pool 结果结构不可识别")
            streaks = []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                v = r.get("连板数", r.get("streak", r.get("boards")))
                try:
                    streaks.append(int(v))
                except (TypeError, ValueError):
                    continue
            return {"count": len(rows), "max_streak": max(streaks) if streaks else None}
        except Exception as e:
            logger.warning("涨停池取数失败", error=str(e))
            degraded.append("zt_pool")
            return {}

    def _sectors(self, degraded) -> Dict[str, float]:
        """板块强度（best-effort v1）：用 manager.get_sector_list()（实测无 get_sector_flow），
        键名弹性解析；解析不出就记 degraded，绝不用 0 冒充。"""
        try:
            from adapters.outbound.datasources.manager import get_data_provider_manager
            res = get_data_provider_manager().get_sector_list()
            rows = _as_rows(res)
            out: Dict[str, float] = {}
            for r in (rows or []):
                if not isinstance(r, dict):
                    continue
                name = r.get("名称") or r.get("行业") or r.get("name") or r.get("sector")
                pct = None
                for k in ("涨跌幅", "行业-涨跌幅", "change_pct", "changePct", "涨跌幅%"):
                    if r.get(k) is not None:
                        pct = r.get(k)
                        break
                if name and pct is not None:
                    try:
                        out[str(name)] = float(pct)
                    except (TypeError, ValueError):
                        continue
            if not out:
                degraded.append("sectors_unparsed")
            return out
        except Exception as e:
            logger.warning("板块取数失败", error=str(e))
            degraded.append("sector_list")
            return {}


def _as_rows(res):
    """把 provider 返回的 MarketData / dict / list / DataFrame 归一为行列表（None=结构不可识别）

    2026-09-11 实测：akshare 路径下 res.data 常是 **pandas DataFrame**（既不是 list 也不是
    dict），原来只判 list/dict → 一律"结构不可识别"，涨停池与板块永远取不到数。
    """
    if res is None:
        return None
    if isinstance(res, list):
        return res
    data = getattr(res, "data", None)
    if data is None and isinstance(res, dict):
        data = res.get("data")
        if data is None:
            return None
    return _rows_of(data)


def _rows_of(data, _depth: int = 0):
    if data is None or _depth > 3:
        return None
    if isinstance(data, list):
        return data
    # MarketData 这类包装对象：继续往里挖它的 .data
    # （实测结构：{success, data: MarketData} 而 MarketData.data = {'date':..., 'records':[...]}）
    inner = getattr(data, "data", None)
    if inner is not None and inner is not data:
        got = _rows_of(inner, _depth + 1)
        if got is not None:
            return got
    # pandas DataFrame（不 import pandas，用鸭子类型判定）
    if hasattr(data, "to_dict") and hasattr(data, "columns"):
        try:
            return data.to_dict("records")
        except Exception:
            return None
    if isinstance(data, dict):
        for key in ("items", "rows", "list", "records", "data"):
            v = data.get(key)
            if isinstance(v, list):
                return v
            if hasattr(v, "to_dict") and hasattr(v, "columns"):
                try:
                    return v.to_dict("records")
                except Exception:
                    continue
        return None
    return None
