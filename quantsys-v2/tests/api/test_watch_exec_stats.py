"""执行闭环统计端点（REQ-261021194640-69b8 FR-7，卡 t-b8d5ae）

判据：三态计数与 p50/p95 可读；空数据返回 0（时延 null 不伪造 0）；
时间窗非法 400；聚合异常 503 且不返回半份数字。
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes import watch_async
from adapters.outbound.repositories.watch_todo_repository import _percentile


class FakeRepo:
    def __init__(self, data=None, boom=False):
        self.data = data or {
            'executed': 3, 'declined': 1, 'unresolved': 2, 'timeout': 1,
            'latency_p50_seconds': 12.5, 'latency_p95_seconds': 41.0,
            'latency_sample_size': 3,
        }
        self.boom = boom
        self.calls = []

    def exec_stats(self, since=None, until=None):
        self.calls.append((since, until))
        if self.boom:
            raise RuntimeError('db down')
        return dict(self.data)


def _client(monkeypatch, repo):
    import adapters.outbound.repositories.watch_todo_repository as repo_mod
    monkeypatch.setattr(repo_mod, 'WatchTodoRepository', lambda: repo)
    app = FastAPI()
    app.include_router(watch_async.router)
    return TestClient(app)


def test_exec_stats_reads_counts_and_latency(monkeypatch):
    repo = FakeRepo()
    client = _client(monkeypatch, repo)
    resp = client.get('/api/watch/exec/stats')
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['executed'] == 3 and data['declined'] == 1
    assert data['unresolved'] == 2 and data['timeout'] == 1
    assert data['latency_p50_seconds'] == 12.5
    assert data['latency_p95_seconds'] == 41.0


def test_empty_data_returns_zero_not_error(monkeypatch):
    repo = FakeRepo({'executed': 0, 'declined': 0, 'unresolved': 0, 'timeout': 0,
                     'latency_p50_seconds': None, 'latency_p95_seconds': None,
                     'latency_sample_size': 0})
    client = _client(monkeypatch, repo)
    resp = client.get('/api/watch/exec/stats')
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['executed'] == 0
    assert data['latency_p50_seconds'] is None


def test_bad_time_window_is_400(monkeypatch):
    client = _client(monkeypatch, FakeRepo())
    resp = client.get('/api/watch/exec/stats', params={
        'since': '2026-10-21T10:00:00', 'until': '2026-10-20T10:00:00'})
    assert resp.status_code == 400


def test_repository_failure_is_503(monkeypatch):
    client = _client(monkeypatch, FakeRepo(boom=True))
    resp = client.get('/api/watch/exec/stats')
    assert resp.status_code == 503


def test_percentile_handles_empty_and_values():
    assert _percentile([], 0.5) is None
    assert _percentile([10.0], 0.95) == 10.0
    assert _percentile([1.0, 2.0, 3.0], 0.5) == 2.0
