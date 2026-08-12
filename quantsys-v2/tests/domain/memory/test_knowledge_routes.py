"""Knowledge FastAPI 路由冒烟（2026-08-12 补）

背景：knowledge 路由长期只有 Flask 版，FastAPI 侧 404；
W1.1 修了 service 层但 agent knowledge_query 走 HTTP 仍 404。
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.knowledge_async import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_active_knowledge_returns_list(client):
    resp = client.get("/api/knowledge/active")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_active_knowledge_domain_filter(client):
    resp = client.get("/api/knowledge/active", params={"domain": "chan_theory"})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["domain"] == "chan_theory"


def test_summary_shape(client):
    resp = client.get("/api/knowledge/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_knowledge" in data
    assert "by_domain" in data


def test_apply_returns_list(client):
    resp = client.post("/api/knowledge/apply", json={"domain": "chan_theory"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
