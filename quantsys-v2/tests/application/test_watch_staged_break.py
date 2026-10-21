"""staged_break 两段式伏击（2026-10-19 P1）——状态机 + 引擎接线验证

用户裁定：盯盘是「守伏击点」，触及 ≠ 信号。本文件证伪清单：
  1) 触及不发卡（静默进观察态）；
  2) 观察窗内 hold 确认达标 → 才走正常触发流水线（通知）；
  3) 窗口到期未确认 → 归档 suppressed 样本，不通知、不占日配额；
  4) reclaim / volume 两种确认语义；
  5) 跨天重置回待命；快照/恢复环回（重启不丢观察窗）；
  6) 条件校验（缺 touch/坏 kind 被拒）。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.conditions import (
    EvalContext, eval_staged_confirm, eval_staged_touch, evaluate,
    freshness_of, hysteresis_rearm_price, validate_condition,
    within_hysteresis_band,
)
from qs_watch.application.services.watch_engine.engine import (
    STAGED_EXPIRED_REASON, WatchEngine,
)
from qs_watch.application.services.watch_engine.staged_break_manager import (
    OUTCOME_CONFIRMED, OUTCOME_ENTERED, OUTCOME_EXPIRED, OUTCOME_OBSERVING,
    OUTCOME_WATCHING, StagedBreakManager,
)

T0 = datetime(2026, 10, 19, 10, 0, 0)  # 周一交易时段


def _cond(kind='hold', price=27.5, direction='below', window_min=120, **confirm_kw):
    confirm = {'kind': kind}
    confirm.update(confirm_kw)
    return {'type': 'staged_break',
            'params': {'touch': {'price': price, 'direction': direction},
                       'confirm': confirm, 'window_min': window_min}}


def _quote(price, volume=None, prev_close=None):
    return SimpleNamespace(symbol='600900', price=price, volume=volume,
                           prev_close=prev_close, change_pct=None)


def _ctx(history=(), avg_volume=None):
    return EvalContext(price_history=tuple(history), avg_volume_20d=avg_volume)


# ── 条件校验 ────────────────────────────────────────────────

def test_validate_accepts_wellformed():
    validate_condition(_cond('hold', minutes=30))
    validate_condition(_cond('reclaim'))
    validate_condition(_cond('volume', multiple=1.5))


def test_validate_rejects_bad_specs():
    with pytest.raises(ValueError, match='touch.price'):
        validate_condition({'type': 'staged_break',
                            'params': {'touch': {'direction': 'below'},
                                       'confirm': {'kind': 'hold'}}})
    with pytest.raises(ValueError, match='confirm.kind'):
        validate_condition(_cond('teleport'))
    with pytest.raises(ValueError, match='multiple'):
        validate_condition(_cond('volume'))   # volume 缺 multiple
    with pytest.raises(ValueError, match='window_min'):
        validate_condition(_cond('hold', window_min=0))


def test_evaluate_rejects_staged_break():
    """staged_break 是有状态条件：直接 evaluate 必须响亮拒绝（防旁路丢状态）"""
    with pytest.raises(ValueError, match='StagedBreakManager'):
        evaluate(_cond(), _quote(27.0), _ctx(), now=T0)


# ── 价格线语义复用（陈旧驻留 / 迟滞带对 staged 同口径）──────

def test_price_line_semantics_apply_to_touch():
    cond = _cond(price=27.5, direction='below')
    assert freshness_of(cond, prev_close=28.0) is True    # 昨收未触及 → 今日新穿越
    assert freshness_of(cond, prev_close=27.0) is False   # 昨收已在触发侧 → 陈旧驻留
    rearm = hysteresis_rearm_price(cond)
    assert rearm > 27.5                                    # 下破后需回升到 T+h
    assert within_hysteresis_band(cond, 27.6) is True
    assert within_hysteresis_band(cond, 28.0) is False


# ── 状态机 ──────────────────────────────────────────────────

def test_touch_enters_observing_silently():
    mgr = StagedBreakManager()
    outcome, res = mgr.process(1, 0, _cond(), _quote(27.4), _ctx(), T0)
    assert outcome == OUTCOME_ENTERED
    assert res.triggered is True          # 触及评估本身成立（供 fast-mode）
    assert mgr.pending() == 1


def test_hold_confirm_fires_after_minutes():
    mgr = StagedBreakManager()
    cond = _cond('hold', minutes=30)
    mgr.process(1, 0, cond, _quote(27.4), _ctx(), T0)
    # 观察中：时长不够 → 静默
    hist = [(T0, 27.4), (T0 + timedelta(minutes=10), 27.3)]
    outcome, _ = mgr.process(1, 0, cond, _quote(27.3), _ctx(hist),
                             T0 + timedelta(minutes=10))
    assert outcome == OUTCOME_OBSERVING
    # 31 分钟后持续在触发侧 → 确认成立
    hist.append((T0 + timedelta(minutes=31), 27.2))
    outcome, res = mgr.process(1, 0, cond, _quote(27.2), _ctx(hist),
                               T0 + timedelta(minutes=31))
    assert outcome == OUTCOME_CONFIRMED
    assert res.triggered is True and '伏击确认' in res.message
    assert mgr.pending() == 0             # 确认后回待命


def test_hold_broken_by_leaving_triggered_side():
    mgr = StagedBreakManager()
    cond = _cond('hold', minutes=30)
    mgr.process(1, 0, cond, _quote(27.4), _ctx(), T0)
    # 窗内价格曾回到阈值上方（离开触发侧）→ 企稳不成立，继续观察
    hist = [(T0, 27.4), (T0 + timedelta(minutes=5), 27.8)]
    outcome, _ = mgr.process(1, 0, cond, _quote(27.4), _ctx(hist),
                             T0 + timedelta(minutes=35))
    assert outcome == OUTCOME_OBSERVING


def test_reclaim_confirm():
    mgr = StagedBreakManager()
    cond = _cond('reclaim')
    mgr.process(1, 0, cond, _quote(27.4), _ctx(), T0)
    outcome, _ = mgr.process(1, 0, cond, _quote(27.3), _ctx(), T0 + timedelta(minutes=5))
    assert outcome == OUTCOME_OBSERVING                     # 仍在触发侧，未收复
    outcome, res = mgr.process(1, 0, cond, _quote(27.6), _ctx(), T0 + timedelta(minutes=6))
    assert outcome == OUTCOME_CONFIRMED                     # 收复 27.5 → 确认
    assert '伏击确认' in res.message


def test_volume_confirm_and_degraded():
    cond = _cond('volume', multiple=1.5)
    # 无均量数据 → degraded：不判死也不确认，继续观察直到窗口到期
    mgr = StagedBreakManager()
    mgr.process(1, 0, cond, _quote(27.4, volume=100), _ctx(avg_volume=None), T0)
    outcome, _ = mgr.process(1, 0, cond, _quote(27.4, volume=100),
                             _ctx(avg_volume=None), T0 + timedelta(minutes=5))
    assert outcome == OUTCOME_OBSERVING
    # 有均量且放量 → 确认
    mgr2 = StagedBreakManager()
    mgr2.process(1, 0, cond, _quote(27.4, volume=100), _ctx(avg_volume=1000), T0)
    outcome, res = mgr2.process(1, 0, cond, _quote(27.4, volume=2000),
                                _ctx(avg_volume=1000), T0 + timedelta(minutes=5))
    assert outcome == OUTCOME_CONFIRMED
    assert '放量确认' in res.message


def test_window_expiry_returns_to_watching():
    mgr = StagedBreakManager()
    cond = _cond('hold', minutes=30, window_min=60)
    mgr.process(1, 0, cond, _quote(27.4), _ctx(), T0)
    outcome, res = mgr.process(1, 0, cond, _quote(27.4), _ctx(),
                               T0 + timedelta(minutes=61))
    assert outcome == OUTCOME_EXPIRED
    assert '到期未确认' in res.message
    assert mgr.pending() == 0
    # 回到待命后价格仍在触发侧 → 新一轮触及可再进观察（下一周期重新计时）
    outcome, _ = mgr.process(1, 0, cond, _quote(27.3), _ctx(),
                             T0 + timedelta(minutes=62))
    assert outcome == OUTCOME_ENTERED


def test_snapshot_restore_roundtrip():
    cond = _cond(window_min=30)   # 快照里持久化的是这个窗口的 deadline
    mgr = StagedBreakManager()
    mgr.process(7, 2, cond, _quote(27.4), _ctx(), T0)
    snap = mgr.snapshot()
    mgr2 = StagedBreakManager()
    assert mgr2.restore(snap) == 1
    assert mgr2.pending() == 1
    # 恢复后窗口语义不丢：到点照样到期（deadline 来自快照，不依赖重估）
    outcome, _ = mgr2.process(7, 2, cond, _quote(27.4), _ctx(),
                              T0 + timedelta(minutes=31))
    assert outcome == OUTCOME_EXPIRED


def test_reset_daily_clears_observing():
    mgr = StagedBreakManager()
    mgr.process(1, 0, _cond(), _quote(27.4), _ctx(), T0)
    mgr.reset_daily()
    assert mgr.pending() == 0


class _FakeStore:
    def __init__(self):
        self.saved = None

    def load_staged_states(self):
        return {'1:0': {'touch_at': T0.isoformat(),
                        'deadline': (T0 + timedelta(hours=2)).isoformat(),
                        'touch_price': 27.4}}

    def save_staged_states(self, states):
        self.saved = states


def test_store_persistence_roundtrip():
    mgr = StagedBreakManager(store=_FakeStore())
    assert mgr.restore_from_store() == 1
    assert mgr.pending() == 1
    mgr.process(2, 0, _cond(), _quote(27.4), _ctx(), T0)   # 新增一条 → dirty
    assert mgr.flush() is True
    assert '2:0' in mgr._store.saved and '1:0' in mgr._store.saved
    assert mgr.flush() is False                            # 干净后不重写


def test_store_absent_is_noop():
    mgr = StagedBreakManager(store=None)
    assert mgr.restore_from_store() == 0
    mgr.process(1, 0, _cond(), _quote(27.4), _ctx(), T0)
    assert mgr.flush() is False


# ── 引擎接线（真实 tick 路径，假件）─────────────────────────

def _rule(rule_id, symbol, conds):
    return SimpleNamespace(
        id=rule_id, symbol=symbol, enabled=True, conditions=conds, context='test',
        action_hint={'trigger_level': 'L1', 'action_on_trigger': 'observe'},
        cost_price=None, active_window=None, escalation_policy={},
    )


class _FakeRuleRepo:
    def __init__(self, rules):
        self._rules = rules

    def list_enabled(self):
        return self._rules


class _FakeQuoteService:
    def __init__(self, price, prev_close=None):
        self.price = price
        self.prev_close = prev_close

    def get_realtime_quote(self, symbol):
        return SimpleNamespace(symbol=symbol, price=self.price, volume=1_000_000,
                               change_pct=None,
                               prev_close=self.prev_close or self.price * 1.02)


class _FakeTriggerRepo:
    def __init__(self):
        self.rows = []

    def record(self, **kw):
        self.rows.append(kw)
        return SimpleNamespace(id=900 + len(self.rows))


class _FakeNotifier:
    def __init__(self):
        self.calls = []
        self.trigger_repo = _FakeTriggerRepo()
        self._next_id = 100

    def notify(self, rule, condition, quote, result, **kw):
        self._next_id += 1
        self.calls.append({'rule_id': rule.id, 'message': result.message,
                           'disposition': kw.get('disposition')})
        return SimpleNamespace(id=self._next_id, notified=True)


def _engine(rules, price, now, prev_close=None):
    notifier = _FakeNotifier()
    eng = WatchEngine(_FakeRuleRepo(rules), _FakeQuoteService(price, prev_close),
                      notifier, now_fn=lambda: now)
    return eng, notifier


def test_engine_touch_is_silent_confirm_notifies():
    """触及不通知；hold 确认达标才走流水线通知——同一规则两个 tick 对比"""
    cond = _cond('hold', minutes=30)
    eng, notifier = _engine([_rule(1, '600900', [cond])], price=27.4,
                            now=T0, prev_close=28.0)
    eng.tick()
    assert notifier.calls == []                 # 触及静默
    assert eng.staged.pending() == 1
    # 31 分钟后仍在触发侧 → 确认 → 通知出门
    eng2, notifier2 = eng, notifier
    eng2.now_fn = lambda: T0 + timedelta(minutes=31)
    eng2.tick()
    assert len(notifier2.calls) == 1
    assert '伏击确认' in notifier2.calls[0]['message']


def test_engine_expired_archives_suppressed_sample():
    """窗口到期未确认：落 suppressed 归档（sample），不通知"""
    cond = _cond('hold', minutes=30, window_min=60)
    eng, notifier = _engine([_rule(1, '600900', [cond])], price=27.4,
                            now=T0, prev_close=28.0)
    eng.tick()
    assert notifier.calls == []
    eng.now_fn = lambda: T0 + timedelta(minutes=61)
    # hold 需要 30min——时长其实已够；构造「不确认」场景：价格离开过触发侧
    # （history 注入由引擎 state 管，这里直接换 reclaim 且未收复更干净）
    cond2 = _cond('reclaim', window_min=60)
    eng3, notifier3 = _engine([_rule(2, '600900', [cond2])], price=27.4,
                              now=T0, prev_close=28.0)
    eng3.tick()
    assert notifier3.calls == []
    eng3.now_fn = lambda: T0 + timedelta(minutes=61)
    events = eng3.tick()
    assert notifier3.calls == []                                  # 不通知
    archived = [r for r in notifier3.trigger_repo.rows
                if r.get('disposition_reason') == STAGED_EXPIRED_REASON]
    assert len(archived) == 1 and archived[0]['suppressed'] is True
    assert any(e.get('suppressed') for e in events)


def test_engine_staged_does_not_block_sibling_conditions():
    """同规则里 staged 与普通条件并存：普通条件照常评估触发"""
    conds = [_cond('hold', minutes=30),
             {'type': 'price_break', 'params': {'price': 27.0, 'direction': 'below'}}]
    eng, notifier = _engine([_rule(1, '600900', conds)], price=26.9,
                            now=T0, prev_close=28.0)
    eng.tick()
    # staged 触及静默；price_break 26.9 ≤ 27.0 触发（新鲜穿越）→ 一条通知
    assert len(notifier.calls) == 1
    assert eng.staged.pending() == 1
