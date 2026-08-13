"""DailyOrchestrator/IntradayMonitor 随 FastAPI 启动的装配测试（2026-08-13）

回归背景：orchestrator tick（T+1 结转/信号推送/挂单撮合）与 intraday monitor
（止损止盈）原仅由 scheduler_daemon.py 注册。daemon 无 launchd 守护，08-05
进程消失后两层功能静默死亡 8 天——今世缘(603369) 08-07 买入后 T+1 从未结转，
08-13 卖出被 422「可卖 0 股」拦截。与 WatchEngine 静默消失同一事故模式。

契约：orchestrator/intraday 唯一宿主 = FastAPI 5001 进程（lifespan 启动）。
"""
import threading
from datetime import datetime
from pathlib import Path

import pytest


class TestWindows:
    """tick 窗口守卫（沿用原 daemon cron 语义）"""

    def test_orchestrator_window_weekday_8_to_17(self):
        from adapters.inbound.fastapi_app.orchestrator_bootstrap import _in_orchestrator_window
        assert _in_orchestrator_window(datetime(2026, 8, 13, 9, 25))   # 周四 9:25
        assert _in_orchestrator_window(datetime(2026, 8, 13, 17, 59))  # 边界
        assert not _in_orchestrator_window(datetime(2026, 8, 13, 7, 59))
        assert not _in_orchestrator_window(datetime(2026, 8, 13, 18, 0))
        assert not _in_orchestrator_window(datetime(2026, 8, 15, 10, 0))  # 周六

    def test_intraday_window_0930_1130_and_1300_1500_on_00_30(self):
        from adapters.inbound.fastapi_app.orchestrator_bootstrap import _in_intraday_window
        assert _in_intraday_window(datetime(2026, 8, 13, 9, 30))
        assert _in_intraday_window(datetime(2026, 8, 13, 11, 30))
        assert _in_intraday_window(datetime(2026, 8, 13, 14, 30))
        assert _in_intraday_window(datetime(2026, 8, 13, 15, 0))
        assert not _in_intraday_window(datetime(2026, 8, 13, 9, 31))   # 非 :00/:30
        assert not _in_intraday_window(datetime(2026, 8, 13, 12, 0))   # 午休
        assert not _in_intraday_window(datetime(2026, 8, 15, 10, 0))   # 周六


def test_start_orchestrator_calls_ticks(monkeypatch):
    """生产模式（skip=False）：线程跑起来，窗口内调用两个 tick，可优雅停止"""
    from adapters.inbound.fastapi_app import orchestrator_bootstrap as ob

    ticks = {'orch': 0, 'intraday': 0}
    monkeypatch.setattr(
        'infrastructure.jobs.monitor_jobs.daily_orchestrator_tick',
        lambda: ticks.__setitem__('orch', ticks['orch'] + 1))
    monkeypatch.setattr(
        'infrastructure.jobs.monitor_jobs.intraday_monitor_check',
        lambda: ticks.__setitem__('intraday', ticks['intraday'] + 1))
    monkeypatch.setattr(ob, '_in_orchestrator_window', lambda now: True)
    monkeypatch.setattr(ob, '_in_intraday_window', lambda now: True)
    monkeypatch.setattr(ob, '_TICK_INTERVAL_SEC', 0.05)

    resumed = []

    class _FakeOrch:
        def resume_from_breakpoint(self):
            resumed.append(1)

    monkeypatch.setattr(
        'application.services.daily_orchestrator.get_daily_orchestrator',
        lambda: _FakeOrch())

    handles = ob.start_orchestrator(skip=False)
    assert handles is not None
    thread, stop_event = handles
    assert isinstance(thread, threading.Thread)
    assert thread.is_alive()
    assert resumed == [1]  # 启动即断点续跑

    deadline = datetime.now().timestamp() + 5
    while ticks['orch'] == 0 and datetime.now().timestamp() < deadline:
        stop_event.wait(0.05)
    ob.stop_orchestrator(handles)

    assert ticks['orch'] >= 1
    assert ticks['intraday'] >= 1
    assert not thread.is_alive()


def test_start_orchestrator_skip(monkeypatch):
    """skip=True（pytest 环境）：不启动线程，返回 None"""
    from adapters.inbound.fastapi_app import orchestrator_bootstrap as ob

    calls = []
    monkeypatch.setattr(
        'infrastructure.jobs.monitor_jobs.daily_orchestrator_tick',
        lambda: calls.append(1))

    assert ob.start_orchestrator(skip=True) is None
    assert not calls


def test_tick_exception_does_not_kill_thread(monkeypatch):
    """单次 tick 抛异常线程必须存活——否则编排器再次静默死亡"""
    from adapters.inbound.fastapi_app import orchestrator_bootstrap as ob

    calls = {'n': 0}

    def _flaky():
        calls['n'] += 1
        if calls['n'] == 1:
            raise RuntimeError('boom')

    monkeypatch.setattr(
        'infrastructure.jobs.monitor_jobs.daily_orchestrator_tick', _flaky)
    monkeypatch.setattr(ob, '_in_orchestrator_window', lambda now: True)
    monkeypatch.setattr(ob, '_in_intraday_window', lambda now: False)
    monkeypatch.setattr(ob, '_TICK_INTERVAL_SEC', 0.05)

    class _FakeOrch:
        def resume_from_breakpoint(self):
            pass

    monkeypatch.setattr(
        'application.services.daily_orchestrator.get_daily_orchestrator',
        lambda: _FakeOrch())

    handles = ob.start_orchestrator(skip=False)
    thread, _ = handles
    deadline = datetime.now().timestamp() + 5
    while calls['n'] < 2 and datetime.now().timestamp() < deadline:
        thread.join(timeout=0.05)  # 若线程已死 join 立即返回，靠 calls 计数判断
    ob.stop_orchestrator(handles)

    assert calls['n'] >= 2  # 第一次炸了，第二次仍在跑


def test_scheduler_daemon_no_longer_hosts_orchestrator():
    """契约守护：scheduler_daemon 不再注册 orchestrator/intraday（唯一宿主=FastAPI）。

    防止未来部署再次双宿主并行（重复执行 phase/重复唤醒 agent）或静默丢失
    T+1 结转与盘中止损。
    """
    src = Path(__file__).resolve().parents[2] / 'scheduler_daemon.py'
    content = src.read_text(encoding='utf-8')
    assert '_register_orchestrator' not in content
    assert 'daily_orchestrator_tick' not in content
    assert 'intraday_monitor_check' not in content
