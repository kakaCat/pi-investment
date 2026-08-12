"""Tests for Memory Distill API Routes"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from adapters.inbound.fastapi_app.routes.memory_distill_async import router


@pytest.fixture
def client():
    """创建 TestClient"""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestMemoryDistillRoutes:
    """Memory Distill API 路由测试"""

    def test_get_inputs_returns_episodes_and_decisions(self, client):
        """GET /api/memory/distill/inputs 返回 200 含 episodes/decisions 键"""
        with patch('adapters.inbound.fastapi_app.routes.memory_distill_async.MemoryDistiller') as mock_distiller_class:
            mock_distiller = MagicMock()
            mock_distiller_class.return_value = mock_distiller

            # Mock collect_inputs 返回值
            mock_distiller.collect_inputs.return_value = {
                "episodes": [{"id": 1, "title": "test"}],
                "decisions": [{"id": 2, "decision_type": "buy"}]
            }

            response = client.get("/api/memory/distill/inputs?days=7")

            assert response.status_code == 200
            data = response.json()
            assert "episodes" in data
            assert "decisions" in data
            assert len(data["episodes"]) == 1
            assert len(data["decisions"]) == 1
            mock_distiller.collect_inputs.assert_called_once_with(days=7)

    def test_post_candidates_skips_empty_evidence(self, client):
        """POST /api/memory/distill/candidates 无证据条目被跳过"""
        with patch('adapters.inbound.fastapi_app.routes.memory_distill_async.MemoryDistiller') as mock_distiller_class:
            mock_distiller = MagicMock()
            mock_distiller_class.return_value = mock_distiller

            # Mock save_candidates 返回值（模拟跳过无证据条目）
            mock_distiller.save_candidates.return_value = {
                "saved": 1,
                "skipped": 2
            }

            payload = {
                "candidates": [
                    {"title": "rule1", "content": "content1", "evidence_ids": [1, 2]},
                    {"title": "rule2", "content": "content2", "evidence_ids": []},
                    {"title": "rule3", "content": "content3"},
                ]
            }

            response = client.post("/api/memory/distill/candidates", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["saved"] == 1
            assert data["skipped"] == 2
            mock_distiller.save_candidates.assert_called_once()

    def test_post_candidates_requires_candidates_field(self, client):
        """POST /api/memory/distill/candidates 缺少 candidates 字段返回 400"""
        response = client.post("/api/memory/distill/candidates", json={})

        assert response.status_code == 400
        assert "candidates" in response.json()["detail"]
