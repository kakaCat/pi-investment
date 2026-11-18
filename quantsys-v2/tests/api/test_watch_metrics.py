"""盯盘指标端点测试（REQ-c9f899 t10）"""
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.watch_metrics_async import build_metrics, router

NOW = datetime(2026, 9, 18, 10, 0, 0)


def test_build_metrics_shadow_off(monkeypatch):
    monkeypatch.setenv('WATCH_DIGEST_DRY_RUN', 'false')
    m = build_metrics(now=NOW)
    assert m['shadow_mode'] == 'off'
    assert m['degraded'] == []


def test_build_metrics_todo_fields_unknown_without_repo():
    m = build_metrics(now=NOW)
    assert m['pending_todos'] is None
    assert m['by_level'] is None
    assert m['by_flow_state'] is None
    assert m['terminal_rate_today'] is None
    assert m['suppressed_rules'] is None
    assert any('todo' in n for n in m['notes'])


def test_build_metrics_todo_fields_from_repo():
    class FakeTodoRepo:
        def stats(self, now=None):
            return {'pending': 3, 'by_level': {'P1': 3}, 'by_flow_state': {'L3': 3},
                    'created_today': 4, 'closed_today': 1, 'terminal_rate_today': 0.25}

    class FakeNoiseRepo:
        def count_suppressed(self, now=None):
            return 2

    m = build_metrics(now=NOW, todo_repo=FakeTodoRepo(),
                      rule_noise_repo=FakeNoiseRepo())
    assert m['pending_todos'] == 3
    assert m['by_level'] == {'P1': 3}
    assert m['by_flow_state'] == {'L3': 3}
    assert m['todos_created_today'] == 4
    assert m['todos_closed_today'] == 1
    assert m['terminal_rate_today'] == 0.25
    assert m['suppressed_rules'] == 2


def test_build_metrics_todo_repo_failure_degrades_not_zero():
    class BoomRepo:
        def stats(self, now=None):
            raise RuntimeError('db down')

    m = build_metrics(now=NOW, todo_repo=BoomRepo())
    assert m['pending_todos'] is None
    assert any('todo_stats_failed' in d for d in m['degraded'])


def test_route_returns_200():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    r = client.get('/api/watch/metrics')
    assert r.status_code == 200
    body = r.json()
    assert 'shadow_mode' in body and 'pending_todos' in body
