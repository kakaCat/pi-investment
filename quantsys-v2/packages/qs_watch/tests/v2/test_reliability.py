"""V2 定时扫描的投递、归档和档位可靠性回归。"""
import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.v2 import scheduled, tier
from qs_watch.application.services.watch_engine.v2.engine import WatchEngineV2

NOW = datetime(2026, 10, 23, 10, 0, 0)
NEXT_DAY = datetime(2026, 10, 26, 10, 0, 0)


@pytest.fixture(autouse=True)
def _reset_and_trading_day(monkeypatch):
    scheduled.reset_latch()
    monkeypatch.setattr(scheduled, 'is_trading_day', lambda now=None: True)
    yield
    scheduled.reset_latch()


class RuleRepo:
    def __init__(self, rule):
        self.rule = rule
        self.count = 0
        self.tier_updates = []

    def list_by_state(self, state):
        return [self.rule]

    def get_cycle_count(self, rule_id):
        return self.count

    def set_cycle_count(self, rule_id, count):
        self.count = count

    def update_fields(self, rule_id, **fields):
        for key, value in fields.items():
            setattr(self.rule, key, value)
        if 'watch_tier' in fields:
            self.tier_updates.append(fields['watch_tier'])
        return self.rule


class TriggerRepo:
    def __init__(self, fail_first=False):
        self.rows = []
        self.fail_first = fail_first
        self.attempts = 0

    def record(self, **kwargs):
        self.attempts += 1
        if self.fail_first and self.attempts == 1:
            raise RuntimeError('db down')
        self.rows.append(kwargs)
        return SimpleNamespace(id=len(self.rows))

    def mark_notified(self, trigger_id, notified):
        self.rows[trigger_id - 1]['notified'] = bool(notified)


class Quotes:
    def __init__(self, symbol, price):
        self.symbol = symbol
        self.price = price

    def get_realtime_quote(self, symbol):
        if self.price is None:
            return None
        return SimpleNamespace(symbol=symbol, price=self.price, prev_close=10.0)


def make_rule(intent='entry', watch_tier=30, trigger_channel='agent', conditions=None):
    return SimpleNamespace(
        id=1,
        symbol='300750.SZ',
        intent=intent,
        conditions=conditions or [
            {'type': 'price_break', 'params': {'price': 10.0, 'direction': 'above'}}],
        position_state='holding' if intent.startswith('exit_') else 'none',
        account='acct_A',
        cost_price=10.0,
        invalidation_threshold_pct=1000.0,
        watch_tier=watch_tier,
        trigger_channel=trigger_channel,
    )


def make_engine(repo, agent_sender=None, feishu_sender=None, **kwargs):
    return WatchEngineV2(
        rule_repo=repo,
        quote_service=None,
        cycle_store=repo,
        agent_sender=agent_sender,
        feishu_sender=feishu_sender,
        account_agent_map={'acct_A': 'agent-A'},
        **kwargs,
    )


def test_failed_agent_send_retries_same_trigger_and_delays_cycle():
    rule = make_rule()
    repo = RuleRepo(rule)
    triggers = TriggerRepo()
    attempts = []

    def send(*args):
        attempts.append(args)
        return len(attempts) > 1

    engine = make_engine(repo, agent_sender=send)
    first = scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                           quote_service=Quotes(rule.symbol, 11.0),
                           trigger_repo=triggers, engine=engine)
    second = scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                            quote_service=Quotes(rule.symbol, 11.0),
                            trigger_repo=triggers, engine=engine)

    assert first['delivery_failed'] == 1
    assert repo.count == 1
    assert len(attempts) == 2
    assert len(triggers.rows) == 1
    assert triggers.rows[0]['notified'] is True
    assert second['archived'] == 0


def test_agent_call_skips_below_one_percent_and_retries_after_threshold():
    rule = make_rule()
    repo = RuleRepo(rule)
    triggers = TriggerRepo()
    agent_calls = []
    engine = make_engine(
        repo, agent_sender=lambda *args: agent_calls.append(args) or True)
    quotes = Quotes(rule.symbol, 11.0)

    first = scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                           quote_service=quotes, trigger_repo=triggers, engine=engine)
    assert first['delivery_failed'] == 0
    assert len(agent_calls) == 1
    assert repo.count == 1

    repo.count = 0  # 模拟新循环首发 agent；价格浮动不足 1% 时不得重复唤醒
    quotes.price = 11.05
    second = scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                            quote_service=quotes, trigger_repo=triggers, engine=engine)
    assert second['delivery_failed'] == 0, '业务跳过不是投递失败'
    assert len(agent_calls) == 1
    assert repo.count == 0, '未发 agent 不推进循环计数，等价格达到门槛再发'
    assert triggers.rows[0]['notified'] is True, '跳过不得覆盖既有成功投递记录'

    quotes.price = 11.11
    third = scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                           quote_service=quotes, trigger_repo=triggers, engine=engine)
    assert third['delivery_failed'] == 0
    assert len(agent_calls) == 2
    assert repo.count == 1


def test_failed_tenth_direct_does_not_reset_and_retries_same_record():
    rule = make_rule()
    repo = RuleRepo(rule)
    repo.count = 9
    triggers = TriggerRepo()
    calls = []

    def send(title, body):
        calls.append(title)
        return len(calls) > 1

    engine = make_engine(repo, feishu_sender=send)
    scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                   quote_service=Quotes(rule.symbol, 11.0),
                   trigger_repo=triggers, engine=engine)
    assert repo.count == 9
    assert triggers.rows[0]['notified'] is False

    scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                   quote_service=Quotes(rule.symbol, 11.0),
                   trigger_repo=triggers, engine=engine)
    assert repo.count == 0
    assert len(calls) == 2
    assert len(triggers.rows) == 1
    assert triggers.rows[0]['notified'] is True


def test_archive_failure_blocks_delivery_and_retries_next_scan():
    rule = make_rule()
    repo = RuleRepo(rule)
    triggers = TriggerRepo(fail_first=True)
    agent_calls = []
    engine = make_engine(
        repo, agent_sender=lambda *args: agent_calls.append(args) or True)

    first = scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                           quote_service=Quotes(rule.symbol, 11.0),
                           trigger_repo=triggers, engine=engine)
    second = scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                            quote_service=Quotes(rule.symbol, 11.0),
                            trigger_repo=triggers, engine=engine)

    assert first['archive_failed'] == 1
    assert second['archive_failed'] == 0
    assert len(agent_calls) == 1
    assert repo.count == 1
    assert len(triggers.rows) == 1
    assert triggers.rows[0]['notified'] is True


def test_condition_latch_rearms_independently():
    conditions = [
        {'type': 'price_break', 'params': {'price': 20.0, 'direction': 'above'}},
        {'type': 'price_break', 'params': {'price': 10.0, 'direction': 'above'}},
    ]
    rule = make_rule(trigger_channel='direct', conditions=conditions)
    repo = RuleRepo(rule)
    triggers = TriggerRepo()
    quotes = Quotes(rule.symbol, 21.0)
    engine = make_engine(repo, feishu_sender=lambda *args: True)

    for price in (21.0, 15.0, 21.0):
        quotes.price = price
        scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo, quote_service=quotes,
                       trigger_repo=triggers, engine=engine)

    assert len(triggers.rows) == 3


def test_missing_quote_preserves_latch_and_new_day_creates_new_record():
    rule = make_rule(trigger_channel='direct')
    repo = RuleRepo(rule)
    triggers = TriggerRepo()
    quotes = Quotes(rule.symbol, 11.0)
    engine = make_engine(repo, feishu_sender=lambda *args: True)

    scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo, quote_service=quotes,
                   trigger_repo=triggers, engine=engine)
    quotes.price = None
    scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo, quote_service=quotes,
                   trigger_repo=triggers, engine=engine)
    quotes.price = 11.0
    scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo, quote_service=quotes,
                   trigger_repo=triggers, engine=engine)
    assert len(triggers.rows) == 1

    scheduled.scan(rule.watch_tier, now=NEXT_DAY, rule_repo=repo, quote_service=quotes,
                   trigger_repo=triggers, engine=engine)
    assert len(triggers.rows) == 2


def test_slow_tier_moves_to_fast_and_completes_tenth_delivery():
    rule = make_rule(watch_tier=tier.TIER_SLOW)
    repo = RuleRepo(rule)
    triggers = TriggerRepo()
    agent_calls = []
    feishu_calls = []
    engine = make_engine(
        repo,
        agent_sender=lambda *args: agent_calls.append(args) or True,
        feishu_sender=lambda *args: feishu_calls.append(args) or True,
    )
    quotes = Quotes(rule.symbol, 20.0)

    result = scheduled.scan(tier.TIER_SLOW, now=NOW, rule_repo=repo,
                            quote_service=quotes, trigger_repo=triggers, engine=engine)
    assert result['tier_changed'] == 1
    assert rule.watch_tier == tier.TIER_FAST

    for _ in range(9):
        scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                       quote_service=quotes, trigger_repo=triggers, engine=engine)

    assert len(agent_calls) == 1
    assert len(feishu_calls) == 1
    assert repo.count == 0
    assert repo.tier_updates == [tier.TIER_FAST]


def test_direct_channel_uses_edge_without_agent_or_cycle_count():
    rule = make_rule(trigger_channel='direct')
    repo = RuleRepo(rule)
    triggers = TriggerRepo()
    agent_calls = []
    feishu_calls = []
    engine = make_engine(
        repo,
        agent_sender=lambda *args: agent_calls.append(args) or True,
        feishu_sender=lambda *args: feishu_calls.append(args) or True,
    )

    for _ in range(2):
        scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                       quote_service=Quotes(rule.symbol, 11.0),
                       trigger_repo=triggers, engine=engine)

    assert agent_calls == []
    assert len(feishu_calls) == 1
    assert repo.count == 0
    assert len(triggers.rows) == 1


def test_scheduled_delivery_contains_name_pnl_and_zero_sellable():
    rule = make_rule(intent='exit_stop', trigger_channel='direct', conditions=[
        {'type': 'price_break', 'params': {'price': 9.0, 'direction': 'below'}}])
    repo = RuleRepo(rule)
    triggers = TriggerRepo()
    messages = []
    engine = make_engine(
        repo,
        feishu_sender=lambda title, body: messages.append((title, body)) or True,
        name_resolver=lambda symbols: {rule.symbol: '宁德时代'},
        position_reader=lambda account, symbol: SimpleNamespace(shares_available=0),
    )

    scheduled.scan(rule.watch_tier, now=NOW, rule_repo=repo,
                   quote_service=Quotes(rule.symbol, 8.8),
                   trigger_repo=triggers, engine=engine)

    title, body = messages[0]
    assert '宁德时代' in title
    assert '浮亏 -12.0%' in body
    assert '可卖 0 股' in body


def test_job_reports_delivery_failure(monkeypatch):
    monkeypatch.setattr(scheduled, 'scan', lambda *args, **kwargs: {
        'delivery_failed': 1, 'archive_failed': 0})
    result = asyncio.run(scheduled.WatchScanJob(30).execute({}))
    assert result.success is False
    assert 'delivery_failed=1' in result.error
