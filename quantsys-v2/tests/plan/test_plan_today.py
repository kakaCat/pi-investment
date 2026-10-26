"""今日计划聚合视图测试（t7 · IF-10）"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from qs_plan.application.plan_aggregator import PlanAggregator

NOW = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)


def _plan(pid=1, status='active'):
    return SimpleNamespace(
        id=pid, account='agent_brain', name='p%d' % pid, status=status, version=2,
        horizon='day', review_due_at=None, reflection_overdue_count=0,
        spec={'targets': [{'symbol': '600519.SH', 'budget_pct': 5, 'role': 'core'}],
              'entry': {'conditions': [], 'combinator': 'all_of'},
              'exit': {'stop_loss': {'type': 'pct', 'value': 8}}})


class FakeRepo:
    def __init__(self, plans):
        self.plans = plans

    def list_plans(self, account, statuses=None):
        return [p for p in self.plans if statuses is None or p.status in statuses]


class TestTodayView:
    def _agg(self, **kw):
        kw.setdefault('now_fn', lambda: NOW)
        return PlanAggregator(FakeRepo(kw.pop('plans', [])), **kw)

    def test_empty_returns_200_shape(self):
        out = self._agg(plans=[]).build('agent_brain')
        assert out['empty'] is True and out['plans'] == []
        assert 'note' in out

    def test_plan_with_targets_and_env(self):
        agg = PlanAggregator(
            FakeRepo([_plan()]),
            env_gate_provider=lambda: {'status': 'blocked', 'reason': '指数 -2% 本轮只记录不动作'},
            position_provider=lambda a, s: 'holding',
            todo_provider=lambda a: 3,
            now_fn=lambda: NOW)
        out = agg.build('agent_brain')
        assert out['empty'] is False
        item = out['plans'][0]
        assert item['plan']['id'] == 1 and item['plan']['status'] == 'active'
        assert item['targets'][0] == {'symbol': '600519.SH', 'budget_pct': 5,
                                      'role': 'core', 'position': 'holding'}
        assert item['env_gate']['status'] == 'blocked'
        assert item['pending_todos'] == 3

    def test_missing_sources_degrade_not_fake_zero(self):
        agg = PlanAggregator(FakeRepo([_plan()]), now_fn=lambda: NOW)
        item = agg.build('agent_brain')['plans'][0]
        assert item['env_gate']['status'] == 'skipped'
        assert item['targets'][0]['position'] is None
        assert item['pending_todos'] is None

    def test_provider_exception_fails_open(self):
        def boom():
            raise RuntimeError('down')
        agg = PlanAggregator(FakeRepo([_plan()]), env_gate_provider=boom,
                             position_provider=lambda a, s: (_ for _ in ()).throw(RuntimeError()),
                             now_fn=lambda: NOW)
        item = agg.build('agent_brain')['plans'][0]
        assert item['env_gate']['status'] == 'skipped'
        assert item['targets'][0]['position'] is None

    def test_only_live_statuses_listed(self):
        agg = PlanAggregator(FakeRepo([_plan(1, 'active'), _plan(2, 'draft'),
                                       _plan(3, 'closed')]), now_fn=lambda: NOW)
        out = agg.build('agent_brain')
        assert [i['plan']['id'] for i in out['plans']] == [1]
