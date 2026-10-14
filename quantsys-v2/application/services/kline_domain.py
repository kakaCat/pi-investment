"""K 线检查域分域（可交易域 / 观察中 / 存量）—— REQ-261006163444-8e4f

背景（为什么需要它）
--------------------
数据质量告警此前把 ``quant.daily_klines`` 里的**全部** distinct symbol 当成检查域，
于是 400 只早已退市/长停的标的每天都在拉低平均覆盖率与评分、并永久占据 D 级配额
（实测：可交易域 5280 只覆盖 98.54% / 评分 90.84，全库口径被拉到 91.70% / 86.28）。
本模块把"谁还在交易"这件事变成一个**可复算的数据事实**：

    gap = 该标的最后一个有 K 线的交易日，到全市场最后交易日之间隔了几个交易日
          （交易日按倒序排名，最后交易日名次为 1 ⇒ gap = 名次 - 1）

    gap == 0        → 可交易域 tradable （最后交易日当天有 K 线）
    1 <= gap <= 4   → 观察中 observing  （新掉出，逐日进告警正文）
    gap >= 5        → 存量 stock        （退市/长停，只报数不点名）

为什么不用 ``is_delisted`` / ``is_suspended`` 标记
--------------------------------------------------
实测（2026-10-06）这两个标记只覆盖死标的的 46%（161/351），另有 190 只窗口内 0 数据却
**没有任何标记**，55 只停更标的也全部未标 —— 标记不足以定义域。因此判据取"最后交易日
有无 K 线"这一零污染的数据事实（D-3）。

设计约束
--------
- **纯函数**：本模块不 import 任何 DB / 仓储实现，数据由调用方（``build_domain_snapshot``
  的 ``kline_repo`` 参数）注入 ⇒ 可脱离数据库单测（规范 kb-conventions-c01「层边界只许向内」）。
- **不抛异常**：退化（无交易日 / 无标的 / 查询失败）一律收敛成 ``degraded=True`` + ``degrade_reason``，
  由调用方响亮处理，不得静默跳过（FR-1/FR-3）。
- **零新增状态**：不落库、不缓存；"上期在域"就是最后一个交易日的集合，现算即得。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "TRADABLE_MAX_GAP",
    "STOCK_MIN_GAP",
    "UNKNOWN_GAP",
    "DomainSnapshot",
    "classify_domain",
    "build_domain_snapshot",
]

# ── 分域常量（唯一一处定义，别在调用方另抄一套）────────────────────────
TRADABLE_MAX_GAP = 0   # gap == 0 ⇒ 可交易域
STOCK_MIN_GAP = 5      # gap >= 5 ⇒ 存量；1..4 ⇒ 观察中
UNKNOWN_GAP = 9999     # 标的最后交易日不在交易日集合内（脏数据）时的哨兵


@dataclass(frozen=True)
class DomainSnapshot:
    """一次分域快照（不可变）。

    Attributes:
        last_trade_date: 全市场最后交易日 'YYYY-MM-DD'；无数据时 None
        prev_trade_date: 倒数第二个交易日；不足两个交易日时 None
        gap_days: symbol -> 连续无数据交易日数（0 = 最后交易日有 K 线）
        tradable: gap == 0 的标的
        observing: 1 <= gap <= 4 的标的
        stock: gap >= 5 的标的（含 UNKNOWN_GAP）
        dropped_new: gap == 1 的标的（上一交易日在域、本交易日不在）
        dropped_known: prev_trade_date 可得 ⇒ 掉出可判；否则调用方不得把 dropped_new 当结论
        degraded: 快照不可用（无交易日 / 无标的 / 查询失败）
        degrade_reason: 退化原因摘要（degraded=True 时非空）
    """

    last_trade_date: Optional[str]
    prev_trade_date: Optional[str]
    gap_days: Mapping[str, int]
    tradable: frozenset
    observing: frozenset
    stock: frozenset
    dropped_new: frozenset
    dropped_known: bool
    degraded: bool = False
    degrade_reason: Optional[str] = None

    @property
    def total(self) -> int:
        """参与分域的标的数（三层之和）。"""
        return len(self.gap_days)

    @property
    def dropped_count(self) -> int:
        """本期掉出可交易域的标的数。"""
        return len(self.dropped_new)


def _as_day(value: Any) -> str:
    """把 date / datetime / 字符串统一成 'YYYY-MM-DD'；无法解析时原样 str 截断。"""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _degenerate(reason: str) -> DomainSnapshot:
    """构造退化快照（所有集合为空）。"""
    return DomainSnapshot(
        last_trade_date=None,
        prev_trade_date=None,
        gap_days={},
        tradable=frozenset(),
        observing=frozenset(),
        stock=frozenset(),
        dropped_new=frozenset(),
        dropped_known=False,
        degraded=True,
        degrade_reason=reason,
    )


def classify_domain(
    trade_dates_desc: Sequence[Any],
    symbol_last_dates: Iterable[Tuple[str, Any]],
) -> DomainSnapshot:
    """把"交易日序列 + 每标的最后交易日"分成三层（纯函数，无 I/O）。

    Args:
        trade_dates_desc: 全市场交易日，**倒序**（[0] = 最后交易日 D_last）；允许 date/datetime/str
        symbol_last_dates: (symbol, 该标的最后有 K 线的交易日) 可迭代；同 symbol 重复时取最新

    Returns:
        DomainSnapshot。退化输入返回 ``degraded=True`` 的快照，**不抛异常**。
    """
    dates = []
    seen = set()
    for raw in trade_dates_desc or ():
        day = _as_day(raw)
        if day and day not in seen:
            seen.add(day)
            dates.append(day)

    if not dates:
        return _degenerate("no_trade_dates")

    # 交易日倒序名次：D_last = 1 ⇒ gap = 名次 - 1
    rank = {day: idx + 1 for idx, day in enumerate(dates)}
    last_trade_date = dates[0]
    prev_trade_date = dates[1] if len(dates) > 1 else None

    gap_days: dict = {}
    unknown: list = []
    for item in symbol_last_dates or ():
        try:
            symbol, raw_day = item
        except (TypeError, ValueError):
            continue
        symbol = str(symbol).strip()
        if not symbol:
            continue
        day = _as_day(raw_day)
        r = rank.get(day)
        gap = (r - 1) if r is not None else UNKNOWN_GAP
        # 同 symbol 重复：取最小 gap（即最新的一条），保证幂等且不接受"更旧"覆盖"更新"
        if symbol not in gap_days or gap < gap_days[symbol]:
            gap_days[symbol] = gap
        if gap == UNKNOWN_GAP:
            unknown.append(symbol)

    if unknown:
        logger.warning(
            "分域：%d 只标的的最后交易日不在交易日集合内（按存量处理）: %s",
            len(unknown), ", ".join(sorted(unknown)[:20]),
        )

    tradable = frozenset(s for s, g in gap_days.items() if g <= TRADABLE_MAX_GAP)
    observing = frozenset(s for s, g in gap_days.items() if TRADABLE_MAX_GAP < g < STOCK_MIN_GAP)
    stock = frozenset(s for s, g in gap_days.items() if g >= STOCK_MIN_GAP)
    dropped_new = frozenset(s for s, g in gap_days.items() if g == 1)

    if not gap_days:
        return _degenerate("no_symbols")

    return DomainSnapshot(
        last_trade_date=last_trade_date,
        prev_trade_date=prev_trade_date,
        gap_days=gap_days,
        tradable=tradable,
        observing=observing,
        stock=stock,
        dropped_new=dropped_new,
        dropped_known=prev_trade_date is not None,
        degraded=False,
        degrade_reason=None,
    )


def build_domain_snapshot(kline_repo: Any) -> DomainSnapshot:
    """编排：向仓储要两个只读事实 → ``classify_domain``。查询失败 ⇒ 退化快照（不抛）。

    ⚠️ **交易日要取够 STOCK_MIN_GAP 个**（不是 2 个）：``classify_domain`` 用交易日倒序名次
    算 gap，若只取最后 2 个，则"隔了 2~4 个交易日"的标的名次查不到 ⇒ 被当成 ``UNKNOWN_GAP``
    静默丢进存量（实测：只取 2 个时观察中假报 2 只、存量假报 404 只；取 5 个才是 3 / 403）。
    取 ``STOCK_MIN_GAP`` 个已足够：更老的标的名次缺失 ⇒ gap >= 5 ⇒ 本来就该落存量。

    Args:
        kline_repo: 需实现 ``list_recent_trade_dates(limit)`` 与 ``list_symbol_last_trade_date()``
            （见 ``KlineORMRepository``；daily_klines 的数据访问归它）
    """
    try:
        dates = list(kline_repo.list_recent_trade_dates(max(2, STOCK_MIN_GAP)) or [])
        rows = list(kline_repo.list_symbol_last_trade_date() or [])
    except Exception as exc:  # 退化要响亮：由调用方转成 error 告警
        reason = f"{type(exc).__name__}: {exc}"[:200]
        logger.error("建分域快照失败: %s", reason)
        return _degenerate(reason)
    return classify_domain(dates, rows)
