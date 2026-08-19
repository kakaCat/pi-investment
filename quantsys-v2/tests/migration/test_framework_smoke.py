"""证明测试框架能驱动 FastAPI in-process client（Flask 已删除 2026-08）"""
from tests.migration.parity import normalize


def test_both_clients_boot(fastapi_client):
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
