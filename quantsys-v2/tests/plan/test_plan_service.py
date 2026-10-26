"""PlanService 单元测试（t4 验收：假件仓储，不连库）"""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from qs_plan.application.plan_service import (
    DECISION_AUDIT_REQUIRED, PLAN_CHANGE_LOCKED, PLAN_SPEC_INVALID, PLAN_STATE_ILLEGAL,
    VERSION_CONFLICT, PlanError, PlanService,
)

NOW = datetime(2026, 10, 22, 2, 0, tzinfo=timezone.utc)


def _spec(stop=8.0, symbol='600519.SH'):
    return {
        'targets': [{'symbol': symbol, 'budget_pct': 5, 'role': 'core'}],
        'entry': {'conditions': [{'type': 'price_break', 'params': {'price': 10}}],
                  'combinator': 'all_of'},
        'exit': {'stop_loss': {'type': 'pct', 'value': stop}},
        'monitoring': {'news': True},
        'schedule': {'interval_sec': 30},
    }


class FakeRepo:
    def __init__(self, plan):
        self.plan = plan
        self.versions = [SimpleNamespace(version=1, spec=plan.spec,
                                         window_ends_at=None)]
        self.events = []

    def get_plan(self, plan_id):
        return self.plan if plan_id == self.plan.id else None

    def list_plans(self, account, statuses=None):
        return [self.plan]

    def create_plan(self, account, name, horizon, spec, created_by, actor=None):
        self.plan = SimpleNamespace(id=1, account=account, name=name, horizon=horizon,
                                    status='draft', spec=spec, draft_spec=None, version=1,
                                    stats={}, activated_at=None, closed_at=None,
                                    reflection_overdue_count=0)
        return self.plan

    def update_draft_spec(self, plan_id, draft_spec, expected_version):
        if self.plan.version != expected_version:
            return False
        self.plan.draft_spec = draft_spec
        return True

    def apply_version(self, plan_id, expected_version, spec, baseline=None,
                      window_days=10, change_reason=None, hypothesis=None,
                      created_by='agent', decision_audit_id=None, to_status=None):
        if self.plan.version != expected_version:
            return None
        self.plan.version += 1
        self.plan.spec = spec
        self.plan.draft_spec = None
        self.versions.insert(0, SimpleNamespace(
            version=self.plan.version, spec=spec,
            window_ends_at=(NOW.date() + timedelta(days=window_days))))
        return self.plan.version

    def transition_status(self, plan_id, to_status, actor, reason=None,
                          decision_audit_id=None, expected_version=None,
                          extra_fields=None):
        if expected_version is not None and self.plan.version != expected_version:
            return False
        self.events.append((self.plan.status, to_status, reason))
        self.plan.status = to_status
        for k, v in (extra_fields or {}).items():
            setattr(self.plan, k, v)
        return True

    def list_versions(self, plan_id, limit=50):
        return self.versions[:limit]


def _service(repo, has_position=False):
    return PlanService(repo, now_fn=lambda: NOW,
                       position_provider=lambda account, symbol: has_position)


def _plan(status='draft', spec=None):
    return SimpleNamespace(id=1, account='agent_brain', name='p', horizon='day',
                           status=status, spec=spec or _spec(), draft_spec=None,
                           version=1, stats={'hit_rate': 0.4, 'pnl': -1200},
                           activated_at=None, closed_at=None,
                           reflection_overdue_count=0)


class TestCreateAndPatch:
    def test_create_rejects_invalid_spec(self):
        svc = _service(FakeRepo(_plan()))
        with pytest.raises(PlanError) as ei:
            svc.create(account='a', name='p', horizon='day', spec={'targets': []},
                       created_by='agent', actor='agent')
        assert ei.value.code == PLAN_SPEC_INVALID

    def test_patch_requires_audit_for_agent(self):
        svc = _service(FakeRepo(_plan()))
        with pytest.raises(PlanError) as ei:
            svc.patch(1, 1, {'exit': {'stop_loss': {'type': 'pct', 'value': 10}}},
                      reason='x', actor='agent')
        assert ei.value.code == DECISION_AUDIT_REQUIRED

    def test_patch_returns_diff_preview(self):
        svc = _service(FakeRepo(_plan()))
        out = svc.patch(1, 1, {'exit': {'stop_loss': {'type': 'pct', 'value': 10}}},
                        reason='止损太紧', actor='agent', decision_audit_id='d-1')
        paths = {d['path'] for d in out['diff']}
        assert 'exit.stop_loss.value' in paths
        assert out['diff'][0]['from'] == 8.0 and out['diff'][0]['to'] == 10

    def test_patch_version_conflict(self):
        svc = _service(FakeRepo(_plan()))
        with pytest.raises(PlanError) as ei:
            svc.patch(1, 9, {'exit': {'stop_loss': {'type': 'pct', 'value': 10}}},
                      reason='x', actor='user')
        assert ei.value.code == VERSION_CONFLICT


class TestApplyDiscipline:
    def _pending(self, repo):
        repo.plan.draft_spec = _spec(stop=10.0)
        return _service(repo)

    def test_apply_without_draft_rejected(self):
        svc = _service(FakeRepo(_plan()))
        with pytest.raises(PlanError) as ei:
            svc.apply(1, 1, actor='user')
        assert ei.value.code == PLAN_SPEC_INVALID

    def test_apply_success_bumps_version(self):
        repo = FakeRepo(_plan())
        svc = self._pending(repo)
        out = svc.apply(1, 1, actor='user', reason='放宽止损')
        assert out['version'] == 2

    def test_apply_stale_version_conflict(self):
        repo = FakeRepo(_plan())
        svc = self._pending(repo)
        with pytest.raises(PlanError) as ei:
            svc.apply(1, 99, actor='user')
        assert ei.value.code == VERSION_CONFLICT

    def test_window_lock_requires_reason_or_evidence(self):
        repo = FakeRepo(_plan())
        # 上一版改的同一字段，观察窗未满
        repo.versions.insert(0, SimpleNamespace(
            version=2, spec=_spec(stop=9.0),
            window_ends_at=NOW.date() + timedelta(days=5)))
        repo.versions.insert(1, SimpleNamespace(version=1, spec=_spec(stop=8.0),
                                               window_ends_at=None))
        repo.plan.version = 2
        repo.plan.spec = _spec(stop=9.0)
        repo.plan.draft_spec = _spec(stop=11.0)
        svc = _service(repo)
        with pytest.raises(PlanError) as ei:
            svc.apply(1, 2, actor='user')
        assert ei.value.code == PLAN_CHANGE_LOCKED
        # 带 ≥2 条证据可放行
        out = svc.apply(1, 2, actor='user',
                        hypothesis={'evidence': ['sim:假止损率 71%', 'outcome:5d up 22%']})
        assert out['version'] == 3

    def test_reversal_requires_reason(self):
        repo = FakeRepo(_plan())
        # v1=8.0 → v2=10.0，现在改回 8.0（反向）
        repo.versions.insert(0, SimpleNamespace(version=2, spec=_spec(stop=10.0),
                                               window_ends_at=NOW.date() + timedelta(days=5)))
        repo.versions.insert(1, SimpleNamespace(version=1, spec=_spec(stop=8.0),
                                               window_ends_at=None))
        repo.plan.version = 2
        repo.plan.spec = _spec(stop=10.0)
        repo.plan.draft_spec = _spec(stop=8.0)
        svc = _service(repo)
        with pytest.raises(PlanError) as ei:
            svc.apply(1, 2, actor='user')
        assert ei.value.code == PLAN_CHANGE_LOCKED
        out = svc.apply(1, 2, actor='user', reason='上次判断错了：止损放宽后单笔亏损过大')
        assert out['version'] == 3


class TestLifecycle:
    def test_draft_cannot_close(self):
        svc = _service(FakeRepo(_plan(status='draft')))
        with pytest.raises(PlanError) as ei:
            svc.close(1, reason='不要了')
        assert ei.value.code == PLAN_STATE_ILLEGAL

    def test_holding_close_requires_disposition(self):
        svc = _service(FakeRepo(_plan(status='holding')), has_position=True)
        with pytest.raises(PlanError) as ei:
            svc.close(1, reason='关掉')
        assert ei.value.code == PLAN_STATE_ILLEGAL
        svc.close(1, reason='关掉', close_disposition='市价清仓')
        assert svc.repo.plan.status == 'closing'

    def test_activate_pause_resume(self):
        repo = FakeRepo(_plan(status='draft'))
        svc = _service(repo)
        svc.activate(1, expected_version=1)
        assert repo.plan.status == 'active'
        svc.pause(1, '临时')
        assert repo.plan.status == 'paused'
        svc.resume(1, expected_version=1)
        assert repo.plan.status == 'active'

    def test_on_fill_advances_and_closes(self):
        repo = FakeRepo(_plan(status='active'))
        svc = _service(repo, has_position=True)
        assert svc.on_fill(1, side='buy', qty=100, remaining_qty=100) == 'holding'
        assert svc.on_fill(1, side='sell', qty=30, remaining_qty=70) == 'holding'
        assert svc.on_fill(1, side='sell', qty=70, remaining_qty=0) == 'closed'
        assert repo.plan.status == 'closed'
