"""盯盘场景矩阵（w-aebfddcd，2026-09-11）——专找"走不通"的分支

覆盖：A 规则入场闸门 / B 引擎 tick 机制 / C 路由与授权策略 / D 摘要门投送门。
尽量复用既有测试的假件（同一套假件 = 同一套契约），只关注"这条逻辑能不能走通"。
"""
import pytest
from datetime import datetime, timedelta
from types import SimpleNamespace

from qs_notification.domain.policies.watch_channel_policy import (
    CH_DECISION_INBOX, CH_ENTRY_SIGNAL, CH_EXIT_MANAGE, CH_MARKET_STATE, CH_POSITION_OPS,
    CH_RISK_STOP, CH_RULE_GOVERNANCE, CH_SYSTEM_OPS, CH_WATCH_MARKET, CH_WATCH_SYMBOL,
    WatchChannelPolicy,
)
from qs_notification.domain.policies.watch_delivery_policy import (
    AGENT_DH, AUTONOMOUS, NOT_APPLICABLE, REMIND_ONLY, WatchDeliveryPolicy,
)
from qs_watch.domain.watch.services.disposition import TRADE_INTENTS
from qs_watch.domain.watch.services.rule_guard import (
    TradeRuleWithoutAccount, WatchRuleNotApplicable, guard_new_rule, guard_rule_change,
)
from tests.services.test_watch_engine import FakeNotifier, make_engine, make_rule, NOW
from tests.application.test_watch_digest_accounts import (
    TRADING_NOW, UNASSIGNED, _Agent, _Rule, _RuleRepo, _Trig, _TriggerRepo,
    _StateRepo as _DigestStateRepo,
)
from qs_watch.application.services.watch_engine.digest_service import WatchDigestService

PRICE_UP = lambda: {'600519.SH': 101.0}   # 上破 100 → 命中


# ── A. 规则入场闸门 ──────────────────────────────────────────────
@pytest.mark.parametrize("intent", TRADE_INTENTS)
def test_A1_trade_intent_needs_account(intent):
    with pytest.raises(TradeRuleWithoutAccount):
        guard_new_rule(intent=intent, symbol='600519.SH')
    guard_new_rule(intent=intent, account='agent_virtual', symbol='600519.SH')


def test_A2_observe_allowed_without_account():
    guard_new_rule(intent='trend_observe')


def test_A3_strategy_account_rejected_for_any_intent():
    for intent in ('trend_observe', '', 'entry'):
        with pytest.raises(WatchRuleNotApplicable):
            guard_new_rule(intent=intent, account='v13_simulation')


def test_A4_buy_hint_without_intent_is_caught():
    with pytest.raises(TradeRuleWithoutAccount):
        guard_new_rule(action_hint={'action_on_trigger': 'buy'})


def test_A5_update_cannot_smuggle_trade_rule():
    class R:
        symbol, intent, account, linked_account = '600519.SH', 'trend_observe', None, None
        action_hint, conditions = {}, []
    with pytest.raises(TradeRuleWithoutAccount):
        guard_rule_change(R(), {'intent': 'entry'})
    class R2(R):
        intent, linked_account = 'exit_stop', 'agent_virtual'
    with pytest.raises(TradeRuleWithoutAccount):
        guard_rule_change(R2(), {'linked_account': None})


# ── B. 引擎 tick 机制 ───────────────────────────────────────────
def test_B1_hit_notifies_and_event_carries_disposition():
    n = FakeNotifier()
    engine = make_engine([make_rule()], PRICE_UP(), n)
    engine.now_fn = lambda: NOW
    events = engine.tick()
    assert len(n.notifications) == 1
    assert events[0]['disposition'] and events[0]['notified'] is True


def test_B2_latch_prevents_repeat_until_rearm():
    """电平保持不重复推送；条件回落 → 重新武装后再报"""
    n = FakeNotifier()
    prices = PRICE_UP()
    engine = make_engine([make_rule()], prices, n)
    clock = {'t': NOW}
    engine.now_fn = lambda: clock['t']
    engine.tick()
    engine.tick()                       # 仍在上方 → 闩锁，不重复
    assert len(n.notifications) == 1
    clock['t'] = NOW + timedelta(minutes=20)  # 越过冷却窗，且仍在交易时段内（10:50）
    prices['600519.SH'] = 99.0          # 回落到阈值下 → 解除闩锁
    engine.tick()
    clock['t'] = NOW + timedelta(minutes=25)  # 11:10，仍在交易时段内
    prices['600519.SH'] = 101.0         # 再穿越 → 重新通知
    engine.tick()
    assert len(n.notifications) == 2


def test_B3_cooldown_suppresses_within_window():
    n = FakeNotifier()
    prices = PRICE_UP()
    engine = make_engine([make_rule()], prices, n)
    engine.now_fn = lambda: NOW
    engine.tick()
    prices['600519.SH'] = 99.0
    engine.tick()                       # 解除闩锁
    prices['600519.SH'] = 101.0
    engine.tick()                       # 同 NOW（0 秒后）→ 冷却窗内
    assert len(n.notifications) == 1, '冷却窗未生效：短时间内重复通知'


def test_B4_quote_failure_does_not_crash():
    n = FakeNotifier()
    engine = make_engine([make_rule()], {}, n)     # 无报价
    engine.now_fn = lambda: NOW
    assert engine.tick() == []
    assert n.notifications == []


def test_B5_duplicate_rules_same_event_dedup():
    """同标的同向两条规则同时命中：
      · 观察类（trend_observe → auto_observed）→ 第二条 deduped 不重复打扰（守卫内）；
      · 宪法级（exit_stop → escalated）→ **不吞消息**：第二条保留升级通道照发，
        只标注「与规则#1 同事件，合并展示」（REQ-261016155500-4f2a wt:engine:2，
        止损被吞 = 资损风险）。"""
    from tests.services.test_watch_engine import make_rule as _mk
    observe, observe2 = _mk(id=1), _mk(id=2)
    for r in (observe, observe2):                       # 观察类 → auto_observed（守卫内）
        r.intent = 'trend_observe'
        r.action_hint = {'trigger_level': 'L1', 'action_on_trigger': 'observe'}
    n = FakeNotifier()
    engine = make_engine([observe, observe2], PRICE_UP(), n)
    engine.now_fn = lambda: NOW
    events = engine.tick()
    dispositions = [e.get('disposition') for e in events]
    assert 'deduped' in dispositions, '观察类同事件重复未被去重：%s' % dispositions
    deduped = [e for e in events if e.get('disposition') == 'deduped'][0]
    assert deduped['notified'] is False

    # 宪法级：两条都 escalated，第二条带合并标注、notified=True（消息必达）
    n2 = FakeNotifier()
    rules = [make_rule(id=1), make_rule(id=2)]     # intent=exit_stop（make_rule 默认）
    engine2 = make_engine(rules, PRICE_UP(), n2)
    engine2.now_fn = lambda: NOW
    events2 = engine2.tick()
    disp2 = [e.get('disposition') for e in events2]
    assert disp2 == ['escalated', 'escalated'], '宪法级触发被吞：%s' % disp2
    second = events2[1]
    assert second['notified'] is True
    assert second['merged_from_rule'] == 1
    assert '合并展示' in (second['disposition_reason'] or '')
    assert len(n2.notifications) == 2


def test_B6_tick_self_checks_trading_hours():
    """时段自检（2026-09-11 修复）：盘后/周末直接调 tick() 不得产出事件。

    修复前：时段守卫只在 run_forever 循环里，旁路调用（补跑脚本/新服务）会在盘后推通知。
    """
    n = FakeNotifier()
    engine = make_engine([make_rule()], PRICE_UP(), n)
    engine.now_fn = lambda: datetime(2026, 7, 21, 20, 0)      # 周二晚间
    assert engine.tick() == [] and n.notifications == []
    engine.now_fn = lambda: datetime(2026, 7, 25, 10, 30)     # 周六盘中时间点
    assert engine.tick() == [] and n.notifications == []
    engine.now_fn = lambda: datetime(2026, 7, 21, 10, 30)     # 周二盘中
    assert engine.tick(), '交易时段内应正常判定'


# ── B7. 全局环境闸（2026-10-20）：环境不达标 → 个股信号只归档不动作 ──
class _ArchivingNotifier(FakeNotifier):
    """在 FakeNotifier 上加「归档口」：suppressed 归档走 trigger_repo.record。"""

    def __init__(self):
        super().__init__()
        self._seq = 0
        self.trigger_repo = self

    def record(self, **kwargs):
        self._seq += 1
        return SimpleNamespace(id=self._seq, **kwargs)


class _EnvStateProvider:
    def __init__(self, state):
        self.state = state

    def get_state(self):
        return self.state


class _EnvMarketSvc:
    def __init__(self, state):
        self.state_provider = _EnvStateProvider(state)


def test_B7_environment_gate_archives_instead_of_notifying():
    """tick 前置环境门：指数暴跌+板块无主线+资金偏冷 → 个股信号只归档。

    证伪点：通知出口为 0、日配额不被吃掉、归档行 suppressed=true 且带拦截原因。
    """
    from qs_watch.domain.watch.models import MarketState

    state = MarketState(
        indices={'000300.SH': {'change_pct': -1.80}},
        sectors={'银行': 0.30, '农林牧渔': -1.20},
        sentiment_score=18.0, advance_decline_ratio=0.30, degraded=[])
    n = _ArchivingNotifier()
    engine = make_engine([make_rule()], PRICE_UP(), n,
                         market_watch_service=_EnvMarketSvc(state))
    engine.now_fn = lambda: NOW

    events = engine.tick()

    assert n.notifications == [], '环境不达标仍发了通知'
    assert n._seq == 1, '个股信号应归档恰好一条'
    assert engine.state.daily_emit_counts == {}, '环境拦截占用了日通知配额'
    assert len(events) == 1
    ev = events[0]
    assert ev['notified'] is False and ev['suppressed'] is True
    assert '环境闸拦截' in ev['disposition_reason']
    # 同一条件持续成立：闩锁挡住，不重复归档
    engine.tick()
    assert n._seq == 1


# ── C. 路由与授权策略 ───────────────────────────────────────────
@pytest.mark.parametrize("kwargs,expected", [
    ({'intent': 'exit_stop'}, CH_RISK_STOP),
    ({'intent': 'entry'}, CH_ENTRY_SIGNAL),
    ({'intent': 'exit_take_profit'}, CH_EXIT_MANAGE),
    ({'intent': 'exit_reduce'}, CH_EXIT_MANAGE),
    ({'intent': 'add_position'}, CH_POSITION_OPS),
    ({'intent': 't_trade'}, CH_POSITION_OPS),
    ({'intent': 'trend_observe'}, CH_WATCH_SYMBOL),
    ({'intent': 'entry', 'scope': 'market'}, CH_WATCH_MARKET),
    ({'intent': 'entry', 'scope': 'sector'}, CH_WATCH_MARKET),
    ({'kind': 'system'}, CH_SYSTEM_OPS),
    ({'kind': 'decision'}, CH_DECISION_INBOX),
    ({'kind': 'market_state'}, CH_MARKET_STATE),
    ({'disposition': 'meta_review'}, CH_RULE_GOVERNANCE),
])
def test_C1_channel_routing_matrix(kwargs, expected):
    assert WatchChannelPolicy().resolve(**kwargs) == expected


def test_C2_amount_threshold_promotes_to_risk_channel():
    p = WatchChannelPolicy(amount_alerts_pct=0.05, account_total_yuan=100000.0)
    assert p.resolve(intent='entry', action_amount_yuan=6000) == CH_RISK_STOP
    assert p.resolve(intent='entry', action_amount_yuan=1000) == CH_ENTRY_SIGNAL


@pytest.mark.parametrize("account,agent,autonomy", [
    ('agent_virtual', AGENT_DH, AUTONOMOUS),
    ('agent_brain', AGENT_DH, AUTONOMOUS),
    ('user_main_simulation', AGENT_DH, REMIND_ONLY),
    ('v13_simulation', AGENT_DH, NOT_APPLICABLE),
    ('unknown_account', AGENT_DH, REMIND_ONLY),     # 兜底：授权不默认放开
    (None, AGENT_DH, REMIND_ONLY),
])
def test_C3_account_to_agent_and_authority(account, agent, autonomy):
    p = WatchDeliveryPolicy(account_overrides={}, category_overrides={}, autonomy_overrides={})
    assert p.resolve(account=account) == agent
    assert p.resolve_autonomy(account) == autonomy


# ── D. 摘要门投送门 ────────────────────────────────────────────
def _svc(agent, rules, trigs, state=None):
    return WatchDigestService(trigger_repo=_TriggerRepo(trigs), rule_repo=_RuleRepo(rules),
                              agent_service=agent, state_repo=state or _DigestStateRepo())


class _WarmState:
    """刚唤醒过（冷却窗内）"""

    def load_state(self):
        return {'last_wake_at': TRADING_NOW, 'wake_date': TRADING_NOW.date(), 'wake_count': 1}

    def save_wake(self, now):
        pass


class _CappedState:
    """当日唤醒已用满"""

    def load_state(self):
        return {'last_wake_at': None, 'wake_date': TRADING_NOW.date(), 'wake_count': 99}

    def save_wake(self, now):
        pass


def test_D1_account_segment_wakes_with_authority():
    a = _Agent()
    rules = [_Rule(1, '600519', account='agent_virtual')]
    res = _svc(a, rules, [_Trig(11, 1, '600519')]).maybe_wake(now=TRADING_NOW)
    assert res['woke'] and a.calls[0]['data']['autonomy'] == AUTONOMOUS
    assert a.calls[0]['data']['target_agent'] == AGENT_DH


def test_D2_cooldown_blocks_second_wake():
    a = _Agent()
    rules = [_Rule(1, '600519', account='agent_virtual')]
    res = _svc(a, rules, [_Trig(11, 1, '600519')], state=_WarmState()).maybe_wake(now=TRADING_NOW)
    assert res['woke'] is False
    assert '距上次唤醒' in res.get('reason', '')      # 冷却门文案
    assert a.calls == []


def test_D3_daily_cap_blocks_wake():
    a = _Agent()
    rules = [_Rule(1, '600519', account='agent_virtual')]
    res = _svc(a, rules, [_Trig(11, 1, '600519')], state=_CappedState()).maybe_wake(now=TRADING_NOW)
    assert res['woke'] is False and a.calls == []


def test_D4_strategy_account_not_delivered():
    a = _Agent()
    rules = [_Rule(9, '300224', account='v13_simulation', intent='trend_observe')]
    res = _svc(a, rules, [_Trig(19, 9, '300224')]).maybe_wake(now=TRADING_NOW)
    assert a.calls == [] and res['out_of_scope'][0]['account'] == 'v13_simulation'


def test_D5_multi_account_two_wakes_no_crosstalk():
    a = _Agent()
    rules = [_Rule(1, '600519', account='agent_virtual'),
             _Rule(2, '600036', account='user_main_simulation')]
    trigs = [_Trig(11, 1, '600519'), _Trig(12, 2, '600036')]
    res = _svc(a, rules, trigs).maybe_wake(now=TRADING_NOW)
    assert res['wakes'] == 2
    by_acct = {c['data']['account_name']: c['data'] for c in a.calls}
    assert '600036' not in by_acct['agent_virtual']['digest']
    assert by_acct['user_main_simulation']['autonomy'] == REMIND_ONLY
