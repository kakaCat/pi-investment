"""迟滞闩锁 + 每条件日上限（REQ-261016155500-4f2a wt:engine:1，2026-10-16）

验收锚点：
  · 阈值附近抖动（回落但未越过迟滞带）不重新武装 → 不重复推送；
  · 远离后真实再穿越 → 可重新触发；
  · 每规则每条件每日 ≤2 次通知：第 3 次只归档（suppressed=true，reason=日上限）；
  · 计数随 runtime state 持久化（restore 只接今天的计数）。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.conditions import (
    DEFAULT_DAILY_EMIT_CAP, hysteresis_rearm_price, within_hysteresis_band,
)
from qs_watch.application.services.watch_engine.state_manager import StateManager
from qs_watch.application.services.watch_engine.trigger_judge import TriggerJudge

NOW = datetime(2026, 10, 16, 10, 0, 0)
BELOW = {'type': 'price_break', 'params': {'price': 12.85, 'direction': 'below'}}


def _judge():
    return TriggerJudge(StateManager())


# ── 迟滞带纯函数 ────────────────────────────────────────────

def test_hysteresis_rearm_price_below():
    # 12.85 下破：h = max(12.85*0.5%, 0.05) = 0.06425 → 重新武装需回升到 12.91425 上
    rearm = hysteresis_rearm_price(BELOW)
    assert abs(rearm - 12.91425) < 1e-9
    # 带内（12.90）仍迟滞；带外（13.00）重新武装
    assert within_hysteresis_band(BELOW, 12.90) is True
    assert within_hysteresis_band(BELOW, 13.00) is False


def test_hysteresis_rearm_price_above():
    cond = {'type': 'price_break', 'params': {'price': 15.0, 'direction': 'above'}}
    rearm = hysteresis_rearm_price(cond)
    assert abs(rearm - 14.925) < 1e-9
    assert within_hysteresis_band(cond, 14.95) is True
    assert within_hysteresis_band(cond, 14.90) is False


def test_hysteresis_ignored_for_non_price_break():
    assert hysteresis_rearm_price({'type': 'pnl_pct', 'params': {'pct': -8}}) is None
    assert within_hysteresis_band({'type': 'pnl_pct', 'params': {'pct': -8}}, 1.0) is False
    assert within_hysteresis_band(BELOW, None) is False


# ── 抖动不复读 ──────────────────────────────────────────────

def test_jitter_does_not_rearm():
    """触发 → 回落但仍在上迟滞带内 → 不重新武装 → 再次跌穿不重复推送。"""
    judge = _judge()
    # 第 1 次：跌穿 → 发
    assert judge.should_emit(1, 0, True, BELOW, NOW, value=12.80) is True
    judge.mark_emitted(1, 0, NOW, '002007')
    # 价格回升到阈值上方但未越过迟滞带（12.90 > 12.85 但 ≤ 12.914）→ 保持闩锁
    assert judge.should_emit(1, 0, False, BELOW, NOW + timedelta(minutes=10),
                             value=12.90) is False
    # 再次跌穿（12.80 ≤ 12.85）→ 闩锁还在 → 不重复
    assert judge.should_emit(1, 0, True, BELOW, NOW + timedelta(minutes=20),
                             value=12.80) is False


def test_real_recovery_can_retrigger():
    """真正回升越过迟滞带（12.95 > 12.914）→ 重新武装 → 下次跌穿可再发。"""
    judge = _judge()
    assert judge.should_emit(1, 0, True, BELOW, NOW, value=12.80) is True
    judge.mark_emitted(1, 0, NOW, '002007')
    # 越过迟滞带 → 重新武装
    assert judge.should_emit(1, 0, False, BELOW, NOW + timedelta(minutes=10),
                             value=12.95) is False
    # 冷却默认 300s：推进 6 分钟后再跌穿 → 重新触发
    later = NOW + timedelta(minutes=16)
    assert judge.should_emit(1, 0, True, BELOW, later, value=12.80) is True


def test_non_price_break_keeps_legacy_unlatch():
    """非 price_break 维持原语义：未触发即重新武装。"""
    judge = _judge()
    cond = {'type': 'pnl_pct', 'params': {'pct': -8, 'direction': 'below'}}
    assert judge.should_emit(1, 0, True, cond, NOW) is True
    judge.mark_emitted(1, 0, NOW, '002007')
    # 未触发 → 立即重新武装（无迟滞带概念）
    assert judge.should_emit(1, 0, False, cond, NOW + timedelta(minutes=1)) is False
    assert (1, 0) not in judge.state.latched


# ── 每日上限 ────────────────────────────────────────────────

def test_daily_cap_archives_third_emit():
    judge = _judge()
    assert judge.daily_emit_exceeded(1, 0, NOW) is False
    judge.bump_daily_emit(1, 0, NOW)
    judge.bump_daily_emit(1, 0, NOW)
    assert judge.daily_emit_exceeded(1, 0, NOW) is True
    assert DEFAULT_DAILY_EMIT_CAP == 2


def test_daily_cap_resets_next_day():
    judge = _judge()
    judge.bump_daily_emit(1, 0, NOW)
    judge.bump_daily_emit(1, 0, NOW)
    tomorrow = NOW + timedelta(days=1)
    assert judge.daily_emit_exceeded(1, 0, tomorrow) is False
    judge.bump_daily_emit(1, 0, tomorrow)
    assert judge.daily_emit_exceeded(1, 0, tomorrow) is False  # 1 < 2


# ── 计数持久化（restore 只接今天的计数）──────────────────────

def _store_stub(rows):
    return SimpleNamespace(load_all=lambda: rows,
                           load_dedup=lambda: [], load_events=lambda since=None: [],
                           load_price_history=lambda symbols=None, since=None: [])


def test_restore_takes_only_todays_count():
    today = NOW.date()
    rows = [
        {'rule_id': 1, 'cond_idx': 0, 'latched': False, 'last_triggered_at': None,
         'cooldown_effective_sec': None,
         'emit_count_date': today, 'emit_count': 2},          # 今天 → 接住
        {'rule_id': 2, 'cond_idx': 0, 'latched': False, 'last_triggered_at': None,
         'cooldown_effective_sec': None,
         'emit_count_date': today - timedelta(days=1), 'emit_count': 5},  # 昨天 → 作废
    ]
    sm = StateManager(store=_store_stub(rows))
    sm.restore_from_store(now=NOW)
    assert sm.daily_emit_counts.get((1, 0)) == (today, 2)
    assert (2, 0) not in sm.daily_emit_counts
    judge = TriggerJudge(sm)
    assert judge.daily_emit_exceeded(1, 0, NOW) is True   # 恢复后上限仍然有效
    assert judge.daily_emit_exceeded(2, 0, NOW) is False
