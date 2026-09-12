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
