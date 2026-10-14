"""tick 单链路接线测试（REQ-261007133807-eda6 t6 · FR-1、FR-2）

守三件事：
1) 每次触发的事件都带**理由码**（"为什么叫/没叫"从这条通道可查）；
2) 去重命中时**覆盖裁决但保留原判**（DEDUPED + 理由文本含「原判」）；
3) 卡面用的 `escalation_reason` 仍只承载**三条可信升级路径**的理由
   （否则预算门/观察类等"没叫"的理由会污染卡面标签与简化预案的判断）。

复用 test_watch_engine.py 的 fake 模式（同款仓储/行情/通知替身）。
"""
from datetime import datetime
from types import SimpleNamespace

from application.services.watch_engine.engine import WatchEngine
from domain.watch.services.escalation_verdict import EscalationCode

NOW = datetime(2026, 7, 21, 10, 30)  # 周二，交易时段内


def make_rule(id=1, symbol='600519.SH', conditions=None, intent='entry',
              action='buy', level='L1', policy=None, escalate=None):
    ah = {'trigger_level': level, 'action_on_trigger': action}
    if escalate is not None:
        ah['escalate'] = escalate
    return SimpleNamespace(
        id=id, symbol=symbol,
        conditions=conditions or [{'type': 'price_break',
                                   'params': {'direction': 'above', 'price': 100.0}}],
        cost_price=None, active_window=None, intent=intent, action_hint=ah,
        escalation_policy=policy, scope='symbol', linked_account=None,
        lifecycle_stage='watching', created_from=None, next_action_hint=None,
        target=None, review_interval_days=None, review_due_at=None, enabled=True,
    )


class FakeRepo:
    def __init__(self, rules):
        self._rules = rules

    def list_enabled(self):
        return list(self._rules)


class FakeQuoteService:
    def __init__(self, prices):
        self.prices = prices

    def get_realtime_quote(self, symbol):
        price = self.prices.get(symbol)
        if price is None:
            return None
        return SimpleNamespace(symbol=symbol, price=price, prev_close=98.0,
                               volume=1_000_000, change_pct=None)


class FakeNotifier:
    def __init__(self):
        self.notifications = []
        self.kwargs = []

    def notify(self, rule, condition, quote, result, **kwargs):
        self.notifications.append((rule.id, condition['type'], quote.price))
        self.kwargs.append(kwargs)
        return SimpleNamespace(id=len(self.notifications))


def make_engine(rules, prices, notifier=None, **kw):
    return WatchEngine(
        rule_repo=FakeRepo(rules),
        quote_service=FakeQuoteService(prices),
        notifier=notifier or FakeNotifier(),
        now_fn=lambda: NOW,
        **kw,
    )


def test_every_event_carries_escalation_code():
    """行动类规则过门 → 事件带 GATES_PASSED_ACTION（"为什么叫"从事件可查）。"""
    events = make_engine([make_rule()], {'600519.SH': 101.0}).tick()
    assert len(events) == 1
    assert events[0]['escalation_code'] == EscalationCode.GATES_PASSED_ACTION
    assert events[0]['escalation_reason'].strip()


def test_observe_rule_event_carries_the_not_waking_code():
    """观察类不叫 agent，但**也要有码**（成本控制不是黑盒）。"""
    events = make_engine([make_rule(intent='trend_observe', action='observe')],
                         {'600519.SH': 101.0}).tick()
    assert events[0]['escalation_code'] == EscalationCode.OBSERVE_INTENT
    assert events[0]['disposition'] == 'auto_observed'


def test_escalation_reason_still_only_carries_upgrade_path_reasons():
    """非升级路径的触发：`escalation_reason` 必须为空（否则卡面标签会误变「需决策」）。"""
    notifier = FakeNotifier()
    make_engine([make_rule()], {'600519.SH': 101.0}, notifier).tick()
    assert notifier.kwargs[0].get('escalation_reason') is None


def test_upgrade_path_trigger_keeps_reason_for_card():
    """显式升级路径命中 → `escalation_reason` 有值（卡面据此标「需决策」）。"""
    notifier = FakeNotifier()
    rule = make_rule(escalate=True)
    engine = make_engine([rule], {'600519.SH': 101.0}, notifier)
    engine.tick()
    assert notifier.kwargs[0].get('escalation_reason')
    assert '规则显式声明' in notifier.kwargs[0]['escalation_reason']


def test_dedup_override_keeps_original_verdict_in_reason():
    """真实去重场景（同标的同向两条规则一次 tick）：第二条码变 DEDUPED，
    但理由里保留「原判」——"本来会叫、被压掉了"必须可查。"""
    events = make_engine([make_rule(id=1), make_rule(id=2)],
                         {'600519.SH': 101.0}).tick()
    assert len(events) == 2
    assert events[0]['escalation_code'] == EscalationCode.GATES_PASSED_ACTION
    deduped = events[1]
    assert deduped['disposition'] == 'deduped'
    assert deduped['escalation_code'] == EscalationCode.DEDUPED
    assert '原判' in deduped['escalation_reason']
    assert '过五道门' in deduped['escalation_reason']  # 原判内容本身


def test_dedup_override_via_verdict_api_directly():
    """直接对出口产的裁决做覆盖：DEDUPED + 原判保留（不依赖引擎分支能否被触发）。"""
    from domain.watch.services.escalation_verdict import Verdict
    original = Verdict(True, EscalationCode.ANOMALY_CHANGE_PCT, '异常波动：涨跌幅 -6.10%')
    after = original.overridden(EscalationCode.DEDUPED, '去重合并（同标的同向 60s 内）')
    assert after.code == EscalationCode.DEDUPED and after.should_wake is False
    assert '原判' in after.reason and original.reason in after.reason
