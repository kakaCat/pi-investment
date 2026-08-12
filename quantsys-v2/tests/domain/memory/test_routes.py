"""Memory API 路由层冒烟测试（W1.2 审查补漏）

背景：初版交付 26 个测试全部集中在 domain/repository 层，路由层零覆盖，
导致 get_session 误导入 + MemoryRepository(session) 构造错误上线即 500，
且被 main.py 的 try/except ImportError 静默吞掉。本测试守住路由层契约。
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.memory_async import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def sample_payload():
    return {
        "kind": "experience",
        "scope": "global",
        "title": "test_route_smoke",
        "content": "路由层冒烟测试内容",
        "evidence": {"decision_id": 999},
        "status": "testing",
        "provenance": {"session_kind": "user", "channel": "pytest", "session_id": "s1"},
        "source": "pytest",
    }


def test_create_and_search_roundtrip(client, sample_payload):
    resp = client.post("/api/memory", json=sample_payload)
    assert resp.status_code == 200, resp.text
    created = resp.json()
    entry_id = created["id"]

    resp = client.get("/api/memory/search", params={"q": "路由层冒烟"})
    assert resp.status_code == 200
    results = resp.json()
    items = results if isinstance(results, list) else results.get("items", [])
    assert any(i["id"] == entry_id for i in items)

    # 清理
    from infrastructure.persistence.orm import get_session
    from sqlalchemy import text
    session = get_session()
    session.execute(text("DELETE FROM quant.memory_entries WHERE id = :id"), {"id": entry_id})
    session.commit()


def test_evidence_gate_rejects_active_without_evidence(client, sample_payload):
    sample_payload["evidence"] = None
    sample_payload["status"] = "active"
    resp = client.post("/api/memory", json=sample_payload)
    assert resp.status_code == 400


def test_health(client):
    resp = client.get("/api/memory/health")
    assert resp.status_code == 200
