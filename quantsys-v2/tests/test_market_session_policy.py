"""MarketSessionPolicy 纯函数单测（RFC 016 D1/D3/D4；2026-09-12）

不依赖真实 DB、不依赖真实时钟（零 IO）——范式对齐 tests/test_trading_day_guard.py。

覆盖：
1. 相位判定与午休口径（11:30–13:00 不属于盘中）
2. 边界：09:15 / 09:25 / 09:30 / 11:30 / 13:00 / 14:57 / 15:00
3. 非交易日
4. `is_market_open` 与 `is_price_fresh_window` 的差异（集合竞价/午休更宽）
5. 交易分钟与进度（与旧 elapsed_trading_fraction 逐点等价）
6. 三种"开始"：09:15 可报价 / 09:25 可撮合 / 09:30 可连续交易
7. VO 组装：reason 可复核、degraded 透传、to_dict 契约字段名
8. price_is_fresh（D4）：休市日读到最近交易日收盘价 = 新鲜
"""
from datetime import datetime, time

from domain.trading.models.market_session import MarketSession, SessionPhase
from domain.trading.services.market_session_policy import (
    AFTERNOON_START,
    CALL_AUCTION_START,
    CONTINUOUS_START,
    MATCHING_START,
    TOTAL_TRADING_MINUTES,
    MarketSessionPolicy,
)

POLICY = MarketSessionPolicy()


# ── 1/2. 相位判定与边界 ───────────────────────────────────────────────
def test_lunch_break_is_not_market_open():
    """午休唯一口径：11:30–13:00 不属于盘中"""
    assert POLICY.phase_for(time(12, 0)) is SessionPhase.LUNCH_BREAK
    assert POLICY.is_market_open(SessionPhase.LUNCH_BREAK) is False


def test_phase_boundaries():
    assert POLICY.phase_for(time(9, 0)) is SessionPhase.PRE_OPEN
    assert POLICY.phase_for(time(9, 15)) is SessionPhase.CALL_AUCTION
    assert POLICY.phase_for(time(9, 25)) is SessionPhase.OPENING
    assert POLICY.phase_for(time(9, 30)) is SessionPhase.MORNING
    assert POLICY.phase_for(time(11, 30)) is SessionPhase.MORNING      # 端点闭合：算盘中
    assert POLICY.phase_for(time(13, 0)) is SessionPhase.AFTERNOON     # 端点闭合：算盘中
    assert POLICY.phase_for(time(14, 57)) is SessionPhase.AFTERNOON
    assert POLICY.phase_for(time(15, 0)) is SessionPhase.AFTERNOON     # 端点闭合：算盘中
    assert POLICY.phase_for(time(15, 1)) is SessionPhase.AFTER_HOURS


def test_boundaries_stay_market_open():
    """11:30 / 13:00 / 15:00 与既有 TRADING_SESSIONS(start<=t<=end) 逐字一致"""
    for t in (time(11, 30), time(13, 0), time(15, 0)):
        assert POLICY.is_market_open(POLICY.phase_for(t)) is True


# ── 3. 非交易日 ──────────────────────────────────────────────────────
def test_non_trading_day():
    assert POLICY.phase_for(time(10, 0), is_trading_day=False) is SessionPhase.NON_TRADING_DAY
    assert POLICY.is_price_fresh_window(time(10, 0), is_trading_day=False) is False
    assert POLICY.elapsed_trading_minutes(time(10, 0), is_trading_day=False) == 0


# ── 4. 开市 vs 价格新鲜窗口 ───────────────────────────────────────────
def test_price_fresh_window_is_wider_than_market_open():
    # 集合竞价：价格已在变，但尚未连续交易
    assert POLICY.is_price_fresh_window(time(9, 20), is_trading_day=True) is True
    assert POLICY.is_market_open(POLICY.phase_for(time(9, 20))) is False
    # 午休：不可交易，但报价窗口未结束
    assert POLICY.is_price_fresh_window(time(12, 0), is_trading_day=True) is True
    # 收盘后 5 分钟宽限内仍算；再往后不算
    assert POLICY.is_price_fresh_window(time(15, 5), is_trading_day=True) is True
    assert POLICY.is_price_fresh_window(time(15, 6), is_trading_day=True) is False
    # 集合竞价之前不算
    assert POLICY.is_price_fresh_window(time(9, 10), is_trading_day=True) is False


# ── 5. 交易分钟 / 进度（与旧 elapsed_trading_fraction 等价）────────────
def test_elapsed_trading_minutes_matches_legacy_semantics():
    assert POLICY.elapsed_trading_minutes(time(9, 30)) == 0
    assert POLICY.elapsed_trading_minutes(time(10, 30)) == 60
    assert POLICY.elapsed_trading_minutes(time(11, 30)) == 120
    assert POLICY.elapsed_trading_minutes(time(12, 30)) == 120   # 午休冻结在上午收盘
    assert POLICY.elapsed_trading_minutes(time(13, 0)) == 120
    assert POLICY.elapsed_trading_minutes(time(14, 0)) == 180
    assert POLICY.elapsed_trading_minutes(time(15, 0)) == TOTAL_TRADING_MINUTES
    assert POLICY.elapsed_trading_minutes(time(16, 0)) == TOTAL_TRADING_MINUTES


def test_session_progress():
    assert POLICY.session_progress(time(9, 30)) == 0.0
    assert POLICY.session_progress(time(12, 0)) == 0.5
    assert POLICY.session_progress(time(15, 0)) == 1.0


# ── 6. 三种"开始" ────────────────────────────────────────────────────
def test_three_starts_are_distinct():
    assert CALL_AUCTION_START == time(9, 15)   # 可报价开始（集合竞价）
    assert MATCHING_START == time(9, 25)       # 可撮合开始
    assert CONTINUOUS_START == time(9, 30)     # 可连续交易开始
    assert AFTERNOON_START == time(13, 0)


def test_session_start_of_and_next_boundary():
    assert POLICY.session_start_of(SessionPhase.MORNING) == time(9, 30)
    assert POLICY.session_start_of(SessionPhase.AFTERNOON) == time(13, 0)
    assert POLICY.next_boundary(time(9, 0)) == time(9, 15)
    assert POLICY.next_boundary(time(11, 0)) == time(11, 30)
    assert POLICY.next_boundary(time(15, 30)) is None


# ── 7. VO 组装 ───────────────────────────────────────────────────────
def test_evaluate_builds_reviewable_verdict():
    session = POLICY.evaluate(
        datetime(2026, 9, 11, 10, 0),
        is_trading_day=True,
        day_source='kline-data',
        day_degraded=False,
    )
    assert isinstance(session, MarketSession)
    assert session.phase is SessionPhase.MORNING
    assert session.is_market_open is True
    assert session.phase_start == '09:30' and session.phase_end == '11:30'
    assert session.next_boundary_at.startswith('2026-09-11T11:30')
    assert session.elapsed_trading_minutes == 30
    assert session.session_progress == 0.125
    assert session.source == 'clock+kline-data'
    assert session.degraded is False
    assert '相位 morning' in session.reason
    # 契约字段名（对外一律 session_phase，不得用已被占用的 market_phase）
    d = session.to_dict()
    assert d['session_phase'] == 'morning'
    assert d['is_market_open'] is True
    assert 'market_phase' not in d


def test_evaluate_propagates_degradation():
    session = POLICY.evaluate(
        datetime(2026, 9, 11, 10, 0),
        is_trading_day=True,
        day_source='intraday-recent-market',
        day_degraded=True,
        day_reason='当日K线未落库，按近期市场活跃判定',
    )
    assert session.degraded is True
    assert '降级' in session.reason


# ── 8. 价格新鲜（D4）─────────────────────────────────────────────────
def test_price_is_fresh_non_trading_day_reads_last_close():
    """休市日读到最近交易日收盘价 → 新鲜（是"已收盘最终价"，不是陈旧）"""
    session = POLICY.evaluate(
        datetime(2026, 9, 12, 10, 0), is_trading_day=False, day_source='weekend',
    )
    assert session.is_market_open is False
    assert session.price_is_fresh('2026-09-11', '2026-09-11') is True
    assert session.price_is_fresh('2026-09-10', '2026-09-11') is False


# ── 9. 审查回归钉子（2026-09-12：每条都是代码审查实测复现后补的）─────────
def test_endpoint_closure_is_minute_granular_not_second_exact():
    """端点闭合必须是**整分钟**语义：11:30:45 / 15:00:30 仍算盘中。

    回归背景：`_INCLUSIVE_END` 曾按精确 `time` 相等匹配，而调用方传的是
    `datetime.now().time()`（秒/微秒非零）→ 11:30 / 15:00 两个节拍被判
    LUNCH_BREAK / AFTER_HOURS，`intraday_monitor_check()`（含收盘那次止损止盈）被静默跳过。
    """
    assert POLICY.phase_for(time(11, 30, 45)) is SessionPhase.MORNING
    assert POLICY.phase_for(time(11, 30, 0, 1)) is SessionPhase.MORNING
    assert POLICY.phase_for(time(15, 0, 30)) is SessionPhase.AFTERNOON
    assert POLICY.phase_for(time(15, 0, 59, 999999)) is SessionPhase.AFTERNOON
    for t in (time(11, 30, 45), time(15, 0, 30)):
        assert POLICY.is_market_open(POLICY.phase_for(t)) is True
        assert POLICY.is_price_fresh_window(t, is_trading_day=True) is True
    # 宽限窗口同口径（曾出现 15:05 新鲜 / 15:05:30 不新鲜 的秒级悬崖）
    assert POLICY.is_price_fresh_window(time(15, 5, 30), is_trading_day=True) is True


def test_next_boundary_empty_on_non_trading_day():
    """非交易日没有相位边界（曾被填成当日 11:30，会让消费者在周六醒来）"""
    v = POLICY.evaluate(datetime(2026, 9, 12, 10, 0), is_trading_day=False, day_source='weekend')
    assert v.next_boundary_at == ''


def test_boundary_fields_share_timezone():
    """`at` 与 `next_boundary_at` 必须同口径（`datetime.combine` 曾丢 tzinfo）"""
    from zoneinfo import ZoneInfo
    v = POLICY.evaluate(
        datetime(2026, 9, 11, 10, 0, tzinfo=ZoneInfo('Asia/Shanghai')),
        is_trading_day=True, day_source='kline-data',
    )
    assert v.at.endswith('+08:00')
    assert v.next_boundary_at.endswith('+08:00')
    assert datetime.fromisoformat(v.next_boundary_at) > datetime.fromisoformat(v.at)


def test_price_is_fresh_fails_closed_on_missing_values():
    """缺失/不可解析一律判**不新鲜**（旧实现 `str(a or '') >= str(b or '')` 会把空值判成新鲜）"""
    v = POLICY.evaluate(datetime(2026, 9, 12, 10, 0), is_trading_day=False, day_source='weekend')
    assert v.price_is_fresh(None, None) is False
    assert v.price_is_fresh('', '2026-09-11') is False
    assert v.price_is_fresh('2026-09-11', None) is False
    assert v.price_is_fresh('not-a-date', '2026-09-11') is False


def test_minute_freshness_rejects_future_timestamps():
    """未来时间戳不算"新鲜"（`abs()` 曾双向放行）；aware/naive 混用不再抛 TypeError"""
    from zoneinfo import ZoneInfo
    now = datetime(2026, 9, 11, 10, 0, 0)
    assert POLICY.minute_freshness_ok(datetime(2026, 9, 11, 10, 3), now) is False   # 未来
    assert POLICY.minute_freshness_ok(datetime(2026, 9, 11, 9, 58), now) is True    # 过去 2 分钟
    assert POLICY.minute_freshness_ok(datetime(2026, 9, 11, 9, 50), now) is False   # 过去 10 分钟
    assert POLICY.minute_freshness_ok(
        datetime(2026, 9, 11, 9, 58), datetime(2026, 9, 11, 10, 0, tzinfo=ZoneInfo('Asia/Shanghai')),
    ) is True


def test_service_is_trading_day_accepts_date_and_str(monkeypatch):
    """`MarketSessionService.is_trading_day` 必须接受 date / 'YYYY-MM-DD'（曾 AttributeError）"""
    from datetime import date
    from application.services.market_session_service import MarketSessionService
    from application.services.trading_day_guard import TradingDayGuard

    monkeypatch.setattr(
        TradingDayGuard, 'is_trading_day', classmethod(lambda cls, day=None: True))
    svc = MarketSessionService()
    assert svc.is_trading_day(date(2026, 9, 11)) is True
    assert svc.is_trading_day('2026-09-11') is True
    assert svc.is_trading_day(datetime(2026, 9, 11, 10, 0)) is True
    assert svc.is_trading_day() is True


def test_section_bounds_name_is_public_and_single_sourced():
    """RFC 016 D2 指定的唯一常量名 `SESSION_BOUNDS` 必须存在且被 `window_of` 使用"""
    from domain.trading.services.market_session_policy import SESSION_BOUNDS
    assert isinstance(SESSION_BOUNDS, tuple) and len(SESSION_BOUNDS) == 5
    assert POLICY.window_of(SessionPhase.MORNING) in SESSION_BOUNDS


def test_intraday_gates_agree_at_sub_minute_endpoints():
    """外层节拍闸门与 `IntradayMonitor` 内层闸门必须一致（端到端）。

    回归背景：只修外层时出现「外层 True / 内层 False」→ 11:30 与 15:00 的
    `intraday_monitor_check()`（含收盘那次止损/止盈）仍被跳过。本钉子同时钉两层。
    """
    from adapters.inbound.fastapi_app.orchestrator_bootstrap import _in_intraday_window
    from application.services.intraday_monitor import IntradayMonitor

    monitor = object.__new__(IntradayMonitor)  # 绕过重依赖构造（仓库既有测试手法）
    for h, m, s in ((11, 30, 45), (15, 0, 30), (10, 0, 0), (14, 30, 0)):
        now = datetime(2026, 9, 11, h, m, s)
        assert _in_intraday_window(now) is True, now
        assert monitor._is_trading_time(now.time()) is True, now
    lunch = datetime(2026, 9, 11, 12, 0)
    assert _in_intraday_window(lunch) is False
    assert monitor._is_trading_time(lunch.time()) is False


def test_market_monitor_silent_time_converges_to_same_lunch_break():
    """市场监控的「静默时段」必须与策略的 `LUNCH_BREAK` 同源（第 7 份午休副本收敛）。

    边界：13:00 止；**11:30 整分钟不算静默**（端点闭合规则把它归 MORNING）——
    这是与原实现 `11.5 <= h+m/60 < 13` 唯一的有意差异（原从 11:30 起即静默）。
    """
    from application.services.market_monitor_scheduler import MarketMonitorScheduler

    sched = object.__new__(MarketMonitorScheduler)  # 绕过 BackgroundScheduler 构造
    assert sched._is_silent_time(datetime(2026, 9, 11, 11, 30)) is False   # 端点闭合 → 仍算盘中
    assert sched._is_silent_time(datetime(2026, 9, 11, 11, 31)) is True
    assert sched._is_silent_time(datetime(2026, 9, 11, 12, 0)) is True
    assert sched._is_silent_time(datetime(2026, 9, 11, 12, 59, 59)) is True
    assert sched._is_silent_time(datetime(2026, 9, 11, 13, 0)) is False
    assert sched._is_silent_time(datetime(2026, 9, 11, 9, 30)) is False
    assert sched._is_silent_time(datetime(2026, 9, 11, 15, 0)) is False
