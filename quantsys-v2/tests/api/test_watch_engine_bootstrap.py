"""WatchEngine 随 FastAPI 启动的装配测试（2026-08-12）

回归背景：WatchEngine 常驻线程原仅由 scheduler_daemon.py 启动。08-02 生产
切换到 FastAPI nohup 部署后 daemon 未再拉起，盯盘静默消失——watch_triggers
停在 08-05 14:58，规则照常创建但无人判定、不唤醒 agent、不发飞书。

契约：盯盘引擎唯一宿主 = FastAPI 5001 进程（lifespan 启动）。
"""
from pathlib import Path

import pytest


def test_start_watch_engine_calls_factory(monkeypatch):
    """生产模式（skip=False）：调用 factory 启动引擎线程并返回句柄"""
    from adapters.inbound.fastapi_app import watch_bootstrap

    sentinel = (object(), object())
    calls = []
    monkeypatch.setattr(
        'application.services.watch_engine.factory.start_watch_engine_in_thread',
        lambda: calls.append(1) or sentinel,
    )

    result = watch_bootstrap.start_watch_engine(skip=False)

    assert result == sentinel
    assert len(calls) == 1


def test_start_watch_engine_skip(monkeypatch):
    """skip=True（pytest 环境）：不启动线程，返回 None"""
    from adapters.inbound.fastapi_app import watch_bootstrap

    calls = []
    monkeypatch.setattr(
        'application.services.watch_engine.factory.start_watch_engine_in_thread',
        lambda: calls.append(1),
    )

    result = watch_bootstrap.start_watch_engine(skip=True)

    assert result is None
    assert not calls


def test_scheduler_daemon_no_longer_hosts_watch_engine():
    """契约守护：scheduler_daemon 已删除（2026-08-13），盯盘唯一宿主=FastAPI。

    防止未来重新引入 daemon 类进程导致双引擎并行（重复触发+重复唤醒）
    或 daemon 死亡后功能静默丢失（08-05 盯盘/T+1 两起事故同根因）。
    """
    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / 'scheduler_daemon.py').exists()
    assert not (repo_root / 'application/services/unified_scheduler.py').exists()
