"""测试期通知外发守卫的单测（REQ-261003150739-b98d FR-3）

锁三件事：① URL 分类（agent / feishu / wake / 无关 URL）；
② 包装器行为（通知接收端**拦截+记账**、无关 URL **原样放行**、真实外发计数恒 0）；
③ 开关语义（`off` 不安装；`fail` 才判失败）。

回归锁与 fail 模式的切换在 t4（同一文件追加）。
"""
from pathlib import Path

import requests

from tests.notify_guard import (
    ENV_SWITCH,
    MODE_FAIL,
    MODE_OFF,
    MODE_REPORT,
    GuardHandle,
    NotifyAttempt,
    classify,
    install_notify_guard,
    mode_from_env,
)


# ── ① URL 分类 ────────────────────────────────────────────────────────────
def test_classify_agent_gateway_path():
    assert classify("http://127.0.0.1:13080/api/v1/notifications/send") == "agent"


def test_classify_feishu_webhook_path():
    assert classify("https://open.feishu.cn/open-apis/bot/v2/hook/abc") == "feishu"


def test_classify_wake_path():
    assert classify("http://127.0.0.1:13080/wake") == "wake"


def test_classify_unrelated_url_is_none():
    # 数据源/普通 HTTP 测试不能被误伤——这是守卫"透明"的前提
    assert classify("https://example.com/quote?symbol=600000") is None
    assert classify("") is None


def test_classify_by_configured_authority():
    # 路径特征之外的第二道判据：配置里的接收端 **authority（主机 + 端口）**
    hosts = {("notify.internal", 8080): "agent", ("hook.internal", 443): "feishu"}
    assert classify("http://notify.internal:8080/anything", hosts=hosts) == "agent"
    assert classify("https://hook.internal/x/y", hosts=hosts) == "feishu"
    assert classify("http://other.internal:8080/x", hosts=hosts) is None


def test_same_host_different_port_is_not_a_sink():
    """2026-10-03 全量清点的**误伤回归**：同主机不同端口不得判成通知外发。

    实测（只比主机名的旧版）：`http://127.0.0.1:9/api/embeddings`、
    `http://127.0.0.1:5001/api/stocks/resolve` 被误拦，整套测试误伤 58 个用例。
    """
    hosts = {("127.0.0.1", 8080): "agent"}
    assert classify("http://127.0.0.1:9/api/embeddings", hosts=hosts) is None
    assert classify("http://127.0.0.1:5001/api/stocks/resolve", hosts=hosts) is None
    assert classify("http://127.0.0.1:8080/api/v1/notifications/send", hosts=hosts) == "agent"


def test_wake_path_must_be_exact():
    """`/wake` 是整段路径判据，不做子串匹配（避免 /api/awake 之类误伤）。"""
    assert classify("http://127.0.0.1:13080/wake") == "wake"
    assert classify("http://127.0.0.1:13080/wake?agent=x") == "wake"
    assert classify("http://127.0.0.1:13080/api/awake") is None
    assert classify("http://127.0.0.1:13080/wake/extra") is None


# ── ② 包装器行为 ──────────────────────────────────────────────────────────
def test_wrapper_blocks_notification_and_passes_through_others(monkeypatch):
    calls = []

    def _fake_post(*args, **kwargs):
        calls.append(args)
        return "REAL-HTTP"

    monkeypatch.setattr(requests, "post", _fake_post)
    handle = GuardHandle(MODE_REPORT).install()
    try:
        # 无关 URL：原样走真实实现，且不进记账
        assert requests.post("https://example.com/quote") == "REAL-HTTP"
        assert handle.intercepted() == 0

        # 通知接收端：拦截成合成成功响应，不发起真实请求
        resp = requests.post("http://127.0.0.1:13080/api/v1/notifications/send", json={})
        assert resp.status_code == 200
        assert resp.json() == {"success": True, "code": 0, "StatusCode": 0}
        assert resp.text == ""
        assert len(calls) == 1, "通知请求不得真的走 requests.post"
        assert handle.intercepted() == 1
        assert handle.real_egress_count() == 0
        assert handle.attempts()[0].sink == "agent"
        assert handle.attempts()[0].blocked is True
        assert handle.attempts()[0].egress is False
    finally:
        handle.uninstall()


def test_keyword_url_is_also_classified(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: "REAL")
    handle = GuardHandle(MODE_REPORT).install()
    try:
        requests.get(url="https://open.feishu.cn/open-apis/bot/v2/hook/x")
        assert [a.sink for a in handle.attempts()] == ["feishu"]
    finally:
        handle.uninstall()


# ── ③ 开关语义 ────────────────────────────────────────────────────────────
def test_off_switch_installs_nothing(monkeypatch):
    monkeypatch.setenv(ENV_SWITCH, MODE_OFF)
    assert mode_from_env() == MODE_OFF
    assert install_notify_guard() is None


def test_mode_from_env_defaults_and_unknown_value(monkeypatch):
    monkeypatch.delenv(ENV_SWITCH, raising=False)
    from tests.notify_guard import DEFAULT_MODE

    assert mode_from_env() == DEFAULT_MODE
    monkeypatch.setenv(ENV_SWITCH, "nonsense")
    assert mode_from_env() == DEFAULT_MODE


def _attempt(nodeid: str) -> NotifyAttempt:
    return NotifyAttempt(
        ts=0.0,
        method="post",
        url="http://127.0.0.1:13080/api/v1/notifications/send",
        sink="agent",
        test_nodeid=nodeid,
    )


def test_only_fail_mode_reports_a_failure():
    """report 模式只记账、绝不判失败（t3 的兼容态）；fail 模式才给失败信息（t4 的收敛态）。

    这里**刻意不碰 requests**：直接构造记账记录，避免影响会话级守卫（上一版用
    importlib.reload(requests) 还原，会把会话守卫的包装器一并冲掉——那才是"守卫静默失效"）。
    """
    report = GuardHandle(MODE_REPORT)
    report._attempts.append(_attempt("tests/x.py::test_y"))
    assert report.failure_for("tests/x.py::test_y") is None
    assert report.real_egress_count() == 0

    failing = GuardHandle(MODE_FAIL)
    failing._attempts.append(_attempt("tests/x.py::test_y"))
    reason = failing.failure_for("tests/x.py::test_y")
    assert reason and "漏桩" in reason and "notifications/send" in reason
    assert failing.failure_for("tests/x.py::test_other") is None


# ── ④ 回归锁（t4）───────────────────────────────────────────────────────────
def test_default_mode_is_fail(monkeypatch):
    """默认必须是 fail：漏桩要让用例红，而不是只记一笔账（FR-4）。"""
    monkeypatch.delenv(ENV_SWITCH, raising=False)
    assert mode_from_env() == MODE_FAIL


def test_session_guard_records_no_real_egress(notify_guard):
    """本会话的硬保证：真实外发计数为 0，且被拦下的调用全部标记 blocked。"""
    assert notify_guard is not None, '守卫生效时必须能拿到会话句柄（QUANTSYS_NOTIFY_GUARD=off 时才为 None）'
    notify_guard.assert_no_real_egress()
    assert all(a.blocked for a in notify_guard.attempts())
    assert all(a.egress is False for a in notify_guard.attempts())


def test_stub_targets_point_at_implementation_module():
    """静态回归锁（FR-1 / FR-2）：桩必须打在**实现所在模块**。

    守卫只能保证「漏桩不再外发」，但漏桩本身仍应被发现——所以这里把两个已知漏点的
    打桩点钉死：一旦有人把桩改回 `alerting` / 转发壳，这条用例立刻红。
    """
    root = Path(__file__).resolve().parents[1]
    guard_src = (root / 'tests' / 'test_false_success_guard.py').read_text(encoding='utf-8')
    assert "monkeypatch.setattr(host_runtime, '_send_feishu'" in guard_src
    assert 'host_alerting' not in guard_src, '不得再引用 alerting——那里打桩是静默失效的'

    e2e_src = (root / 'tests' / 'e2e' / 'test_daily_orchestrator.py').read_text(encoding='utf-8')
    assert "monkeypatch.setattr(host_runtime, '_run_job'" in e2e_src, 'e2e 手动触发用例必须打桩 _run_job'
