"""agent sessions 域 parity 测试（Flask ↔ FastAPI）

背景：agent gateway SessionSyncer POST /api/sessions/events 打到 FastAPI 5001 一直 404，
根因是 FastAPI 缺整个 /api/sessions/* 路由组（Flask 蓝图 agent_sessions.py 未迁移）。
本文件冻结 6 条路由的双端契约。
"""
import pytest

from tests.migration.parity import assert_parity
from tests.services.test_session_service import DDL

KEY = "agent:main:wake:default"
SEED = {
    "events": [{
        "session_key": KEY, "seq": 1,
        "event_type": "session_start",
        "payload": {"channel": "wake", "peerId": "default", "agentId": "main"},
        "created_at": "2026-07-24T02:00:00+00:00",
    }]
}


@pytest.fixture(autouse=True)
def sessions_tables():
    """建表 + 清数据（与 Flask 版 test_agent_session_routes.py 同一契约）"""
    _clean_tables()
    yield


def _clean_tables():
    from infrastructure.persistence.database.base_repository import BaseRepository
    repo = BaseRepository()
    cursor = repo._get_cursor()
    cursor.execute(DDL)
    cursor.execute("DELETE FROM quant.agent_session_events")
    cursor.execute("DELETE FROM quant.agent_sessions")
    repo.db.commit()


@pytest.fixture
def seeded(flask_client):
    """通过 Flask 端写入一条事件（POST 单独有用例，这里只造数据）"""
    resp = flask_client.open("/api/sessions/events", method="POST", json=SEED)
    assert resp.status_code == 200


def test_post_events(flask_client, fastapi_client):
    """幂等摄入端点：两端共享同一测试库，第二次写入必为 duplicate，
    无法用 assert_parity 同库连打——清库后各自独立验证响应契约一致"""
    f = flask_client.open("/api/sessions/events", method="POST", json=SEED)
    _clean_tables()
    fa = fastapi_client.request("POST", "/api/sessions/events", json=SEED)
    assert f.status_code == fa.status_code == 200
    assert fa.json() == f.get_json()
    _clean_tables()


def test_post_events_rejects_empty(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/sessions/events", json_body={"events": []})


def test_list_sessions(flask_client, fastapi_client, seeded):
    assert_parity(flask_client, fastapi_client, "GET", "/api/sessions")


def test_get_session(flask_client, fastapi_client, seeded):
    assert_parity(flask_client, fastapi_client, "GET", f"/api/sessions/{KEY}")


def test_get_session_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", "/api/sessions/agent:nope")


def test_get_events(flask_client, fastapi_client, seeded):
    assert_parity(flask_client, fastapi_client, "GET", f"/api/sessions/{KEY}/events")


def test_get_diagnosis(flask_client, fastapi_client, seeded):
    assert_parity(flask_client, fastapi_client, "GET", f"/api/sessions/{KEY}/diagnosis")


def test_ai_diagnosis(flask_client, fastapi_client, seeded, monkeypatch):
    """ai-diagnosis 走外部 LLM，mock 掉 service 避免真实调用；两端应同样映射 RuntimeError→503"""
    from application.services.session_service import SessionService

    def _boom(self, session_key, refresh=False):
        raise RuntimeError("LLM unavailable (test)")

    monkeypatch.setattr(SessionService, "ai_diagnosis", _boom)
    assert_parity(flask_client, fastapi_client, "POST", f"/api/sessions/{KEY}/ai-diagnosis")
