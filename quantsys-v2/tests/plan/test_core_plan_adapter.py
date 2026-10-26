"""core_plan 批次适配（t14）：生成 draft/幂等/不可用"""
import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from qs_plan.application.core_plan_adapter import CorePlanAdapter, CorePlanUnavailable

NOW = datetime(2026, 10, 21, 9, 30, tzinfo=timezone.utc)


class FakeService:
    def __init__(self):
        self.created = []
        self._names = {}

    def list(self, account, statuses=None):
        return [SimpleNamespace(name=n) for n in self._names]

    def create(self, account, name, horizon, spec, created_by, actor=None):
        pid = len(self.created) + 1
        self.created.append({'id': pid, 'name': name, 'horizon': horizon, 'spec': spec})
        self._names[name] = pid
        return SimpleNamespace(id=pid)


def _write(tmp_path, *, generated='2026-10-21T09:05:01', account='agent_brain'):
    payload = {
        'generated_at': generated, 'account': account, 'account_total': 100000,
        'execution_plan': {'batches': [
            {'batch': 1, 'amount': 20000, 'detail': [
                {'symbol': '600519.SH', 'amount': 10000, 'close': 1500.0},
                {'symbol': '000001.SZ', 'amount': 10000, 'close': 10.0},
            ]},
        ]},
    }
    p = tmp_path / 'core_plan.json'
    p.write_text(json.dumps(payload), encoding='utf-8')
    return str(p)


class TestCorePlanAdapter:
    def test_generates_draft_plans(self, tmp_path):
        svc = FakeService()
        adapter = CorePlanAdapter(svc, core_plan_path=_write(tmp_path), now_fn=lambda: NOW)
        out = adapter.from_batch('agent_brain', 1)
        assert len(out['created']) == 2
        assert [c['horizon'] for c in svc.created] == ['swing', 'swing']
        assert svc.created[0]['spec']['targets'][0]['budget_pct'] == 10.0
        assert svc.created[0]['name'] == 'core-plan-b1-600519.SH'
        # 择时不发明：入场条件为空 + pending 标记（不是占位追高条件）
        entry = svc.created[0]['spec']['entry']
        assert entry['pending'] is True and entry['conditions'] == []

    def test_idempotent_second_call(self, tmp_path):
        svc = FakeService()
        adapter = CorePlanAdapter(svc, core_plan_path=_write(tmp_path), now_fn=lambda: NOW)
        adapter.from_batch('agent_brain', 1)
        out = adapter.from_batch('agent_brain', 1)
        assert out['created'] == [] and len(out['skipped']) == 2

    def test_missing_file_raises(self, tmp_path):
        adapter = CorePlanAdapter(FakeService(), core_plan_path=str(tmp_path / 'nope.json'),
                                  now_fn=lambda: NOW)
        with pytest.raises(CorePlanUnavailable):
            adapter.from_batch('agent_brain', 1)

    def test_stale_file_raises(self, tmp_path):
        old = (NOW - timedelta(days=30)).isoformat()
        adapter = CorePlanAdapter(FakeService(), core_plan_path=_write(tmp_path, generated=old),
                                  now_fn=lambda: NOW)
        with pytest.raises(CorePlanUnavailable) as ei:
            adapter.from_batch('agent_brain', 1)
        assert '过期' in str(ei.value)

    def test_account_mismatch_raises(self, tmp_path):
        adapter = CorePlanAdapter(FakeService(), core_plan_path=_write(tmp_path),
                                  now_fn=lambda: NOW)
        with pytest.raises(CorePlanUnavailable):
            adapter.from_batch('agent_virtual', 1)

    def test_unknown_batch_raises(self, tmp_path):
        adapter = CorePlanAdapter(FakeService(), core_plan_path=_write(tmp_path),
                                  now_fn=lambda: NOW)
        with pytest.raises(CorePlanUnavailable):
            adapter.from_batch('agent_brain', 9)
