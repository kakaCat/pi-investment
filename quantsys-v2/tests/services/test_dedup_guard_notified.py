"""dedup 守卫 + notified 口径 + 先落库后发送（REQ-261016155500-4f2a wt:engine:2）

验收锚点：
  · 同标的同向 60s 内双规则触发、后响者为止损级（escalated）→ 消息必达 + 合并标注；
  · 发送失败 → 同一条 trigger 补发（不新建不双发），notified 如实回写；
  · auto_observed 实际已推送 → events.notified=True（口径与真实发送一致）。
"""
from datetime import datetime
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.engine import WatchEngine
from qs_watch.application.services.watch_engine.notifier import WatchNotifier

NOW = datetime(2026, 7, 21, 10, 30)


def _rule(rid, intent='exit_stop', action_on_trigger='sell', trigger_level='L2'):
    return SimpleNamespace(
        id=rid, symbol='002007',
        conditions=[{'type': 'price_break',
                     'params': {'direction': 'below', 'price': 12.85}}],
        cost_price=13.27, active_window=None, intent=intent,
        action_hint={'trigger_level': trigger_level, 'action_on_trigger': action_on_trigger},
        escalation_policy=None, scope='symbol', linked_account=None,
        lifecycle_stage='watching', created_from=None, next_action_hint=None,
        target=None, review_interval_days=None, review_due_at=None, enabled=True,
        action_params=None, ops_notes=None,
    )


class _Repo:
    def __init__(self, rules):
        self._rules = rules

    def list_enabled(self):
        return list(self._rules)


class _Quotes:
    def __init__(self, price):
        self.price = price

    def get_realtime_quote(self, symbol):
        return SimpleNamespace(symbol=symbol, price=self.price, prev_close=13.10,
                               volume=1_000_000, change_pct=None)


class _Notifier:
    """记录调用 + 可编排 notified 结果（模拟送达/失败）。"""

    def __init__(self, notified=True):
        self.calls = []
        self._seq = 0
        self._notified = notified

    def notify(self, rule, condition, quote, result, **kwargs):
        self._seq += 1
        self.calls.append({'rule_id': rule.id, **kwargs})
        return SimpleNamespace(id=self._seq, notified=self._notified)

    def record_governance(self, rule, reason, detail=None):
        return None


def _engine(rules, price, notifier, clock=None):
    clock = clock or {'now': NOW}
    return WatchEngine(rule_repo=_Repo(rules), quote_service=_Quotes(price),
                       notifier=notifier, now_fn=lambda: clock['now'])


def test_stop_loss_not_swallowed_by_dedup():
    """宪法级（exit_stop/escalated）后响者不被 dedup 吞掉：照发 + 合并标注。"""
    notifier = _Notifier(notified=True)
    engine = _engine([_rule(1), _rule(2)], 12.80, notifier)
    events = engine.tick()

    assert [e['disposition'] for e in events] == ['escalated', 'escalated']
    second = events[1]
    assert second['notified'] is True
    assert second['merged_from_rule'] == 1
    assert '合并展示' in (second['disposition_reason'] or '')
    # notifier 收到 merged_from_rule 透传（渲染层标注的数据源）
    assert notifier.calls[1]['merged_from_rule'] == 1
    assert notifier.calls[0]['merged_from_rule'] is None


def test_notified_flag_matches_real_send_result():
    """口径修复：auto_observed 实际推送 → events.notified=True（此前恒 False 撒谎）。"""
    notifier = _Notifier(notified=True)
    observe = _rule(1, intent='trend_observe', action_on_trigger='observe',
                    trigger_level='L1')
    engine = _engine([observe], 12.80, notifier)
    events = engine.tick()
    assert events[0]['disposition'] == 'auto_observed'
    assert events[0]['notified'] is True


def test_unsent_trigger_not_latched_and_resends_same_row():
    """发送失败：不闩锁 → 下 tick 重判 → notify 补发短路命中同一条 trigger（不双发）。"""
    clock = {'now': NOW}
    # 第 1 轮失败、第 2 轮成功的 notifier
    notifier = _Notifier(notified=False)

    class _Repo2:
        def __init__(self):
            self.rows = []

        def record(self, **kwargs):
            row = SimpleNamespace(id=len(self.rows) + 1, **kwargs)
            self.rows.append(row)
            return row

        def mark_notified(self, trigger_id, notified):
            self.rows[trigger_id - 1].notified = bool(notified)

        def latest_unsent(self, rule_id):
            for row in reversed(self.rows):
                if row.rule_id == rule_id and not row.notified:
                    return row
            return None

    class _Notifier2:
        """真 WatchNotifier：先落库后发送；facade 首调失败、重调成功。"""

        def __init__(self, repo):
            self.attempts = 0
            self.facade_calls = 0
            trigger_repo = repo

            class _Facade:
                def send_watch_triggered(self, **kwargs):
                    self_.facade_calls += 1
                    ok = self_.facade_calls >= 2       # 第 1 次失败，第 2 次成功
                    return SimpleNamespace(success=ok)

            self_ = self
            self._notifier = WatchNotifier(
                trigger_repo=trigger_repo,
                notification_facade=_Facade(),
                ws_url=None,
            )
            self.repo = repo

        def notify(self, rule, condition, quote, result, **kwargs):
            return self._notifier.notify(rule, condition, quote, result, **kwargs)

        def record_governance(self, rule, reason, detail=None):
            return None

    repo = _Repo2()
    notifier2 = _Notifier2(repo)
    engine = WatchEngine(rule_repo=_Repo([_rule(1)]), quote_service=_Quotes(12.80),
                         notifier=notifier2, now_fn=lambda: clock['now'])
    events1 = engine.tick()
    # 第 1 轮：落库 notified=False、发送失败 → 事件如实 False、不闩锁
    assert events1[0]['notified'] is False
    assert len(repo.rows) == 1

    # 第 2 轮（1 分钟后）：重判 → notify 补发短路 → 同一行重发成功
    clock['now'] = NOW.replace(minute=31)
    events2 = engine.tick()
    assert len(repo.rows) == 1, '补发不得新建 trigger 行（双发）'
    assert repo.rows[0].notified is True
    assert notifier2.facade_calls == 2
