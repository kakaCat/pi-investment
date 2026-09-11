"""TradingDayGuard 单测（步2 交易日判断收口，2026-09-11，w-f4aa1f6a）

覆盖：
1. judge_trading_day 纯函数语义（周末/未来/有K线/当日启发式/过去无K线）
2. TradingDayGuard 的判定来源与降级标记（monkeypatch 数据源，不依赖真实 DB）
3. 写入型守卫 should_write_daily 的语义
4. 兼容层：live_trading.simulation_trader.judge_trading_day 仍可用（同名委托）
"""
from datetime import date

import pytest

from application.services.trading_day_guard import (
    SOURCE_INTRADAY,
    SOURCE_KLINE,
    SOURCE_NO_DATA,
    SOURCE_UNAVAILABLE,
    SOURCE_WEEKEND,
    TradingDayGuard,
    judge_trading_day,
)


# ── 1. 纯函数 ────────────────────────────────────────────────
def test_weekend_is_never_trading_day():
    # 2026-08-08 是周六——正是历史上被写入 5 条合成快照的那天
    assert judge_trading_day(
        date(2026, 8, 8), kline_exists_on_date=True,
        latest_kline_date=date(2026, 8, 7), today=date(2026, 8, 8),
    ) is False


def test_future_date_is_not_trading_day():
    assert judge_trading_day(
        date(2026, 9, 30), kline_exists_on_date=False,
        latest_kline_date=date(2026, 9, 11), today=date(2026, 9, 11),
    ) is False


def test_kline_present_means_trading_day():
    assert judge_trading_day(
        date(2026, 9, 10), kline_exists_on_date=True,
        latest_kline_date=date(2026, 9, 10), today=date(2026, 9, 11),
    ) is True


def test_today_without_kline_uses_recent_activity_heuristic():
    """盘中场景：日K 17:40 才落库，不能因"今天还没K线"判非交易日
    （2026-08-12 事故：v13/v14 调仓因此从未执行却记 success）。"""
    assert judge_trading_day(
        date(2026, 9, 11), kline_exists_on_date=False,
        latest_kline_date=date(2026, 9, 10), today=date(2026, 9, 11),
    ) is True


def test_today_with_stale_market_is_not_trading_day():
    assert judge_trading_day(
        date(2026, 9, 11), kline_exists_on_date=False,
        latest_kline_date=date(2026, 8, 1), today=date(2026, 9, 11),
    ) is False


def test_past_weekday_without_kline_is_holiday():
    assert judge_trading_day(
        date(2026, 10, 1), kline_exists_on_date=False,
        latest_kline_date=date(2026, 9, 30), today=date(2026, 10, 8),
    ) is False


# ── 2. 护栏判定来源与降级 ─────────────────────────────────────
@pytest.fixture(autouse=True)
def _clear_guard_cache():
    from application.services import trading_day_guard as m

    m._verdict_cache.clear()
    yield
    m._verdict_cache.clear()


def test_check_source_weekend(monkeypatch):
    called = {'n': 0}

    def _boom(day):
        called['n'] += 1
        raise AssertionError('周末不应查数据源')

    monkeypatch.setattr(TradingDayGuard, '_kline_stats', staticmethod(_boom))
    v = TradingDayGuard.check('2026-08-08')
    assert v.is_trading_day is False
    assert v.source == SOURCE_WEEKEND and v.degraded is False
    assert called['n'] == 0


def test_check_source_kline(monkeypatch):
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (True, date(2026, 9, 10))),
    )
    v = TradingDayGuard.check('2026-09-10')
    assert v.is_trading_day is True
    assert v.source == SOURCE_KLINE and v.degraded is False


def test_check_marks_intraday_heuristic_degraded(monkeypatch):
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (False, date.today())),
    )
    v = TradingDayGuard.check(date.today())
    assert v.is_trading_day is True
    assert v.source == SOURCE_INTRADAY and v.degraded is True


def test_check_no_data_source(monkeypatch):
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (False, date(2026, 9, 10))),
    )
    v = TradingDayGuard.check('2026-09-09')
    assert v.is_trading_day is False
    assert v.source == SOURCE_NO_DATA


def test_check_datasource_failure_is_conservative_and_visible(monkeypatch):
    def _boom(day):
        raise RuntimeError('db down')

    monkeypatch.setattr(TradingDayGuard, '_kline_stats', staticmethod(_boom))
    v = TradingDayGuard.check('2026-09-10')
    assert v.is_trading_day is False          # 保守：宁可少写，不写合成数据
    assert v.source == SOURCE_UNAVAILABLE and v.degraded is True


# ── 3. 写入型守卫 ────────────────────────────────────────────
def test_should_write_daily_blocks_weekend():
    v = TradingDayGuard.should_write_daily('2026-08-08')
    assert v.is_trading_day is False and v.source == SOURCE_WEEKEND


def test_should_write_daily_allows_trading_day(monkeypatch):
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (True, date(2026, 9, 10))),
    )
    assert TradingDayGuard.should_write_daily('2026-09-10').is_trading_day is True


# ── 4. 兼容层 ────────────────────────────────────────────────
def test_simulation_trader_reexport_still_works():
    from live_trading.simulation_trader import judge_trading_day as legacy

    assert legacy(
        date(2026, 8, 8), kline_exists_on_date=True,
        latest_kline_date=date(2026, 8, 7), today=date(2026, 8, 8),
    ) is False
    assert legacy(
        date(2026, 9, 10), kline_exists_on_date=True,
        latest_kline_date=date(2026, 9, 10), today=date(2026, 9, 11),
    ) is True
