"""invalidation —— 失效判定（作废范围）（REQ-261022235419-2299 / t5，FR-6）

用户裁定（D-4/D-6）：盯盘规则要能**作废** —— 价格跑远后目标过时，规则应
标记失效并交 agent 裁决（改阈值回 active / 退役归 archived）。

判定口径（architecture.md IF-3 / data-model.md）：

- 偏离 = ``|现价 − 触发价| / 触发价``；触发价取规则 conditions 里的价格线
  （price_break / staged_break 的 price）
- 偏离 > ``rule.invalidation_threshold_pct``（agent 必填）→ 失效
- **覆盖全部激活票**：不依赖持仓状态、不依赖是否触发、不依赖是否到期
- **止损豁免**：保护线被穿越是资损事实（该触发），不是失效
- 无报价 / 缺阈值 → 跳过（不误标）

本模块只做判定，返回 InvalidEvent 由调用方落库 + 投递（t6/t7）。
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional

import structlog

logger = structlog.get_logger(__name__)

#: 止损（保护线）不参与失效判定（D-6 / architecture.md ⑤）
EXEMPT_INTENTS = ('exit_stop',)

#: 价格线条件类型（取触发价用）
PRICE_LINE_TYPES = ('price_break', 'staged_break')


@dataclass
class InvalidEvent:
    """失效事件（值对象；由调用方落 rule_state=invalid + 留痕 + 投递）。"""

    rule_id: Any
    symbol: str
    trigger_price: float
    current_price: float
    deviation_pct: float
    threshold_pct: float
    reason: str
    at: Optional[datetime] = None


def _intent_of(rule) -> str:
    return str(getattr(rule, 'intent', '') or '').strip()


def _threshold_pct(rule) -> Optional[float]:
    """agent 设定的失效线（必填）；缺失/非法返回 None → 跳过判定。"""
    value = getattr(rule, 'invalidation_threshold_pct', None)
    if value is None:
        return None
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return None
    return pct if pct > 0 else None


def _trigger_prices(rule) -> List[float]:
    """规则所有价格线（用于算偏离；任一超线即判失效）。"""
    prices: List[float] = []
    for cond in (getattr(rule, 'conditions', None) or []):
        if not isinstance(cond, dict):
            continue
        if cond.get('type') not in PRICE_LINE_TYPES:
            continue
        params = cond.get('params') or {}
        raw = params.get('price')
        try:
            price = float(raw)
        except (TypeError, ValueError):
            continue
        if price > 0:
            prices.append(price)
    return prices


def check_invalidation(rule, quote, now: Optional[datetime] = None,
                       threshold_pct: Optional[float] = None) -> Optional[InvalidEvent]:
    """失效判定：偏离超 agent 失效线 → InvalidEvent；否则 None。

    参数：
        rule:          规则（读 intent / conditions / invalidation_threshold_pct）
        quote:         实时报价（需 .price；None/无价则跳过）
        now:           判定时刻（写进事件）
        threshold_pct: 显式失效线（覆盖 rule 上的值；主要便于测试/裁决回写）

    返回 InvalidEvent 或 None（None = 不失效 / 无法判定，均不落库）。
    """
    # ── 止损豁免（保护线穿越=触发，不作废）────────────────────────────
    if _intent_of(rule) in EXEMPT_INTENTS:
        return None

    threshold = threshold_pct if threshold_pct is not None else _threshold_pct(rule)
    if threshold is None:
        return None

    price = getattr(quote, 'price', None) if quote is not None else None
    try:
        current_price = float(price)
    except (TypeError, ValueError):
        return None
    if current_price <= 0:
        return None

    # ── 逐条价格线算偏离，任一超线即失效 ──────────────────────────────
    worst: Optional[InvalidEvent] = None
    for trigger_price in _trigger_prices(rule):
        deviation = abs(current_price - trigger_price) / trigger_price * 100.0
        if deviation > threshold:
            event = InvalidEvent(
                rule_id=getattr(rule, 'id', None),
                symbol=getattr(rule, 'symbol', ''),
                trigger_price=trigger_price,
                current_price=current_price,
                deviation_pct=round(deviation, 2),
                threshold_pct=threshold,
                reason=(f'价格偏离 {deviation:.2f}% 超过失效线 {threshold:.2f}%'
                        f'（触发价 {trigger_price:.2f} / 现价 {current_price:.2f}）'),
                at=now,
            )
            if worst is None or event.deviation_pct > worst.deviation_pct:
                worst = event
    return worst
