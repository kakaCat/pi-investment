"""非生产环境闸门：测试进程永不唤醒真实 agent（2026-09-11，w-f4aa1f6a）

事故背景：pytest 套件（根 conftest 载入 .env.test → PGDATABASE=quant_test）里跑的
池刷新调用 AgentNotificationService，而 wake 地址取自生产 .env / 内置默认
http://127.0.0.1:13080 —— 测试反复运行把 quant_test 的假池变更
（pool_id 798/813/827/841「动态」，removed=["000858.SZ"]）真实投递给在线 agent，
制造 5 条 wake 回执 + 5 次"请处置"要求（生产库 stock_pools 最大 id 仅 52，无从处置）。

本文件只测**闸门本身**：
  - 测试库（PGDATABASE 以 _test 结尾）→ skipped，且一个 HTTP 都不发
  - pytest 运行中且库名非测试库 → skipped（第二道信号）
  - 显式开闸（AGENT_NOTIFY_ALLOW_TEST=true 或 allow_non_prod=True）→ 放行投递
"""
from unittest.mock import patch

import pytest

from application.services.agent_notification_service import (
    DB_ENV_VARS,
    AgentNotificationService,
    non_prod_reason,
)


class _Resp:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {"success": True}
        self.text = str(self._body)

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def _no_hatch_by_default(monkeypatch):
    """默认关闸：每个用例自己决定是否开闸"""
    monkeypatch.delenv("AGENT_NOTIFY_ALLOW_TEST", raising=False)
    monkeypatch.delenv("AGENT_NOTIFY_ENABLED", raising=False)


def test_test_db_reason(monkeypatch):
    monkeypatch.setenv("PGDATABASE", "quant_test")
    assert non_prod_reason() == "test-db:PGDATABASE=quant_test"


def test_test_db_reason_via_dsn_only(monkeypatch):
    """DSN-only 配置（.env.test 的 Option 1 写法）同样能被识别——只查 PGDATABASE 会漏"""
    for var in ("PGDATABASE", "DATABASE_URL", "POSTGRES_DSN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("QUANT_DATABASE_URL",
                       "postgresql://mac@127.0.0.1:5432/quant_test?sslmode=disable")
    assert non_prod_reason() == "test-db:QUANT_DATABASE_URL=quant_test"


def test_prod_dsn_is_not_blocked_env_wise(monkeypatch):
    """反向用例：生产库 DSN 不触发闸门（闸门只认 _test 结尾库名）"""
    for var in DB_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("QUANT_DATABASE_URL", "postgresql://mac@127.0.0.1:5432/quant_investment")
    monkeypatch.setenv("AGENT_NOTIFY_ALLOW_TEST", "true")  # 排除 pytest-runtime 信号干扰
    assert non_prod_reason() is None


def test_pytest_runtime_reason_when_db_looks_prod(monkeypatch):
    """库名信号全部清空（模拟生产库配置），pytest 信号仍须独立拦住"""
    for var in DB_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("PGDATABASE", "quant_investment")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/x.py::test_y (call)")
    assert non_prod_reason() == "pytest-runtime"


def test_hatch_env_disables_guard(monkeypatch):
    monkeypatch.setenv("PGDATABASE", "quant_test")
    monkeypatch.setenv("AGENT_NOTIFY_ALLOW_TEST", "true")
    assert non_prod_reason() is None


def test_test_process_does_not_post(monkeypatch):
    """核心负向用例：测试库环境下 notify 不产生任何 HTTP 请求"""
    monkeypatch.setenv("PGDATABASE", "quant_test")
    with patch("application.services.agent_notification_service.requests.post") as mock_post:
        svc = AgentNotificationService()
        assert svc.notify_agent_detailed("pool_changed", {"pool_id": 841}) == "skipped"
        assert svc.notify_agent("pool_changed", {"pool_id": 841}) is False
    assert mock_post.call_count == 0


def test_pytest_without_test_db_does_not_post(monkeypatch):
    """第二道信号：库名看起来是生产库，但进程在跑 pytest → 依旧不投递"""
    monkeypatch.setenv("PGDATABASE", "quant_investment")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/x.py::test_y (call)")
    with patch("application.services.agent_notification_service.requests.post") as mock_post:
        svc = AgentNotificationService()
        assert svc.notify_agent_detailed("pool_changed", {"pool_id": 841}) == "skipped"
    assert mock_post.call_count == 0


def test_hatch_lets_transport_tests_through(monkeypatch):
    """正向用例：显式开闸后投递链路照常工作（否则传输层单测无法自证）"""
    monkeypatch.setenv("PGDATABASE", "quant_test")
    monkeypatch.setenv("AGENT_NOTIFY_ALLOW_TEST", "true")
    with patch("application.services.agent_notification_service.requests.post",
               return_value=_Resp()) as mock_post:
        svc = AgentNotificationService()
        assert svc.notify_agent_detailed("pool_changed", {"pool_id": 1}) == "ok"
    assert mock_post.call_count == 1


def test_explicit_allow_flag_lets_transport_tests_through(monkeypatch):
    """结构化开闸：构造参数 allow_non_prod=True（生产代码永不置位）"""
    monkeypatch.setenv("PGDATABASE", "quant_test")
    with patch("application.services.agent_notification_service.requests.post",
               return_value=_Resp()) as mock_post:
        svc = AgentNotificationService(allow_non_prod=True)
        assert svc.notify_agent_detailed("pool_changed", {"pool_id": 1}) == "ok"
    assert mock_post.call_count == 1


def test_disabled_still_wins_over_guard(monkeypatch):
    """AGENT_NOTIFY_ENABLED=false 的语义不变（先于闸门判定）"""
    monkeypatch.setenv("PGDATABASE", "quant_test")
    monkeypatch.setenv("AGENT_NOTIFY_ENABLED", "false")
    with patch("application.services.agent_notification_service.requests.post") as mock_post:
        assert AgentNotificationService().notify_agent_detailed("x", {}) == "disabled"
    assert mock_post.call_count == 0
