"""分域纯函数用例 —— REQ-261006163444-8e4f（t1/t5 共用）

覆盖设计 test-cases 文档 §1 的 T1–T7，外加两条契约用例（frozen、鸭子类型入参/退化收敛）。
本文件**不碰数据库**：`classify_domain` 是纯函数，`build_domain_snapshot` 用假仓储注入。
"""
import logging

import pytest
from dataclasses import FrozenInstanceError

from application.services.kline_domain import (
    STOCK_MIN_GAP,
    TRADABLE_MAX_GAP,
    UNKNOWN_GAP,
    DomainSnapshot,
    build_domain_snapshot,
    classify_domain,
)

# 倒序交易日（[0] = D_last）；故意含一个"非交易日"以验证名次按传入序列计
DATES = [
    "2026-09-30",  # rn 1  → gap 0
    "2026-09-29",  # rn 2  → gap 1
    "2026-09-28",  # rn 3  → gap 2
    "2026-09-25",  # rn 4  → gap 3
    "2026-09-24",  # rn 5  → gap 4  （观察中上界）
    "2026-09-23",  # rn 6  → gap 5  （存量下界）
    "2026-09-22",  # rn 7  → gap 6
    "2026-09-21",  # rn 8  → gap 7
]


def test_t1_three_way_split():
    """T1 三分法：最后交易日在域、隔 2 日在观察中、远古日在存量。"""
    snap = classify_domain(DATES, [("A", "2026-09-30"), ("B", "2026-09-28"), ("C", "2020-01-02")])
    assert snap.gap_days["A"] == 0
    assert snap.gap_days["B"] == 2
    assert "A" in snap.tradable
    assert "B" in snap.observing
    assert "C" in snap.stock
    assert snap.last_trade_date == "2026-09-30"
    assert snap.prev_trade_date == "2026-09-29"


def test_t2_gap_boundary_4_and_5():
    """T2 边界闭合：gap==4 落观察中、gap==5 落存量（不是 >=5 之外的其它分段）。"""
    snap = classify_domain(DATES, [("E", "2026-09-24"), ("F", "2026-09-23")])
    assert snap.gap_days["E"] == 4 and "E" in snap.observing
    assert snap.gap_days["F"] == 5 and "F" in snap.stock
    assert STOCK_MIN_GAP == 5 and TRADABLE_MAX_GAP == 0


def test_t3_dropped_new_is_gap_one():
    """T3 掉出定义：gap==1 同时落 observing 与 dropped_new。"""
    snap = classify_domain(DATES, [("A", "2026-09-30"), ("B", "2026-09-29")])
    assert snap.gap_days["B"] == 1
    assert snap.dropped_new == frozenset({"B"})
    assert "B" in snap.observing and "B" not in snap.tradable


def test_t4_single_trade_date_dropout_unknown():
    """T4 只有一个交易日时：掉出不可判（dropped_known False、dropped_new 为空）。"""
    snap = classify_domain(["2026-09-30"], [("A", "2026-09-30")])
    assert snap.prev_trade_date is None
    assert snap.dropped_known is False
    assert snap.dropped_new == frozenset()
    assert "A" in snap.tradable


@pytest.mark.parametrize("empty", [[], ()])
def test_t5_degenerate_never_raises(empty):
    """T5 退化输入：不抛异常，收敛为 degraded + 原因，所有集合为空。"""
    snap = classify_domain(empty, [])
    assert isinstance(snap, DomainSnapshot)
    assert snap.degraded is True
    assert snap.degrade_reason == "no_trade_dates"
    assert snap.last_trade_date is None
    assert not snap.tradable and not snap.observing and not snap.stock and not snap.dropped_new


def test_t5b_no_symbols_is_degraded():
    """T5b 有交易日但无标的：同样按退化响亮处理（设计未写明，实施时新增）。"""
    snap = classify_domain(["2026-09-30"], [])
    assert snap.degraded is True and snap.degrade_reason == "no_symbols"


def test_t6_unknown_day_falls_to_stock_with_warning(caplog):
    """T6 标的日子不在交易日集合：落存量、gap=UNKNOWN_GAP、日志点名。"""
    with caplog.at_level(logging.WARNING):
        snap = classify_domain(DATES, [("X", "1999-01-01")])
    assert snap.gap_days["X"] == UNKNOWN_GAP
    assert "X" in snap.stock
    assert any("不在交易日集合内" in r.getMessage() and "X" in r.getMessage()
               for r in caplog.records)


def test_t7_sets_are_disjoint_and_cover_all():
    """T7 不变量：三层两两不相交，且并集等于 gap_days 键集。"""
    rows = [("A", "2026-09-30"), ("B", "2026-09-29"), ("C", "2026-09-28"),
            ("D", "2026-09-23"), ("E", "1999-01-01")]
    snap = classify_domain(DATES, rows)
    layers = [snap.tradable, snap.observing, snap.stock]
    assert snap.tradable | snap.observing | snap.stock == set(snap.gap_days)
    assert not (snap.tradable & snap.observing)
    assert not (snap.observing & snap.stock)
    assert not (snap.tradable & snap.stock)
    assert len(snap.tradable) + len(snap.observing) + len(snap.stock) == snap.total


def test_t7b_duplicate_symbol_keeps_latest():
    """同一标的重复出现时取最新（更小 gap），旧的不得覆盖新的。"""
    snap = classify_domain(DATES, [("A", "2020-01-01"), ("A", "2026-09-30")])
    assert snap.gap_days["A"] == 0 and "A" in snap.tradable
    snap2 = classify_domain(DATES, [("A", "2026-09-30"), ("A", "2020-01-01")])
    assert snap2.gap_days["A"] == 0 and "A" in snap2.tradable


def test_contract_frozen_and_date_types():
    """契约：快照不可变；date/datetime 入参与字符串等价。"""
    from datetime import date, datetime
    snap = classify_domain([date(2026, 9, 30), date(2026, 9, 29)], [("A", date(2026, 9, 30))])
    assert snap.last_trade_date == "2026-09-30" and snap.gap_days["A"] == 0
    snap2 = classify_domain([datetime(2026, 9, 30, 15, 0)], [("A", "2026-09-30")])
    assert snap2.gap_days["A"] == 0
    with pytest.raises(FrozenInstanceError):
        snap.degraded = True


class _FakeRepo:
    def __init__(self, dates, rows):
        self._dates, self._rows = dates, rows

    def list_recent_trade_dates(self, limit=2):
        return self._dates[:limit]

    def list_symbol_last_trade_date(self):
        return self._rows


class _BrokenRepo:
    def list_recent_trade_dates(self, limit=2):
        raise RuntimeError("db down")

    def list_symbol_last_trade_date(self):
        return []


def test_contract_build_snapshot_duck_typing():
    """契约：build_domain_snapshot 只依赖两个只读方法（鸭子类型）。"""
    snap = build_domain_snapshot(_FakeRepo(["2026-09-30", "2026-09-29"],
                                           [("A", "2026-09-30"), ("B", "2026-09-29")]))
    assert snap.last_trade_date == "2026-09-30"
    assert snap.dropped_new == frozenset({"B"})
    assert snap.degraded is False


def test_contract_build_snapshot_failure_degrades():
    """契约：仓储抛错 ⇒ 退化快照（不抛），reason 携带原因。"""
    snap = build_domain_snapshot(_BrokenRepo())
    assert snap.degraded is True
    assert "db down" in (snap.degrade_reason or "")


def test_contract_build_snapshot_asks_enough_trade_dates():
    """回归锁（2026-10-06 集成实测发现）：build 必须取够 STOCK_MIN_GAP 个交易日。

    只取 2 个时，"隔了 2~4 个交易日"的标的算不出名次 ⇒ 被静默丢进存量
    （实测观察中假报 2 只 / 存量 404 只；取够后为 3 / 403）。
    """
    calls = {}

    class _Repo:
        def list_recent_trade_dates(self, limit=2):
            calls['limit'] = limit
            return ["2026-09-30", "2026-09-29", "2026-09-28", "2026-09-25", "2026-09-24"][:limit]

        def list_symbol_last_trade_date(self):
            return [("A", "2026-09-30"), ("B", "2026-09-28"), ("C", "2026-09-24"),
                    ("OLD", "2020-01-01")]

    snap = build_domain_snapshot(_Repo())
    assert calls['limit'] >= STOCK_MIN_GAP == 5
    assert snap.gap_days["B"] == 2 and "B" in snap.observing      # 不是存量
    assert snap.gap_days["C"] == 4 and "C" in snap.observing
    assert "OLD" in snap.stock                                    # 名次缺失 ⇒ 存量（正确）
