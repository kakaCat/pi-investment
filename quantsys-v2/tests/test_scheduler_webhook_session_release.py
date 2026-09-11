"""同步 job handler 的线程池会话释放回归测试（2026-09-11 w-f4aa1f6a）。

事故：同步 handler 经 run_in_threadpool 跑在线程池线程里，而 close_session() 只清
"当前线程"的 scoped 注册表 → 线程池线程长期存活、每个线程读一次 ORM 就永久挂住会话
（session_guard 实测 age_seconds>300，thread_name=ThreadPoolExecutor-108_6 等），
最终把 DB 连接池健康度打到 100%（事件 ed7d2f6a）。

对照实验（真实 DB，人工执行）：
  直接执行 handler        → 同线程会话保持 = True （连接被占）
  经 _run_sync_handler…   → 同线程会话保持 = False（已释放）
本测试用打桩 close_session 保证在无 DB 的环境下也能守住"必须释放"这条契约。
"""
import pytest

from api.internal.scheduler_webhook import _run_sync_handler_with_session_release


@pytest.fixture
def close_calls(monkeypatch):
    calls = []
    import infrastructure.persistence.orm.config as cfg

    # wrapper 内部在调用时才 from ... import close_session，故打桩模块属性即可生效
    monkeypatch.setattr(cfg, "close_session", lambda: calls.append("closed"), raising=True)
    return calls


def test_releases_session_after_success(close_calls):
    result = _run_sync_handler_with_session_release(lambda meta: {"ok": True}, {})
    assert result == {"ok": True}
    assert close_calls == ["closed"]


def test_releases_session_even_when_handler_raises(close_calls):
    def boom(meta):
        raise RuntimeError("handler 失败也必须释放会话")

    with pytest.raises(RuntimeError):
        _run_sync_handler_with_session_release(boom, {})
    assert close_calls == ["closed"], "handler 抛异常时未释放会话 → 连接会被永久占住"


def test_release_failure_does_not_mask_handler_result(close_calls, monkeypatch):
    import infrastructure.persistence.orm.config as cfg

    def broken_close():
        raise RuntimeError("释放失败")

    monkeypatch.setattr(cfg, "close_session", broken_close)
    # 释放失败不应改变 handler 的返回值（只记 warning）
    assert _run_sync_handler_with_session_release(lambda meta: "ok", {}) == "ok"
