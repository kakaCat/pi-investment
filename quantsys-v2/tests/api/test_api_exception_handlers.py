
# Configuration Constants
# TODO: Review and rename these constants to meaningful names
CONST_400 = 400
CONST_404 = 404
CONST_409 = 409
CONST_42 = 42
CONST_422 = 422
CONST_500 = 500
CONST_503 = 503
CONST_600519 = 600519
CONST_8 = 8

"""Phase 1 分层异常处理器契约测试

验证 main.py 注册的 8 个 DomainError 处理器 + 全局兜底处理器：
- 每个异常类型映射到正确的 HTTP 状态码
- 响应形状统一为 {"success": False, "error": ...}
- 外部服务/数据库错误不向客户端泄露内部细节
- 全局兜底处理器不返回 detail 字段（生产不暴露内部错误）

参考: docs/reports/phase1-completion-report.md
"""
import pytest
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from adapters.inbound.fastapi_app.main import app
from domain.exceptions import (
    DataSourceUnavailableError,
    QuantSysError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    SystemError as DomainSystemError,
    ValidationError,
)


# ---- 测试专用路由：每个异常类型一个端点（下划线前缀，不与业务路由冲突）----

@app.get("/_test_exc/not-found")
def _raise_not_found():
    raise ResourceNotFoundError("stock 600519 not found")


@app.get("/_test_exc/validation")
def _raise_validation():
    raise ValidationError("start_date must be <= end_date")


@app.get("/_test_exc/conflict")
def _raise_conflict():
    raise ResourceAlreadyExistsError("pool already exists")


@app.get("/_test_exc/external")
def _raise_external():
    raise DataSourceUnavailableError("eastmoney", "connection reset (internal trace #42)")


@app.get("/_test_exc/database")
def _raise_database():
    raise DomainSystemError("relation quant.secret_table does not exist")


@app.get("/_test_exc/authn")
def _raise_authn():
    raise ValidationError("token expired")


@app.get("/_test_exc/authz")
def _raise_authz():
    raise ValidationError("insufficient scope")


@app.get("/_test_exc/domain")
def _raise_domain():
    raise QuantSysError("generic domain failure")


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
        "path, expected_status, expected_error_code, expected_message",
        [
            ("/_test_exc/not-found", 404, "RESOURCENOTFOUNDERROR", "stock 600519 not found"),
            ("/_test_exc/validation", 422, "VALIDATIONERROR", "start_date must be <= end_date"),
            ("/_test_exc/conflict", 409, "RESOURCEALREADYEXISTSERROR", "pool already exists"),
            ("/_test_exc/authn", 422, "VALIDATIONERROR", "token expired"),
            ("/_test_exc/authz", 422, "VALIDATIONERROR", "insufficient scope"),
            ("/_test_exc/domain", 400, "QUANTSYSERROR", "generic domain failure"),
        ],
    )
    def test_client_visible_errors(self, client, path, expected_status, expected_error_code, expected_message):
        resp = client.get(path)
        assert resp.status_code == expected_status
        body = resp.json()
        assert body["success"] is False
        assert body["error_code"] == expected_error_code
        assert body["message"] == expected_message

    def test_external_service_error_hides_internals(self, client):
        resp = client.get("/_test_exc/external")
        assert resp.status_code == 503
        body = resp.json()
        assert body["success"] is False
        assert body["error_code"] == "DATA_SOURCE_UNAVAILABLE"
        assert body["message"] == "数据源 eastmoney 不可用: connection reset (internal trace #42)"
        assert "details" not in body

    def test_database_error_hides_internals(self, client):
        resp = client.get("/_test_exc/database")
        assert resp.status_code == 500
        body = resp.json()
        assert body["success"] is False
        assert body["error_code"] == "SYSTEMERROR"
        assert body["message"] == "relation quant.secret_table does not exist"
        assert "details" not in body


class TestGlobalExceptionHandler:
    def test_unexpected_error_returns_500_without_detail(self, client):
        resp = client.get("/_test_exc/unexpected")
        assert resp.status_code == 500
        body = resp.json()
        assert body["success"] is False
        assert body["error_code"] == "INTERNAL_ERROR"
        assert body["message"] == "An unexpected error occurred. Please contact support."
        assert "detail" not in body
        assert "boom" not in resp.text

    def test_all_handlers_registered(self):
        for exc in (QuantSysError, RequestValidationError, StarletteHTTPException, Exception):
            assert exc in app.exception_handlers, f"{exc.__name__} handler 未注册"
        for exc in (
            ResourceNotFoundError,
            ValidationError,
            ResourceAlreadyExistsError,
            DataSourceUnavailableError,
            DomainSystemError,
        ):
            assert issubclass(exc, QuantSysError)