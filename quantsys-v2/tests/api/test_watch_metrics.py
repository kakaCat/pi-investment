"""盯盘指标端点测试（REQ-c9f899 t10）"""
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.watch_metrics_async import build_metrics, router

NOW = datetime(2026, 9, 18, 10, 0, 0)


class FakeStore:
    def __init__(self, meta=None, boom=False):
        self.meta = meta or {}
        self.boom = boom

    def load_meta(self):
        if self.boom:
            raise RuntimeError('db down')
        return self.meta


def test_build_metrics_ok(monkeypatch):
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'true')
    monkeypatch.setenv('WATCH_DIGEST_DRY_RUN', 'false')
    m = build_metrics(now=NOW, store=FakeStore({'heartbeat_at': NOW - timedelta(seconds=20)}))
    assert m['heartbeat_verdict'] == 'ok'
    assert m['engine_alive'] is True
    assert m['heartbeat_age_sec'] == 20.0
    assert m['heartbeat_at'].startswith('2026-09-18T09:')
    assert m['degraded'] == []


def test_build_metrics_stale_not_alive(monkeypatch):
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'true')
    monkeypatch.setenv('WATCH_DIGEST_DRY_RUN', 'false')
    m = build_metrics(now=NOW, store=FakeStore({'heartbeat_at': NOW - timedelta(seconds=600)}))
    assert m['heartbeat_verdict'] == 'stale'
    assert m['engine_alive'] is False


def test_build_metrics_read_failure_degrades_honestly(monkeypatch):
    """取数失败必须写进 degraded，且不把未知当 0（R-013）"""
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'true')
    m = build_metrics(now=NOW, store=FakeStore(boom=True))
    assert any('heartbeat_read_failed' in d for d in m['degraded'])
    assert m['heartbeat_age_sec'] is None


def test_build_metrics_todo_fields_unknown_without_repo():
    """t12：未注入仓储（直调）→ todo 规模为 null（未知，不是 0），notes 说明原因（R-013）"""
    m = build_metrics(now=NOW, store=FakeStore({}))
    assert m['pending_todos'] is None
    assert m['by_level'] is None
    assert m['by_flow_state'] is None
    assert m['terminal_rate_today'] is None
    assert m['suppressed_rules'] is None
    assert any('todo' in n for n in m['notes'])


def test_build_metrics_todo_fields_from_repo():
    """t12 §6-项7：注入仓储 → 规模字段取自 WatchTodoRepository.stats + count_suppressed"""
    class FakeTodoRepo:
        def stats(self, now=None):
            return {'pending': 3, 'by_level': {'P1': 3}, 'by_flow_state': {'L3': 3},
                    'created_today': 4, 'closed_today': 1, 'terminal_rate_today': 0.25}

    class FakeNoiseRepo:
        def count_suppressed(self, now=None):
            return 2

    m = build_metrics(now=NOW, store=FakeStore({}), todo_repo=FakeTodoRepo(),
                      rule_noise_repo=FakeNoiseRepo())
    assert m['pending_todos'] == 3
    assert m['by_level'] == {'P1': 3}
    assert m['by_flow_state'] == {'L3': 3}
    assert m['todos_created_today'] == 4
    assert m['todos_closed_today'] == 1
    assert m['terminal_rate_today'] == 0.25
    assert m['suppressed_rules'] == 2


def test_build_metrics_todo_repo_failure_degrades_not_zero():
    """取数失败 → degraded + null，绝不拿 0 冒充（R-013）"""
    class BoomRepo:
        def stats(self, now=None):
            raise RuntimeError('db down')

    m = build_metrics(now=NOW, store=FakeStore({}), todo_repo=BoomRepo())
    assert m['pending_todos'] is None
    assert any('todo_stats_failed' in d for d in m['degraded'])


def test_route_returns_200_and_heartbeat_age(monkeypatch):
    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'true')
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    r = client.get('/api/watch/metrics')
    assert r.status_code == 200
    body = r.json()
    assert 'heartbeat_age_sec' in body and 'engine_alive' in body
