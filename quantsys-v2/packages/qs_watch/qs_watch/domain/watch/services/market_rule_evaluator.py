"""市场级规则判定器（REQ-f08def P6，RFC 014 v3 §1.1/§8，2026-09-11，w-c8cae280）

纯领域服务：把"市场级条件"（指数关键位/涨跌幅、涨停家数、情绪分、量能比、板块强度）
对一份 MarketState 快照求值。不做任何 I/O，取数由 IMarketStateProvider 端口负责。

为什么需要：此前 WatchEngine 只能盯个股（quote_service.get_realtime_quote(rule.symbol)），
指数/板块/情绪这类"市场级"对象根本进不来——而用户对盯盘的定位是"紧盯市场情况的工具"。
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional

from qs_watch.domain.watch.models import MarketState


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
    "held_sector_pct", # 持仓板块联动（2026-10-19 P2）：params={pct, direction}
                       # 任一「有持仓的板块」越线即触发，message 列出受影响持仓
)


def validate_market_condition(cond: Dict[str, Any]) -> None:
    """市场级条件校验（纯函数；非法抛 ValueError，错误文案直接可读）。

    供 REST 规则创建/更新路径调用（application 层 conditions.validate_condition
    委托至此）——市场级类型不进个股 DSL 的 VALID_TYPES，但入出库校验不能缺位。
    """
    if not isinstance(cond, dict):
        raise ValueError('条件必须为对象')
    ctype = cond.get('type')
    if ctype not in MARKET_CONDITION_TYPES:
        raise ValueError(f'未知市场级条件类型: {ctype}，支持: {list(MARKET_CONDITION_TYPES)}')
    params = cond.get('params') or {}
    target = cond.get('target') or params.get('target')

    def _need_direction():
        if params.get('direction') not in ('above', 'below'):
            raise ValueError(f'{ctype} 需要 params.direction: above|below')

    if ctype == 'index_break':
        if not target and not params.get('symbol'):
            raise ValueError('index_break 需要 target（指数代码）')
        if not params.get('price') or float(params['price']) <= 0:
            raise ValueError('index_break 需要 params.price > 0')
        _need_direction()
    elif ctype == 'index_pct':
        if not target and not params.get('symbol'):
            raise ValueError('index_pct 需要 target（指数代码）')
        if 'pct' not in params:
            raise ValueError('index_pct 需要 params.pct')
        _need_direction()
    elif ctype == 'limit_up_count':
        if 'count' not in params or int(params['count']) < 0:
            raise ValueError('limit_up_count 需要 params.count >= 0')
        _need_direction()
    elif ctype == 'sentiment':
        if 'score' not in params:
            raise ValueError('sentiment 需要 params.score')
        if params.get('field') not in (None, 'score', 'fear_greed'):
            raise ValueError('sentiment 的 field 只支持 score|fear_greed')
        _need_direction()
    elif ctype in ('ad_ratio', 'volume_ratio'):
        if 'ratio' not in params or float(params['ratio']) <= 0:
            raise ValueError(f'{ctype} 需要 params.ratio > 0')
        _need_direction()
    elif ctype == 'sector_pct':
        if not target and not params.get('sector'):
            raise ValueError('sector_pct 需要 target（板块名）')
        if 'pct' not in params:
            raise ValueError('sector_pct 需要 params.pct')
        _need_direction()
    elif ctype == 'held_sector_pct':
        if 'pct' not in params:
            raise ValueError('held_sector_pct 需要 params.pct（如 -2.0）')
        _need_direction()


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

        if ctype == "held_sector_pct":
            # 持仓板块联动（P2）：任一「有持仓的板块」越线即触发。
            # state.held_boards 为空 = 映射未构建/无持仓 → skipped（诚实标注，不判死不误判）。
            boards = state.held_boards or {}
            if not boards:
                return MarketEvalResult(False, skipped=True,
                                        message="持仓板块映射为空（未构建或无持仓）")
            pct_th = float(params.get("pct", -2.0))
            direction = (params.get("direction") or "below").lower()
            hits = []
            for board, holdings in boards.items():
                pct = state.sectors.get(board)
                if pct is None:
                    continue
                pct = float(pct)
                if (pct <= pct_th) if direction == "below" else (pct >= pct_th):
                    hits.append((board, pct, holdings))
            if not hits:
                return MarketEvalResult(False, value=None,
                                        message="持仓板块均未越线（阈值 %s %+.1f%%）"
                                                % (direction, pct_th))
            hits.sort(key=lambda x: x[1], reverse=(direction != "below"))
            parts = []
            for board, pct, holdings in hits[:5]:
                holds = "、".join("%s %s股@%s" % (h.get("symbol"), h.get("shares"),
                                                  h.get("account")) for h in holdings)
                parts.append("%s %+.1f%%（%s）" % (board, pct, holds))
            return MarketEvalResult(
                True, value=hits[0][1],
                message="持仓板块联动告警：" + "；".join(parts)
                        + (" 等%d个板块" % len(hits) if len(hits) > 5 else "")
                        + "——板块集体走弱，请评估关联持仓是否调整")

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
