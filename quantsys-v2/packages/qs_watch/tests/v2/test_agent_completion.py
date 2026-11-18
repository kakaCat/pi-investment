from datetime import datetime
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.v2.agent_completion import (
    AgentCompletionError,
    complete_agent_trigger,
)


class TriggerRepo:
    def __init__(self, trigger):
        self.trigger = trigger
        self.notified = []

    def get_by_id(self, trigger_id):
        return self.trigger if self.trigger and self.trigger.id == trigger_id else None

    def save_agent_response(self, trigger_id, response):
        self.trigger.agent_response = dict(response)

    def mark_notified(self, trigger_id, notified):
        self.notified.append((trigger_id, notified))
        self.trigger.notified = notified

    def update_disposition(self, trigger_id, disposition, reason, by):
        self.trigger.disposition = disposition
        self.trigger.disposition_reason = reason
        self.trigger.disposition_by = by
        return self.trigger


class RuleRepo:
    def __init__(self, rule):
        self.rule = rule

    def get_by_id(self, rule_id):
        return self.rule if self.rule and self.rule.id == rule_id else None

    def update_fields(self, rule_id, **fields):
        for key, value in fields.items():
            setattr(self.rule, key, value)
        return self.rule


def fixture_objects():
    rule = SimpleNamespace(
        id=26,
        symbol='000425.SZ',
        intent='exit_stop',
        account='agent_virtual',
        cost_price=10.0,
        invalidation_threshold_pct=20.0,
        conditions=[{'type': 'price_break', 'params': {'price': 9.0}}],
        position_state='holding',
        process_state='pending',
    )
    trigger = SimpleNamespace(
        id=88,
        rule_id=26,
        symbol='000425.SZ',
        condition=rule.conditions[0],
        trigger_price=8.8,
        detail={'intent': 'exit_stop', 'message': '下破 9.0'},
        agent_response=None,
        notified=False,
        disposition='pending',
    )
    return rule, trigger


def complete(trigger_repo, rule_repo, sent, **overrides):
    payload = {
        'action': '卖出',
        'reason': '止损线已破，先控制回撤',
        'disposition': 'handled',
        'account': 'agent_virtual',
        'qty': 1000,
        'by': 'agent-ts',
        **overrides,
    }
    return complete_agent_trigger(
        88, payload,
        trigger_repo=trigger_repo,
        rule_repo=rule_repo,
        feishu_sender=lambda title, body: sent.append((title, body)) or True,
        now=datetime(2026, 10, 27, 10, 0),
    )


def test_complete_saves_decision_sends_v2_card_and_finalizes():
    rule, trigger = fixture_objects()
    triggers, rules, sent = TriggerRepo(trigger), RuleRepo(rule), []

    result = complete(triggers, rules, sent)

    assert result['delivered'] is True
    assert result['deduplicated'] is False
    assert result['entry'] == 'after_agent'
    assert len(sent) == 1
    assert 'Agent 裁决' in sent[0][1]
    assert '卖出' in sent[0][1]
    assert '止损线已破' in sent[0][1]
    assert trigger.agent_response['notification_delivered'] is True
    assert trigger.agent_response['action'] == '卖出'
    assert trigger.disposition == 'handled'
    assert trigger.notified is True
    assert rule.process_state == 'processed'


def test_repeat_complete_does_not_send_second_card():
    rule, trigger = fixture_objects()
    triggers, rules, sent = TriggerRepo(trigger), RuleRepo(rule), []
    complete(triggers, rules, sent)

    result = complete(triggers, rules, sent)

    assert result['deduplicated'] is True
    assert len(sent) == 1
    assert rule.process_state == 'processed'


def test_send_failure_preserves_decision_but_does_not_finalize():
    rule, trigger = fixture_objects()
    triggers, rules = TriggerRepo(trigger), RuleRepo(rule)

    with pytest.raises(AgentCompletionError) as exc:
        complete_agent_trigger(
            88,
            {'action': '观察', 'reason': '等待确认', 'disposition': 'ignored'},
            trigger_repo=triggers,
            rule_repo=rules,
            feishu_sender=lambda title, body: False,
        )

    assert exc.value.status_code == 502
    assert trigger.agent_response['action'] == '观察'
    assert trigger.agent_response['notification_delivered'] is False
    assert trigger.disposition == 'pending'
    assert rule.process_state == 'pending'


def test_missing_trigger_returns_404():
    _, trigger = fixture_objects()
    with pytest.raises(AgentCompletionError) as exc:
        complete_agent_trigger(
            88, {'action': '观察', 'reason': '等待确认'},
            trigger_repo=TriggerRepo(None), rule_repo=RuleRepo(None),
            feishu_sender=lambda title, body: True,
        )
    assert exc.value.status_code == 404


@pytest.mark.parametrize('payload', [
    {'reason': '缺动作'},
    {'action': '观察'},
    {'action': '观察', 'reason': '无效状态', 'disposition': 'pending'},
])
def test_invalid_payload_returns_400(payload):
    rule, trigger = fixture_objects()
    with pytest.raises(AgentCompletionError) as exc:
        complete_agent_trigger(
            88, payload,
            trigger_repo=TriggerRepo(trigger), rule_repo=RuleRepo(rule),
            feishu_sender=lambda title, body: True,
        )
    assert exc.value.status_code == 400
