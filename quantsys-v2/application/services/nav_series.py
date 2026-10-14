"""净值序列的交易日口径（唯一实现）— REQ-261006190953-fc43

## 为什么需要它
净值序列（`quant.simulation_equity_snapshot`）此前按「行相邻」直接配对成日收益，
库里一旦出现落在周末/节假日的行（实测 35 行：08-08/08-15/08-29/09-05/09-06/09-12/10-02），
这些行就被当成交易日参与波动率、IR、回撤与归因窗口；缺口判断更是在消费侧用
「工作日」近似（按 JS 的 UTC 星期几取模），把国庆整段算成缺口、逼出无意义的补跑。

本模块把「哪些日期算数」收成**一处**实现：交易日历说了算。三条口径锁：

1. **不可得 ≠ 空集**：日历读失败/空表一律返回 `None`，调用方按"未校验"处理。
   用空集表达失败会把整个净值序列过滤成空、让指标静默退化——这是最危险的退化方式。
2. **未校验就不过滤**：`trading_days is None` 时 `filter_trading_days` **原样返回**，
   行为退回改造前，并在 `nav_coverage.verified=False` 里响亮声明。
3. **缺口只在交易日上算**：区间内"应有而缺失的交易日"才是缺口；周末与法定节假日不计入。

**本模块是纯口径模块，不做任何 IO**：交易日集合一律**由调用方注入**
（`adapters/outbound/repositories/trading_calendar_repository.trading_day_set()` 读表，
inbound 路由与同层仓储按各自被允许的方向取用）。这样本模块不会产生
`application → adapters` 的方向倒置（见 `tests/test_layer_purity.py` 的棘轮）。

判据与来源常量一律复用 `application.services.trading_day_guard`，不另立第二套。
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    'filter_trading_days',
    'nav_returns_from_snapshots',
    'nav_coverage',
]


def _as_date(value: Any) -> Optional[date]:
    """把 date / datetime / 'YYYY-MM-DD...' 归一成 date；认不出返回 None。"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _row_date(row: Any) -> Optional[date]:
    """取一行净值快照的日期：支持 ORM 对象与 dict（含 date 键别名）。"""
    if isinstance(row, dict):
        value = row.get('snapshot_date', row.get('date'))
    else:
        value = getattr(row, 'snapshot_date', None)
    return _as_date(value)


def _row_total(row: Any) -> Optional[float]:
    """取一行净值快照的总资产；缺失返回 None。"""
    if isinstance(row, dict):
        value = row.get('total_value')
    else:
        value = getattr(row, 'total_value', None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def filter_trading_days(
    rows: Sequence[Any],
    trading_days: Optional[Set[date]] = None,
    *,
    date_of: Callable[[Any], Optional[date]] = _row_date,
) -> List[Any]:
    """过滤掉不在交易日集合里的行。

    `trading_days is None`（日历不可得/未校验）→ **原样返回**（不静默清空）；
    认不出日期的行：视为**不可判定**，保留（宁可多留一行，也不把数据吃掉）。
    """
    if trading_days is None:
        return list(rows)
    kept: List[Any] = []
    for row in rows:
        day = date_of(row)
        if day is None or day in trading_days:
            kept.append(row)
    return kept


def nav_returns_from_snapshots(
    snapshots: Sequence[Any],
    trading_days: Optional[Set[date]] = None,
) -> Tuple[List[float], int]:
    """账户净值序列 → 日收益率序列。返回 `(returns, 参与计算的有效点数)`。

    口径（顺序固定）：

    1. 丢弃 total_value 缺失或 <= 0 的行（残缺估值行）；
    2. `trading_days` 非 None 时丢弃非交易日行（读取端兜底：库里残留脏行也读不到）；
    3. 按 snapshot_date 升序，相邻两点算 `v[i]/v[i-1] - 1`。

    跨节假日的涨跌因此归到「复市首日 vs 上一交易日」这一段，**不产生假日"日收益"**。
    """
    rows = [r for r in (snapshots or []) if _row_total(r) is not None and _row_total(r) > 0]
    if trading_days is not None:
        rows = filter_trading_days(rows, trading_days)
    rows = [r for r in rows if _row_date(r) is not None]
    rows.sort(key=_row_date)

    values = [_row_total(r) for r in rows]
    returns: List[float] = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        if prev and prev > 0:
            returns.append((values[i] - prev) / prev)
    return returns, len(values)


def nav_coverage(
    snapshots: Sequence[Any],
    trading_days: Optional[Set[date]] = None,
    *,
    max_listed: int = 20,
) -> Dict[str, Any]:
    """净值序列覆盖率（**缺口口径唯一实现**）。

    - `verified=False`（无日历）⇒ `missing_count == 0` 且 `basis` 明写"未做交易日校验"，
      **不是**"全缺失"；
    - 缺口 = 序列区间 `[from, to]` 内**交易日历有、序列缺**的交易日；周末与法定节假日不计入；
    - `to` 取序列最后一个**快照**日期（含非交易日行），保证"最后一行为休市日"也落在区间内。
    """
    from application.services.trading_day_guard import SOURCE_CALENDAR, SOURCE_UNAVAILABLE

    rows = [r for r in (snapshots or []) if _row_date(r) is not None]
    rows.sort(key=_row_date)
    all_dates = [_row_date(r) for r in rows]

    if trading_days is None:
        return {
            'verified': False,
            'points': len(rows),
            'from': all_dates[0].isoformat() if all_dates else None,
            'to': all_dates[-1].isoformat() if all_dates else None,
            'missing_trading_days': [],
            'missing_count': 0,
            'basis': '未做交易日校验（交易日历不可得）：缺口数按 0 上报，不据此触发补跑',
            'trading_day_source': SOURCE_UNAVAILABLE,
        }

    in_calendar = [d for d in all_dates if d in trading_days]
    if not in_calendar:
        return {
            'verified': True,
            'points': 0,
            'from': None,
            'to': None,
            'missing_trading_days': [],
            'missing_count': 0,
            'basis': '序列内没有任何一天落在交易日历上（点数为 0，须先查数据）',
            'trading_day_source': SOURCE_CALENDAR,
        }

    # 区间端点在交易日上取（缺口只在交易日上定义），但 to 不早于序列最后一行
    start, end = in_calendar[0], max(in_calendar[-1], all_dates[-1])
    present = set(all_dates)
    missing = sorted(d for d in trading_days if start <= d <= end and d not in present)

    return {
        'verified': True,
        'points': len(in_calendar),
        'from': start.isoformat(),
        'to': end.isoformat(),
        'missing_trading_days': [d.isoformat() for d in missing[:max_listed]],
        'missing_count': len(missing),
        'basis': (
            '按交易日历逐日核对（来源 calendar_table，共 %d 个交易日）：'
            '周末与法定节假日不计入缺口' % len(trading_days)
        ),
        'trading_day_source': SOURCE_CALENDAR,
    }
