from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.meta_review_service import (
    WatchMetaReviewService,
)
from qs_watch.application.services.watch_engine.todo_service import TodoService


NOW = datetime(2026, 10, 26, 10, 0)


class RuleRepo:
    def __init__(self):
        self.rule = SimpleNamespace(
            id=7,
            symbol='300750.SZ',
            intent='trend_observe',
            linked_account='agent_virtual',
            created_at=NOW - timedelta(days=30),
            last_reviewed_at=None,
            expires_at=None,
            created_from=None,
            created_by=None,
        )
        self.updates = []

    def list_enabled(self):
        return [self.rule]

    def update_fields(self, rule_id, **fields):
        self.updates.append((rule_id, fields))


class TriggerRepo:
    def __init__(self):
        self.trigger = None

    def get_rule_trigger_stats(self):
        return {}

    def record(self, **fields):
        self.trigger = SimpleNamespace(id=91, todo_id=None, **fields)
        return self.trigger

    def set_todo_id(self, trigger_id, todo_id):
        assert trigger_id == self.trigger.id
        self.trigger.todo_id = todo_id


class TodoRepo:
    def __init__(self):
        self.fields = None
        self.todo = None

    def create(self, **fields):
        self.fields = fields
        self.todo = SimpleNamespace(id=501, **fields)
        return self.todo


def test_meta_review_creates_traceable_todo_and_assigns_agent():
    rules = RuleRepo()
    triggers = TriggerRepo()
    todos = TodoRepo()
    assigned = []
    service = WatchMetaReviewService(
        rules, triggers, todo_service=TodoService(todos, assigner=assigned.append))

    result = service.scan(NOW)

    assert result['raised'] == 1
    assert result['details'][0]['todo_id'] == 501
    assert todos.fields['level'] == 'P2'
    assert todos.fields['action_kind'] == 'rule_change'
    assert todos.fields['rule_id'] == 7
    assert todos.fields['trigger_id'] == 91
    assert todos.fields['account'] == 'agent_virtual'
    assert todos.fields['evidence']['source'] == 'meta_review'
    assert todos.fields['due_at'] == datetime(2026, 10, 26, 15, 0)
    assert todos.fields['sla_seconds'] == 5 * 60 * 60
    assert triggers.trigger.todo_id == 501
    assert assigned == [todos.todo]


def test_regular_traceable_todo_does_not_assign_twice_by_default():
    todos = TodoRepo()
    assigned = []
    service = TodoService(todos, assigner=assigned.append)

    service.create(
        '300750.SZ', level='P2', sla_seconds=60, due_at=NOW,
        account='agent_virtual', rule_id=7, trigger_id=91,
        action_kind='rule_change')

    assert assigned == []


def test_meta_review_without_todo_service_keeps_trigger_fallback():
    triggers = TriggerRepo()
    service = WatchMetaReviewService(RuleRepo(), triggers)

    result = service.scan(NOW)

    assert result['raised'] == 1
    assert result['details'][0]['todo_id'] is None
    assert triggers.trigger.disposition == 'meta_review'
    assert triggers.trigger.todo_id is None


def test_meta_review_todo_failure_does_not_abort_scan():
    triggers = TriggerRepo()

    class BrokenTodoService:
        def create(self, *args, **kwargs):
            raise RuntimeError('todo unavailable')

    service = WatchMetaReviewService(
        RuleRepo(), triggers, todo_service=BrokenTodoService())

    result = service.scan(NOW)

    assert result['raised'] == 1
    assert result['details'][0]['todo_id'] is None
    assert triggers.trigger.disposition == 'meta_review'
    assert triggers.trigger.todo_id is None


@pytest.mark.parametrize('now, expected', [
    (datetime(2026, 10, 26, 10, 0), datetime(2026, 10, 26, 15, 0)),
    (datetime(2026, 10, 26, 15, 1), datetime(2026, 10, 26, 15, 2)),
])
def test_p2_due_uses_close_or_one_minute_after_late_creation(now, expected):
    from qs_watch.application.services.watch_engine.todo_deadline import p2_due

    due_at, sla_seconds = p2_due(now)

    assert due_at == expected
    assert sla_seconds == int((expected - now).total_seconds())
