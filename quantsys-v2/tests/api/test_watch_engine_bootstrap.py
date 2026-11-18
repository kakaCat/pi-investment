"""Watch 旁路服务的 FastAPI 宿主契约。"""
from pathlib import Path


def test_start_watch_sidecars_calls_factory(monkeypatch):
    from adapters.inbound.fastapi_app import watch_bootstrap

    sentinel = object()
    calls = []
    monkeypatch.setattr(
        'qs_watch.application.services.watch_engine.factory.start_watch_sidecars_in_thread',
        lambda: calls.append(1) or sentinel,
    )

    result = watch_bootstrap.start_watch_sidecars(skip=False)

    assert result is sentinel
    assert calls == [1]


def test_start_watch_sidecars_skip(monkeypatch):
    from adapters.inbound.fastapi_app import watch_bootstrap

    calls = []
    monkeypatch.setattr(
        'qs_watch.application.services.watch_engine.factory.start_watch_sidecars_in_thread',
        lambda: calls.append(1),
    )

    result = watch_bootstrap.start_watch_sidecars(skip=True)

    assert result is None
    assert not calls


def test_v1_stock_engine_entrypoint_removed():
    from adapters.inbound.fastapi_app import watch_bootstrap

    assert not hasattr(watch_bootstrap, 'start_watch_engine')
    assert not hasattr(watch_bootstrap, 'v1_enabled')


def test_scheduler_daemon_no_longer_hosts_watch_engine():
    """盯盘唯一宿主仍是 FastAPI，不能重新引入 daemon 双引擎。"""
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / 'scheduler_daemon.py').exists()
    assert not (repo_root / 'application/services/unified_scheduler.py').exists()
