"""应有交易日解析器 —— 「最近一个已收盘的交易日」与「某天是不是交易日」的唯一实现。

REQ-261004102115-d3de · FR-1（`last_closed_trading_day`）；
REQ-261004154902-a7cd · FR-3（`resolve_trading_day` 姊妹函数：判定指定某一天）。

## 为什么需要它

2026-10-04 的外部探针在数据完好的情况下报了「K 线滞后 2 天」：它把 **2026-10-02（国庆休市）**
当成了应有交易日。根因不是探针本身，而是它复用的 `daily_jobs/pipeline.py:_last_trading_day`
**只排周末、不排节假日**（该函数 docstring 原文：「周末排除法；节假日由告警人工复核」）。

本模块把"哪天该有数据"收成**一个**口径，探针与进程内 freshness_guard 都调它。

## 语义（唯一口径）

```
anchor = ref 时刻 >= 15:30 ? ref.date() : ref.date() - 1 天
结果   = 交易日历中 <= anchor 的最大交易日
```

周末与节假日由日历天然排除，不再需要"周末回退"的显式循环；
盘中（未收盘）不认今天，也由 anchor 表达，无需额外分支。

## 解析链（逐级降级；除入参类型外一律不抛异常）

1. `quant.trading_calendar` 表 —— 离线、快；**需 `max(trade_date) >= anchor` 才算"能回答"**
   （表不覆盖 anchor 时它无从判断 10-01/10-02 是不是交易日）；
2. `DataProviderManager.get_trading_calendar()`（AKShare 官方日历，含未来交易日）；
3. 周一~周五回退 —— 等于修复前的行为，但 `degraded=True` **明确标注**。

降级必须一路带到调用方（探针进 JSON 与告警正文）：国庆期间若日历源全挂，
宁可让读告警的人看见「按工作日口径判定」，也不要静默地重新开始误报。

## 姊妹函数 `resolve_trading_day(day)`（FR-3）

`TradingDayGuard`（「今天是不是交易日」）此前走「近 7 日有 K 线」启发式，长假期间会把
2026-10-05/06/07 判成交易日、把复市首日 2026-10-08 判成休市。修法是**复用本模块同一条取数链**，
只换语义：问「指定某一天」而不是「最近一个已收盘的交易日」。

判据（唯一）：**`result.date == 传入的 day` ⟺ 该日是交易日**。

- 表覆盖该日（`max(trade_date) >= day`）→ 表答 `<= day` 的最大交易日；等于 day 即交易日，
  小于 day 即休市（表只存交易日，无 `is_trading_day=false` 行）；
- 表不覆盖 → provider；provider 也答不了 → 周一~周五回退 + `degraded=True`（工作日回退会把
  法定节假日当作交易日，必须由调用方标注，**不许静默**）。

## 测试注入

单元测试通过 monkeypatch `_read_calendar_table` / `_read_provider` 注入假日历，零网络零 DB。
"""
from __future__ import annotations

import structlog
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from typing import Any, Optional, Union

logger = structlog.get_logger(__name__)

#: 判定来源（对外契约，探针与 freshness_guard 的 result 都会带出去）
SOURCE_CALENDAR_TABLE = "calendar_table"
SOURCE_PROVIDER = "provider"
SOURCE_WEEKDAY_FALLBACK = "weekday_fallback"

#: 收盘基准：与修复前 `_last_trading_day` 的 15:30 保持逐字一致
DEFAULT_CUTOFF = dtime(15, 30)

#: provider 查询窗口（覆盖春节最长休市 + 周末）
DEFAULT_PROVIDER_LOOKBACK_DAYS = 30

_CALENDAR_TABLE = "quant.trading_calendar"


@dataclass(frozen=True)
class TradingDayResult:
    """一次解析的结果。

    - `date`：最近一个已收盘的交易日
    - `source`：`calendar_table` | `provider` | `weekday_fallback`
    - `degraded`：是否走了周一~周五回退（True 时判定可信度更低，必须对外标注）
    """

    date: date
    source: str
    degraded: bool


def _as_date(value: Any) -> Optional[date]:
    """把 DB/provider 返回的日期值归一成 `date`；无法识别返回 None（不抛）。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _anchor(ref: datetime, cutoff: dtime) -> date:
    """未到收盘基准就看前一自然日；到了就认今天（周末/节假日由日历排除）。"""
    today = ref.date()
    return today if ref.time() >= cutoff else today - timedelta(days=1)


def _read_calendar_table(anchor: date) -> Optional[date]:
    """① `quant.trading_calendar`。表不覆盖 anchor 或不可读 → None（降级）。

    口径与 `tools/check_data_contracts.py:compute_expected_trading_day` 一致
    （`is_trading_day IS NOT FALSE`：NULL 视为交易日）；不按 exchange 过滤——
    `max()` 不受 SSE/SZSE/ALL 三份重复影响。
    """
    from sqlalchemy import text

    from infrastructure.persistence.database.engine import get_engine

    with get_engine().connect() as conn:
        coverage = _as_date(conn.execute(text(f"SELECT max(trade_date) FROM {_CALENDAR_TABLE}")).scalar())
        if coverage is None or coverage < anchor:
            logger.warning(
                "trading_calendar_not_covering",
                anchor=str(anchor),
                calendar_max=str(coverage),
            )
            return None
        last = conn.execute(
            text(
                f"SELECT max(trade_date) FROM {_CALENDAR_TABLE} "
                "WHERE trade_date <= :anchor AND is_trading_day IS NOT FALSE"
            ),
            {"anchor": anchor},
        ).scalar()
    return _as_date(last)


def _row_date(row: Any) -> Any:
    if isinstance(row, dict):
        return row.get("trade_date")
    return row


def _read_provider(anchor: date, lookback_days: int) -> Optional[date]:
    """② AKShare 官方交易日历（经既有 DataProviderManager 入口，不直连外部库）。"""
    from infrastructure.services.service_factory import ServiceFactory

    start = anchor - timedelta(days=lookback_days)
    manager = ServiceFactory.get_data_provider_manager()
    result: Any = manager.get_trading_calendar(start.isoformat(), anchor.isoformat())
    if not isinstance(result, dict) or not result.get("success"):
        logger.warning("trading_calendar_provider_failed", anchor=str(anchor), result=str(result)[:200])
        return None

    rows = result.get("data")
    rows = getattr(rows, "data", rows)
    days = {d for d in (_as_date(_row_date(r)) for r in (rows or [])) if d is not None and d <= anchor}
    if not days:
        logger.warning("trading_calendar_provider_empty", anchor=str(anchor))
        return None
    return max(days)


def _weekday_fallback(anchor: date) -> date:
    """③ 周一~周五回退 = 修复前的行为（唯一区别是现在会被标注为降级）。"""
    cursor = anchor
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor


def _resolve_chain(anchor: date, provider_lookback_days: int) -> TradingDayResult:
    """解析链本体（唯一实现）：表 → provider → 周一~周五回退（degraded）。

    返回的 `TradingDayResult.date` 语义 = **`<= anchor` 的最大交易日**；
    两个公开入口的差别只在 anchor 怎么来（`last_closed_trading_day` 由 `ref` + cutoff 推，
    `resolve_trading_day` 直接用传入的那一天）。

    除入参类型外一律不抛：每一级失败都降级，而不是把调用方（探针 / 调度 tick）带崩。
    """
    for source, reader in (
        (SOURCE_CALENDAR_TABLE, lambda: _read_calendar_table(anchor)),
        (SOURCE_PROVIDER, lambda: _read_provider(anchor, provider_lookback_days)),
    ):
        try:
            resolved = reader()
        except Exception as exc:  # noqa: BLE001 —— 任一级失败都必须降级，而不是把探针带崩
            logger.warning("trading_day_source_error", source=source, anchor=str(anchor), error=str(exc))
            continue
        if resolved is not None:
            return TradingDayResult(date=resolved, source=source, degraded=False)

    fallback = _weekday_fallback(anchor)
    logger.warning(
        "trading_day_weekday_fallback",
        anchor=str(anchor),
        fallback=str(fallback),
        hint="交易日历与 provider 均不可用；休市期该口径会误报，请检查 quant.trading_calendar 刷新任务",
    )
    return TradingDayResult(date=fallback, source=SOURCE_WEEKDAY_FALLBACK, degraded=True)


def last_closed_trading_day(
    ref: Optional[datetime] = None,
    *,
    cutoff: dtime = DEFAULT_CUTOFF,
    provider_lookback_days: int = DEFAULT_PROVIDER_LOOKBACK_DAYS,
) -> TradingDayResult:
    """最近一个**已收盘**的交易日（本仓唯一口径）。

    Args:
        ref: 参考时刻，缺省 `datetime.now()`；只接受 `datetime`（不接受裸 `date`，
            以免"某天"与"某天的 15:30"两种语义混淆）。
        cutoff: 收盘基准，缺省 15:30（与修复前一致）。
        provider_lookback_days: ② 的查询窗口。

    Returns:
        `TradingDayResult`。

    Raises:
        TypeError: `ref` 不是 `datetime`（唯一的"抛"路径；其余失败一律降级）。
    """
    if ref is None:
        ref = datetime.now()
    if isinstance(ref, date) and not isinstance(ref, datetime):
        raise TypeError("last_closed_trading_day(ref) 只接受 datetime；裸 date 请自行补 15:30 语义")

    anchor = _anchor(ref, cutoff)
    return _resolve_chain(anchor, provider_lookback_days)


def resolve_trading_day(
    day: Union[date, datetime],
    *,
    provider_lookback_days: int = DEFAULT_PROVIDER_LOOKBACK_DAYS,
) -> TradingDayResult:
    """指定某一天**是不是**交易日（`last_closed_trading_day` 的姊妹函数，共用同一条取数链）。

    REQ-261004154902-a7cd · FR-3：`TradingDayGuard` 的「今天」分支改走本函数，
    不再用「近 7 日有 K 线」启发式（长假误判的来源）。

    Args:
        day: 待判定的那一天（`date`；`datetime` 取 `.date()`）。不接受裸字符串——
            调用方（`TradingDayGuard`）已在入口归一化日期。
        provider_lookback_days: ② 的查询窗口。

    Returns:
        `TradingDayResult`，与 `last_closed_trading_day` **同形状**。判据是
        **`result.date == day` ⟺ 该日是交易日**（`result.date` = `<= day` 的最大交易日）；
        `source` 说明这一答案来自哪一级（`calendar_table` / `provider` / `weekday_fallback`），
        `degraded=True` 表示走了周一~周五回退（休市期会把法定节假日当作交易日，必须标注）。

    Raises:
        TypeError: `day` 既不是 `date` 也不是 `datetime`（唯一的"抛"路径）。
    """
    if isinstance(day, datetime):
        day = day.date()
    if not isinstance(day, date):
        raise TypeError("resolve_trading_day(day) 只接受 date / datetime（不接受字符串）")
    return _resolve_chain(day, provider_lookback_days)


__all__ = [
    "TradingDayResult",
    "last_closed_trading_day",
    "resolve_trading_day",
    "SOURCE_CALENDAR_TABLE",
    "SOURCE_PROVIDER",
    "SOURCE_WEEKDAY_FALLBACK",
    "DEFAULT_CUTOFF",
]
