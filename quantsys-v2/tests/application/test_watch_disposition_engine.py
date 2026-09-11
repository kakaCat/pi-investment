"""引擎级处置/去重验证（REQ-f08def，w-c8cae280）

为什么要有这层测试：单测只证明"决策函数对了"，但真正会出事的是**接线**——
tick 里到底有没有把去重结果传到通知器、通知器有没有真的不发出去。
本文件用假件跑真实 tick 路径，不加任何生产噪声。

覆盖两个真实事故形态：
1) 同规则同向多阈值（#129 挂 <9.6/<9.4）→ 一次跌穿响两次（实测间隔 0.46 秒）
2) 同标的多规则（601600 有 6 条，跨窗口/跨账户）→ 一次跌穿响 4+ 次
"""
from datetime import datetime
from types import SimpleNamespace

from application.services.watch_engine.engine import WatchEngine
from application.services.watch_engine.notifier import WatchNotifier


def _rule(rule_id, symbol, conds, level='L1', action='observe', policy=None):
    return SimpleNamespace(
        id=rule_id, symbol=symbol, enabled=True, conditions=conds, context='test',
        action_hint={'trigger_level': level, 'action_on_trigger': action},
        cost_price=None, active_window=None, escalation_policy=policy or {},
    )


class FakeRuleRepo:
    def __init__(self, rules):
        self._rules = rules

    def list_enabled(self):
        return self._rules


class FakeQuoteService:
    def __init__(self, price):
        self.price = price

    def get_realtime_quote(self, symbol):
        return SimpleNamespace(symbol=symbol, price=self.price,
                               change_pct=-1.5, volume=1_000_000,
                               prev_close=self.price * 1.02)


class FakeNotifier:
    def __init__(self):
        self.calls = []
        self._next_id = 100

    def notify(self, rule, condition, quote, result, escalation_reason=None,
               disposition=None, disposition_reason=None, dup_of=None):
        self._next_id += 1
        self.calls.append({'rule_id': rule.id, 'disposition': disposition,
                           'dup_of': dup_of, 'reason': disposition_reason})
        return SimpleNamespace(id=self._next_id, notified=(disposition != 'deduped'))


def _engine(rules, price, now=None):
    now = now or datetime(2026, 9, 11, 10, 0, 0)
    notifier = FakeNotifier()
    eng = WatchEngine(FakeRuleRepo(rules), FakeQuoteService(price), notifier,
                      now_fn=lambda: now)
    return eng, notifier


def test_same_rule_same_direction_repeats_are_deduped():
    """一次跌穿：同规则两个同向阈值 → 1 条真实通知 + 1 条去重合并"""
    conds = [{'type': 'price_break', 'params': {'price': 9.6, 'direction': 'below'}},
             {'type': 'price_break', 'params': {'price': 9.4, 'direction': 'below'}}]
    eng, notifier = _engine([_rule(129, '601600.SH', conds)], price=9.38)
    eng.tick()
    dispositions = sorted(c['disposition'] for c in notifier.calls)
    assert dispositions == ['auto_observed', 'deduped'], notifier.calls
    duped = [c for c in notifier.calls if c['disposition'] == 'deduped'][0]
    assert duped['dup_of'], '去重必须记录被合并到哪条触发'


def test_cross_rule_same_symbol_same_direction_is_deduped():
    """601600 六条规则的形态：同标的同向的第二条规则不再重复通知"""
    cond = [{'type': 'price_break', 'params': {'price': 9.4, 'direction': 'below'}}]
    eng, notifier = _engine([
        _rule(129, '601600.SH', cond),
        _rule(131, '601600', cond),
        _rule(130, '601600', cond),
    ], price=9.38)
    eng.tick()
    dispositions = [c['disposition'] for c in notifier.calls]
    assert dispositions.count('auto_observed') == 1, dispositions
    assert dispositions.count('deduped') == 2, dispositions


def test_opposite_direction_is_not_deduped():
    """上破与下破是两件事，不得互相吞掉"""
    conds = [{'type': 'price_break', 'params': {'price': 9.4, 'direction': 'below'}},
             {'type': 'price_break', 'params': {'price': 9.35, 'direction': 'above'}}]
    eng, notifier = _engine([_rule(129, '601600', conds)], price=9.38)
    eng.tick()
    assert [c['disposition'] for c in notifier.calls] == ['auto_observed', 'auto_observed']


def test_dedup_window_expires_between_ticks():
    """跨过去重窗的真实二次破位必须照常通知（否则会吞掉真信号）"""
    cond = [{'type': 'price_break', 'params': {'price': 9.4, 'direction': 'below'}}]
    now = [datetime(2026, 9, 11, 10, 0, 0)]
    notifier = FakeNotifier()
    eng = WatchEngine(FakeRuleRepo([_rule(131, '601600', cond)]),
                      FakeQuoteService(9.38), notifier, now_fn=lambda: now[0])
    eng.tick()
    # 条件持续成立 → 闩锁不重复报；先让条件回到未触发态重新武装
    eng.quote_service.price = 9.60
    now[0] = datetime(2026, 9, 11, 10, 0, 30)
    eng.tick()
    now[0] = datetime(2026, 9, 11, 10, 5, 0)   # 超过 60s 去重窗
    eng.quote_service.price = 9.38
    eng.tick()
    assert [c['disposition'] for c in notifier.calls] == ['auto_observed', 'auto_observed']


def test_l2_rule_escalates_to_agent_queue():
    cond = [{'type': 'price_break', 'params': {'price': 70.0, 'direction': 'below'}}]
    eng, notifier = _engine([_rule(900, '601138', cond, level='L2', action='buy')], price=62.5)
    eng.tick()
    assert notifier.calls[0]['disposition'] == 'escalated'


# ── 通知器去重短路：确保"合并不等于少记一条账"─────────────────────────
class FakeTriggerRepo:
    def __init__(self):
        self.recorded = []

    def record(self, **kwargs):
        self.recorded.append(kwargs)
        return SimpleNamespace(id=len(self.recorded), **kwargs)


class FakeFacade:
    def __init__(self):
        self.sent = 0

    def send_watch_triggered(self, **kwargs):
        self.sent += 1
        return SimpleNamespace(success=True)


def test_notifier_skips_channel_but_still_records_when_deduped():
    repo = FakeTriggerRepo()
    facade = FakeFacade()
    notifier = WatchNotifier(trigger_repo=repo, notification_facade=facade, ws_url=None)
    rule = _rule(129, '601600.SH', [{'type': 'price_break',
                                     'params': {'price': 9.4, 'direction': 'below'}}])
    quote = SimpleNamespace(symbol='601600.SH', price=9.38, prev_close=9.6, name='中国铝业')
    result = SimpleNamespace(value=9.38, message='现价 9.38 ≤ 阈值 9.4（下破）')

    notifier.notify(rule, rule.conditions[0], quote, result,
                    disposition='deduped', disposition_reason='测试去重', dup_of=42)

    assert facade.sent == 0, '去重触发不得再发消息（噪声治理的核心）'
    assert len(repo.recorded) == 1, '去重触发仍须落库，账不能少'
    assert repo.recorded[0]['notified'] is False
    assert repo.recorded[0]['disposition'] == 'deduped'
    assert repo.recorded[0]['dup_of'] == 42


def test_notifier_skips_channel_for_auto_observed():
    """P8：观察类（auto_observed）不即时推送，但必须落库（账不丢）"""
    repo = FakeTriggerRepo()
    facade = FakeFacade()
    notifier = WatchNotifier(trigger_repo=repo, notification_facade=facade, ws_url=None)
    rule = _rule(120, "600150", [{"type": "price_break",
                                  "params": {"price": 39.25, "direction": "below"}}])
    quote = SimpleNamespace(symbol="600150", price=39.0, prev_close=40.0, name="中国船舶")
    result = SimpleNamespace(value=39.0, message="现价 39.0 ≤ 阈值 39.25（下破）")

    notifier.notify(rule, rule.conditions[0], quote, result,
                    disposition="auto_observed", disposition_reason="观察类（意图门）")

    assert facade.sent == 0, "观察类不得即时推送（进了日终汇总就不该打扰）"
    assert len(repo.recorded) == 1, "观察类仍须落库，账不能丢"
    assert repo.recorded[0]["notified"] is False
    assert repo.recorded[0]["disposition"] == "auto_observed"