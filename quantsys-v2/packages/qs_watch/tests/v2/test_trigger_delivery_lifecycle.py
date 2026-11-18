"""#4786 回归：同一持久 trigger 的投递生命周期与重启恢复。"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.v2 import scheduled
from qs_watch.application.services.watch_engine.v2.archive import condition_key, reset_latch
from qs_watch.application.services.watch_engine.v2.engine import WatchEngineV2

NOW = datetime(2026, 11, 18, 10, 0, 0)


@pytest.fixture(autouse=True)
def _clean_latch(monkeypatch):
    reset_latch()
    monkeypatch.setattr(scheduled, 'is_trading_day', lambda now=None: True)
    yield
    reset_latch()


class RuleRepo:
    def __init__(self, rule):
        self.rule = rule
        self.count = 0

    def list_by_state(self, state):
        return [self.rule]

    def get_cycle_count(self, rule_id):
        return self.count

    def set_cycle_count(self, rule_id, count):
        self.count = count

    def update_fields(self, rule_id, **fields):
        for key, value in fields.items():
            setattr(self.rule, key, value)
        return self.rule


class TriggerRepo:
    def __init__(self):
        self.rows = []
        self.restore_calls = 0

    def record(self, **kwargs):
        row = SimpleNamespace(
            id=len(self.rows) + 1,
            triggered_at=NOW,
            suppressed=False,
            **kwargs,
        )
        self.rows.append(row)
        return row

    def get_by_id(self, trigger_id):
        return next((row for row in self.rows if row.id == trigger_id), None)

    def find_latest_for_condition(self, rule_id, condition, since, engine='v2'):
        self.restore_calls += 1
        rows = [
            row for row in self.rows
            if row.rule_id == rule_id
            and condition_key(row.condition) == condition_key(condition)
            and row.triggered_at >= since
            and row.engine == engine
            and not row.suppressed
        ]
        return max(rows, key=lambda row: row.id) if rows else None

    def mark_notified(self, trigger_id, notified):
        self.get_by_id(trigger_id).notified = bool(notified)


class Quotes:
    def __init__(self, symbol, price):
        self.symbol = symbol
        self.price = price

    def get_realtime_quote(self, symbol):
        return SimpleNamespace(symbol=symbol, price=self.price, prev_close=10.0)


def make_rule(trigger_channel='agent', cooldown=None):
    condition = {'type': 'price_break', 'params': {'price': 10.0, 'direction': 'above'}}
    if cooldown is not None:
        condition['cooldown_sec'] = cooldown
    return SimpleNamespace(
        id=386,
        symbol='688825.SH',
        intent='entry',
        conditions=[condition],
        position_state='none',
        account='acct_A',
        cost_price=10.0,
        invalidation_threshold_pct=1000.0,
        watch_tier=30,
        trigger_channel=trigger_channel,
    )


def make_engine(repo, agent_sender=None, feishu_sender=None):
    return WatchEngineV2(
        rule_repo=repo,
        quote_service=None,
        cycle_store=repo,
        agent_sender=agent_sender,
        feishu_sender=feishu_sender,
        account_agent_map={'acct_A': 'agent-A'},
    )


def scan(rule, repo, triggers, engine, quotes, now=NOW):
    return scheduled.scan(
        rule.watch_tier,
        now=now,
        rule_repo=repo,
        quote_service=quotes,
        trigger_repo=triggers,
        engine=engine,
    )


def test_first_agent_success_then_100_ticks_have_no_agent_or_feishu_repeat():
    rule = make_rule()
    repo, triggers = RuleRepo(rule), TriggerRepo()
    agent_calls, feishu_calls = [], []
    engine = make_engine(
        repo,
        agent_sender=lambda *args: agent_calls.append(args) or True,
        feishu_sender=lambda *args: feishu_calls.append(args) or True,
    )
    quotes = Quotes(rule.symbol, 11.0)

    for _ in range(101):  # 首次成功 + 后续 100 拍
        scan(rule, repo, triggers, engine, quotes)

    assert len(agent_calls) == 1
    assert len(feishu_calls) == 0
    assert len(triggers.rows) == 1
    assert triggers.rows[0].notified is True


def test_first_direct_success_then_100_ticks_have_no_repeat():
    rule = make_rule(trigger_channel='direct')
    repo, triggers = RuleRepo(rule), TriggerRepo()
    agent_calls, feishu_calls = [], []
    engine = make_engine(
        repo,
        agent_sender=lambda *args: agent_calls.append(args) or True,
        feishu_sender=lambda *args: feishu_calls.append(args) or True,
    )
    quotes = Quotes(rule.symbol, 11.0)

    for _ in range(101):
        scan(rule, repo, triggers, engine, quotes)

    assert len(agent_calls) == 0
    assert len(feishu_calls) == 1
    assert len(triggers.rows) == 1
    assert triggers.rows[0].notified is True


@pytest.mark.parametrize('terminal', [
    'ignored', 'handled', 'expired', 'auto_observed', 'filtered', 'deduped', 'legacy_unknown',
])
def test_terminal_disposition_hard_stops_unnotified_active_trigger(terminal):
    rule = make_rule()
    repo, triggers = RuleRepo(rule), TriggerRepo()
    attempts = []

    def fail_once(*args):
        attempts.append(args)
        return False

    engine = make_engine(repo, agent_sender=fail_once)
    quotes = Quotes(rule.symbol, 11.0)
    scan(rule, repo, triggers, engine, quotes)
    assert len(attempts) == 1
    assert triggers.rows[0].notified is False

    # 模拟 watch_resolve/其他进程已经结案；本进程闩锁必须读库跟进，而非继续重试。
    triggers.rows[0].disposition = terminal
    for _ in range(100):
        scan(rule, repo, triggers, engine, quotes)

    assert len(attempts) == 1
    assert len(triggers.rows) == 1


def test_failed_first_delivery_retries_same_trigger_then_success_stops_it():
    rule = make_rule()
    repo, triggers = RuleRepo(rule), TriggerRepo()
    attempts = []

    def fail_then_succeed(*args):
        attempts.append(args)
        return len(attempts) > 1

    engine = make_engine(repo, agent_sender=fail_then_succeed)
    quotes = Quotes(rule.symbol, 11.0)
    scan(rule, repo, triggers, engine, quotes)
    scan(rule, repo, triggers, engine, quotes)
    scan(rule, repo, triggers, engine, quotes)

    assert len(attempts) == 2
    assert len(triggers.rows) == 1
    assert triggers.rows[0].notified is True


def test_restart_restores_notified_trigger_without_duplicate_notification():
    rule = make_rule()
    repo, triggers = RuleRepo(rule), TriggerRepo()
    calls = []
    quotes = Quotes(rule.symbol, 11.0)
    engine = make_engine(repo, agent_sender=lambda *args: calls.append(args) or True)
    scan(rule, repo, triggers, engine, quotes)
    assert len(calls) == 1

    before_restart = triggers.restore_calls
    reset_latch()  # 模拟进程重启：所有内存闩锁丢失，持久 trigger 仍在
    restarted = make_engine(repo, agent_sender=lambda *args: calls.append(args) or True)
    scan(rule, repo, triggers, restarted, quotes)

    assert triggers.restore_calls == before_restart + 1
    assert len(calls) == 1
    assert len(triggers.rows) == 1


def test_restart_restores_failed_trigger_and_allows_retry():
    rule = make_rule()
    repo, triggers = RuleRepo(rule), TriggerRepo()
    calls = []
    quotes = Quotes(rule.symbol, 11.0)
    failed = make_engine(repo, agent_sender=lambda *args: calls.append(args) or False)
    scan(rule, repo, triggers, failed, quotes)

    reset_latch()
    restarted = make_engine(repo, agent_sender=lambda *args: calls.append(args) or True)
    scan(rule, repo, triggers, restarted, quotes)

    assert len(calls) == 2
    assert len(triggers.rows) == 1
    assert triggers.rows[0].notified is True


def test_hysteresis_reuses_trigger_and_true_rearm_new_edge_creates_new_one():
    rule = make_rule()
    repo, triggers = RuleRepo(rule), TriggerRepo()
    calls = []
    quotes = Quotes(rule.symbol, 11.0)
    engine = make_engine(repo, agent_sender=lambda *args: calls.append(args) or True)

    scan(rule, repo, triggers, engine, quotes)
    quotes.price = 9.98  # above 阈值为 10；仍在 0.5%/最小 0.05 迟滞带内
    scan(rule, repo, triggers, engine, quotes)
    quotes.price = 10.02
    scan(rule, repo, triggers, engine, quotes)
    assert len(triggers.rows) == 1
    assert len(calls) == 1

    quotes.price = 9.8  # 跌破 rearm 边界 9.95，旧事件正式退出
    scan(rule, repo, triggers, engine, quotes)
    quotes.price = 11.1  # 真正的新边沿
    scan(rule, repo, triggers, engine, quotes)

    assert len(triggers.rows) == 2
    assert triggers.rows[0].id != triggers.rows[1].id
    assert len(calls) == 2


def test_cooldown_sec_throttles_failed_retry_but_does_not_block_first_attempt():
    rule = make_rule(cooldown=60)
    repo, triggers = RuleRepo(rule), TriggerRepo()
    calls = []

    def fail_then_succeed(*args):
        calls.append(args)
        return len(calls) > 1

    engine = make_engine(repo, agent_sender=fail_then_succeed)
    quotes = Quotes(rule.symbol, 11.0)
    scan(rule, repo, triggers, engine, quotes, now=NOW)
    cooled = scan(rule, repo, triggers, engine, quotes, now=NOW + timedelta(seconds=30))
    retried = scan(rule, repo, triggers, engine, quotes, now=NOW + timedelta(seconds=61))

    assert len(calls) == 2
    assert cooled['delivery_failed'] == 0, '冷却中的刻意跳过不是发送失败'
    assert retried['delivery_failed'] == 0
    assert len(triggers.rows) == 1
    assert triggers.rows[0].notified is True


def test_restore_read_failure_does_not_create_or_deliver_duplicate():
    class BrokenRestoreRepo(TriggerRepo):
        def find_latest_for_condition(self, **kwargs):
            raise RuntimeError('db down')

    rule = make_rule()
    repo, triggers = RuleRepo(rule), BrokenRestoreRepo()
    calls = []
    engine = make_engine(repo, agent_sender=lambda *args: calls.append(args) or True)

    result = scan(rule, repo, triggers, engine, Quotes(rule.symbol, 11.0))

    assert result['archive_failed'] == 1
    assert calls == []
    assert triggers.rows == []
