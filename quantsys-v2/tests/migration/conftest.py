"""parity 测试共享 fixture：in-process 同时启动 Flask 与 FastAPI"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def flask_client():
    from adapters.inbound.api.server import create_app
    app = create_app()
    # app.testing=False：未处理异常时返回 500 响应（而非向上抛），
    # 使"Flask 与 FastAPI 均有相同既有 bug"的端点也能按状态码比对。
    app.testing = False
    return app.test_client()


@pytest.fixture(scope="session")
def fastapi_client():
    from adapters.inbound.fastapi_app.main import app
    # raise_server_exceptions=False：未处理异常时返回 500 响应（而非向上抛）
    return TestClient(app, raise_server_exceptions=False)
