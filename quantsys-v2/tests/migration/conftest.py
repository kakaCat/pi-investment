"""migration 测试共享 fixture：in-process 启动 FastAPI（Flask 已废弃删除，2026-08）"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def fastapi_client():
    from adapters.inbound.fastapi_app.main import app
    # raise_server_exceptions=False：未处理异常时返回 500 响应（而非向上抛）
    return TestClient(app, raise_server_exceptions=False)
