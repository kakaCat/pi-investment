"""证明 parity 框架能同时驱动 Flask 与 FastAPI 两个 in-process client"""
from tests.migration.parity import normalize


def test_both_clients_boot(flask_client, fastapi_client):
    # Flask 健康端点存在（可能 200 或 404，取决于注册，但 client 必须可用）
    fr = flask_client.get("/api/health")
    assert fr.status_code in (200, 404)
    # FastAPI 根路径与健康检查必定可用
    assert fastapi_client.get("/health").status_code == 200
    assert fastapi_client.get("/").status_code == 200


def test_normalize_strips_volatile_keys():
    a = {"success": True, "timestamp": "2026-01-01", "data": {"x": 1}}
    b = {"success": True, "timestamp": "2099-12-31", "data": {"x": 1}}
    assert normalize(a) == normalize(b)
    # 非易变字段不同则不相等
    c = {"success": True, "data": {"x": 2}}
    assert normalize(a) != normalize(c)
