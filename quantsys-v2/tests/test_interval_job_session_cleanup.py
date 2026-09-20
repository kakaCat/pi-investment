"""_run_interval_job 会话清理回归测试（2026-09-20，w-6faac762）。

背景：interval 周期任务路径（watch_sla_patrol 等）在独立守护线程执行 handler，
但此前从不调用 close_session()——handler 触库后 scoped_session 线程本地的
Session 挂着 autobegin 开放事务随线程终存活，300s 后被 session_guard 判
session_leak_detected（错误事件 7f0819b1，2 天 44 次）。
修复：_run_interval_job 增加 finally close_session()（对齐 _run_job 日任务路径）。
本测试做故障注入：handler 成功 / handler 抛异常两条路径都必须清理会话。
"""

from adapters.inbound.fastapi_app import daily_jobs_bootstrap as djb
from infrastructure.persistence import orm as orm_pkg


class _FakeJob:
    def __init__(self, handler):
        self.job_id = 'test_interval'
        self.handler = handler


def _run_and_count(monkeypatch, handler):
    calls = {'n': 0}

    def _fake_close_session():
        calls['n'] += 1

    monkeypatch.setattr(orm_pkg, 'close_session', _fake_close_session)
    monkeypatch.setattr(djb, 'logger', _SilentLogger())
    djb._run_interval_job(_FakeJob(handler))
    return calls['n']


class _SilentLogger:
    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass


def test_close_session_called_on_success(monkeypatch):
    assert _run_and_count(monkeypatch, lambda: {'ok': True}) == 1


def test_close_session_called_on_handler_exception(monkeypatch):
    def _boom():
        raise RuntimeError('handler exploded')

    assert _run_and_count(monkeypatch, _boom) == 1


def test_close_session_failure_does_not_escape(monkeypatch):
    def _bad_close():
        raise RuntimeError('close failed')

    monkeypatch.setattr(orm_pkg, 'close_session', _bad_close)
    monkeypatch.setattr(djb, 'logger', _SilentLogger())
    # 不应抛出：清理失败必须被吞掉，不能打挂宿主调度循环
    djb._run_interval_job(_FakeJob(lambda: {'ok': True}))
