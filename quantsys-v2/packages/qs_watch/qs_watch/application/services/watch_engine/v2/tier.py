"""档位计算 —— 纯函数，无 I/O、无时钟、无数据库（REQ-261022235419-2299）

档位含义：这条规则多久被查一次（watch_rules.watch_tier，单位秒）。

    TIER_FAST  = 30   贴近触发线 → 每 30 秒
    TIER_MID   = 600  中等距离   → 每 10 分钟
    TIER_SLOW  = 1800 远离触发线 → 每 30 分钟

距离口径（用户裁定）：上一次查到的价格与规则触发价的百分比距离

    distance = |price − trigger_price| / trigger_price × 100

    ≤ NEAR_PCT(1%) → 30
    ≤ MID_PCT(3%)  → 600
    > MID_PCT      → 1800

触发价按条件类型价格化（不做指标空间的近似）：
    price_break   → params.price
    staged_break  → params.touch.price（触及线）
    pnl_pct       → cost_price × (1 + pct/100)
    pct_change    → prev_close × (1 + pct/100)
    combined      → 递归子条件
其它类型（rsi / fund_flow / volume_surge / velocity / ma_break）**不可价格化**，
返回空列表——调用方据此保持原档位不动（不猜）。

一条规则有多条价格线时取**最近**的一条（最容易先触发的那条决定紧迫度）。
"""
from typing import Any, Dict, Iterable, List, Optional

#: 三个档位（秒）
TIER_FAST = 30
TIER_MID = 600
TIER_SLOW = 1800

VALID_TIERS = (TIER_FAST, TIER_MID, TIER_SLOW)

#: 新规则默认档位：开盘任务/档位任务首次扫到就会重算，默认给最快档保证不漏第一拍
DEFAULT_TIER = TIER_FAST

#: 档位阈值（%）
NEAR_PCT = 1.0
MID_PCT = 3.0


def _iter_conditions(conditions: Any) -> Iterable[Dict[str, Any]]:
    """展开条件列表（combined 递归展开），只产出 dict 条件。"""
    if isinstance(conditions, dict):
        conditions = [conditions]
    for cond in conditions or []:
        if not isinstance(cond, dict):
            continue
        yield cond
        if cond.get('type') == 'combined':
            params = cond.get('params') or {}
            yield from _iter_conditions(params.get('conditions'))


def _to_float(value: Any) -> Optional[float]:
    """转正数（价格线必须是正数）；非法/非正 → None。"""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _num(value: Any) -> Optional[float]:
    """转任意数字（pct 可为负，如 -5.0 = 跌 5%）；非法 → None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def trigger_prices(rule: Any, prev_close: Optional[float] = None) -> List[float]:
    """规则的全部价格线（去重、升序、仅正数）；不可价格化时返回空列表。

    prev_close 仅 pct_change 需要（quote.prev_close）；没有就不产出该价格线。
    """
    prices: List[float] = []
    cost_price = _to_float(getattr(rule, 'cost_price', None))
    prev = _to_float(prev_close)

    for cond in _iter_conditions(getattr(rule, 'conditions', None)):
        ctype = cond.get('type')
        params = cond.get('params') or {}
        price: Optional[float] = None
        if ctype == 'price_break':
            price = _to_float(params.get('price'))
        elif ctype == 'staged_break':
            touch = params.get('touch') or {}
            price = _to_float(touch.get('price'))
        elif ctype == 'pnl_pct':
            pct = _num(params.get('pct'))
            if cost_price is not None and pct is not None:
                price = cost_price * (1 + pct / 100.0)
        elif ctype == 'pct_change':
            pct = _num(params.get('pct'))
            if prev is not None and pct is not None:
                price = prev * (1 + pct / 100.0)
        if price is not None and price > 0:
            prices.append(price)

    return sorted(set(prices))


def distance_pct(price: Any, trigger_price: Any) -> Optional[float]:
    """|price − trigger_price| / trigger_price × 100；任一非法返回 None。"""
    p = _to_float(price)
    t = _to_float(trigger_price)
    if p is None or t is None:
        return None
    return abs(p - t) / t * 100.0


def tier_of(distance: Optional[float]) -> Optional[int]:
    """距离（%）→ 档位（秒）；None 表示无法评估，调用方保持原档位。"""
    if distance is None:
        return None
    if distance <= NEAR_PCT:
        return TIER_FAST
    if distance <= MID_PCT:
        return TIER_MID
    return TIER_SLOW


def tier_for(rule: Any, price: Any, prev_close: Optional[float] = None) -> Optional[int]:
    """一条规则在给定价格下的档位；不可价格化/无价格 → None。"""
    prices = trigger_prices(rule, prev_close=prev_close)
    if not prices:
        return None
    distances = [d for d in (distance_pct(price, p) for p in prices) if d is not None]
    if not distances:
        return None
    return tier_of(min(distances))


def normalize_tier(value: Any) -> Optional[int]:
    """读口径归一：只有 30/600/1800 认，其余（NULL/脏值）→ None（保持原档位）。"""
    try:
        tier = int(value)
    except (TypeError, ValueError):
        return None
    return tier if tier in VALID_TIERS else None
