"""市场级规则判定器（REQ-f08def P6，RFC 014 v3 §1.1/§8，2026-09-11，w-c8cae280）

纯领域服务：把"市场级条件"（指数关键位/涨跌幅、涨停家数、情绪分、量能比、板块强度）
对一份 MarketState 快照求值。不做任何 I/O，取数由 IMarketStateProvider 端口负责。

为什么需要：此前 WatchEngine 只能盯个股（quote_service.get_realtime_quote(rule.symbol)），
指数/板块/情绪这类"市场级"对象根本进不来——而用户对盯盘的定位是"紧盯市场情况的工具"。
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

from domain.watch.models import MarketState


@dataclass(frozen=True)
class MarketEvalResult:
    triggered: bool
    value: Optional[float] = None
    message: str = ""
    skipped: bool = False          # 数据缺失 → 跳过（不算触发，也不算健康）


# 支持的 condition.type（市场级）
MARKET_CONDITION_TYPES = (
    "index_break",     # 指数关键位：target=指数代码, params={price, direction}
    "index_pct",       # 指数涨跌幅：target=指数代码, params={pct, direction}
    "limit_up_count",  # 涨停家数：params={count, direction}
    "sentiment",       # 情绪分/恐慌贪婪：params={score, direction, field?}
    "ad_ratio",        # 涨跌家数比：params={ratio, direction}
    "volume_ratio",    # 量能比：params={ratio, direction}
    "sector_pct",      # 板块强度：target=板块名, params={pct, direction}
)


class MarketRuleEvaluator:

    def evaluate(self, condition: Dict[str, Any], state: MarketState) -> MarketEvalResult:
        ctype = (condition or {}).get("type")
        params = (condition or {}).get("params") or {}
        target = (condition or {}).get("target") or params.get("target")

        if ctype == "index_break":
            code = target or params.get("symbol")
            price = state.indices.get(code, {}).get("close") if code else None
            if price is None:
                return MarketEvalResult(False, skipped=True, message="指数 %s 无数据" % code)
            return self._cmp(float(price), float(params.get("price", 0)),
                             params.get("direction"), "指数 %s" % code, fmt="%.2f")

        if ctype == "index_pct":
            code = target or params.get("symbol")
            pct = state.index_change_pct(code) if code else None
            if pct is None:
                return MarketEvalResult(False, skipped=True, message="指数 %s 无涨跌幅" % code)
            return self._cmp(pct, float(params.get("pct", 0)), params.get("direction"),
                             "指数 %s 涨跌幅" % code, suffix="%")

        if ctype == "limit_up_count":
            if state.limit_up_count is None:
                return MarketEvalResult(False, skipped=True, message="涨停家数无数据")
            return self._cmp(float(state.limit_up_count), float(params.get("count", 0)),
                             params.get("direction"), "涨停家数", fmt="%d")

        if ctype == "sentiment":
            field_name = params.get("field") or "score"
            val = state.fear_greed_index if field_name == "fear_greed" else state.sentiment_score
            if val is None:
                return MarketEvalResult(False, skipped=True, message="情绪分无数据")
            return self._cmp(float(val), float(params.get("score", 50)), params.get("direction"),
                             "情绪分(%s)" % field_name, fmt="%.1f")

        if ctype == "ad_ratio":
            if state.advance_decline_ratio is None:
                return MarketEvalResult(False, skipped=True, message="涨跌家数比无数据")
            return self._cmp(float(state.advance_decline_ratio), float(params.get("ratio", 1.0)),
                             params.get("direction"), "涨跌家数比", fmt="%.2f")

        if ctype == "volume_ratio":
            if state.volume_ratio is None:
                return MarketEvalResult(False, skipped=True, message="量能比无数据")
            return self._cmp(float(state.volume_ratio), float(params.get("ratio", 1.0)),
                             params.get("direction"), "量能比", fmt="%.2f")

        if ctype == "sector_pct":
            name = target or params.get("sector")
            pct = state.sectors.get(name) if name else None
            if pct is None:
                return MarketEvalResult(False, skipped=True, message="板块 %s 无数据" % name)
            return self._cmp(float(pct), float(params.get("pct", 0)), params.get("direction"),
                             "板块 %s 涨跌幅" % name, suffix="%")

        return MarketEvalResult(False, skipped=True, message="不支持的市场级条件类型: %s" % ctype)

    @staticmethod
    def _cmp(value: float, threshold: float, direction: Optional[str], label: str,
             fmt: str = "%.2f", suffix: str = "") -> MarketEvalResult:
        d = (direction or "below").lower()
        if d == "above":
            hit = value > threshold
            op = ">"
        else:
            hit = value < threshold
            op = "<"
        msg = "%s %s %s %s %s%s（阈值）" % (label, (fmt % value), op, (fmt % threshold),
                                            "", suffix)
        return MarketEvalResult(hit, value=value, message=msg)
