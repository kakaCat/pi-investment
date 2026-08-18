"""Phase 1 分层异常处理器契约测试

验证 main.py 注册的 8 个 DomainError 处理器 + 全局兜底处理器：
- 每个异常类型映射到正确的 HTTP 状态码
- 响应形状统一为 {"success": False, "error": ...}
- 外部服务/数据库错误不向客户端泄露内部细节
- 全局兜底处理器不返回 detail 字段（生产不暴露内部错误）

参考: docs/reports/phase1-completion-report.md
"""
import pytest
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.main import app
from domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DatabaseError,
    DomainError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)


# ---- 测试专用路由：每个异常类型一个端点（下划线前缀，不与业务路由冲突）----

@app.get("/_test_exc/not-found")
def _raise_not_found():
    raise NotFoundError("stock 600519 not found")


@app.get("/_test_exc/validation")
def _raise_validation():
    raise ValidationError("start_date must be <= end_date")


@app.get("/_test_exc/conflict")
def _raise_conflict():
    raise ConflictError("pool already exists")


@app.get("/_test_exc/external")
def _raise_external():
    raise ExternalServiceError("eastmoney: connection reset (internal trace #42)")


@app.get("/_test_exc/database")
def _raise_database():
    raise DatabaseError("relation quant.secret_table does not exist")


@app.get("/_test_exc/authn")
def _raise_authn():
    raise AuthenticationError("token expired")


@app.get("/_test_exc/authz")
def _raise_authz():
    raise AuthorizationError("insufficient scope")


@app.get("/_test_exc/domain")
def _raise_domain():
    raise DomainError("generic domain failure")


@app.get("/_test_exc/unexpected")
def _raise_unexpected():
    raise RuntimeError("boom: /etc/passwd leaked detail")


@pytest.fixture(scope="module")
def client():
    # raise_server_exceptions=False: 让全局 Exception 处理器接管，而不是抛给测试
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestDomainExceptionHandlers:
    @pytest.mark.parametrize(
        "path, expected_status, expected_error",
        [
            ("/_test_exc/not-found", 404, "stock 600519 not found"),
            ("/_test_exc/validation", 422, "start_date must be <= end_date"),
            ("/_test_exc/conflict", 409, "pool already exists"),
            ("/_test_exc/authn", 401, "token expired"),
            ("/_test_exc/authz", 403, "insufficient scope"),
            ("/_test_exc/domain", 400, "generic domain failure"),
        ],
    )
    def test_client_visible_errors(self, client, path, expected_status, expected_error):
        resp = client.get(path)
        assert resp.status_code == expected_status
        body = resp.json()
        assert body["success"] is False
        assert body["error"] == expected_error

    def test_external_service_error_hides_internals(self, client):
        resp = client.get("/_test_exc/external")
        assert resp.status_code == 502
        body = resp.json()
        assert body == {"success": False, "error": "External service unavailable"}
        assert "internal trace" not in resp.text

    def test_database_error_hides_internals(self, client):
        resp = client.get("/_test_exc/database")
        assert resp.status_code == 500
        body = resp.json()
        assert body == {"success": False, "error": "Database operation failed"}
        assert "secret_table" not in resp.text


class TestGlobalExceptionHandler:
    def test_unexpected_error_returns_500_without_detail(self, client):
        resp = client.get("/_test_exc/unexpected")
        assert resp.status_code == 500
        body = resp.json()
        assert body["success"] is False
        assert body["error"] == "Internal server error"
        # 生产环境不暴露内部错误细节（旧契约的 detail 字段已移除）
        assert "detail" not in body
        assert "boom" not in resp.text

    def test_all_handlers_registered(self):
        for exc in (
            NotFoundError,
            ValidationError,
            ConflictError,
            ExternalServiceError,
            DatabaseError,
            AuthenticationError,
            AuthorizationError,
            DomainError,
            Exception,
        ):
            assert exc in app.exception_handlers, f"{exc.__name__} handler 未注册"
