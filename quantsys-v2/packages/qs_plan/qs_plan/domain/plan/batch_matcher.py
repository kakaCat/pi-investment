"""减仓批次匹配（REQ-261022022657-857f FR-2 · 纯函数）

口径：按 `at_pct` 升序累计 `sell_ratio`，返回累计比例 ≤ 已卖出比例的批次下标。
为什么按累计比例而不按笔数：部分成交与合单成交下笔数不可靠（设计 open-question 已决）。
"""
from typing import Any, Dict, Iterable, List

_EPS = 1e-9


def match_reduce_batches(batches: Iterable[Dict[str, Any]], sold_ratio: float) -> List[int]:
    """返回应退役的批次下标（原始列表下标，非排序后下标）。

    sold_ratio=0 → []；≥1 → 全部；越界抛 ValueError；空批 → []。
    单批 `sell_ratio` 缺失/非数按 0 处理（不臆造比例）。
    """
    if sold_ratio is None:
        raise ValueError('sold_ratio 不能为 None')
    try:
        ratio = float(sold_ratio)
    except (TypeError, ValueError) as exc:
        raise ValueError('sold_ratio 必须是数字') from exc
    if ratio < 0 or ratio > 1:
        raise ValueError('sold_ratio 必须在 [0, 1] 内：%r' % (sold_ratio,))

    indexed = list(enumerate(batches or []))
    indexed.sort(key=lambda kv: float(kv[1].get('at_pct') or 0))
    out: List[int] = []
    cum = 0.0
    for idx, batch in indexed:
        cum += float(batch.get('sell_ratio') or 0)
        if cum <= ratio + _EPS:
            out.append(idx)
        else:
            break
    return out
