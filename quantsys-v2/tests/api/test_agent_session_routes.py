"""agent sessions API 路由测试"""
import pytest
from adapters.inbound.api.server import create_app
from infrastructure.persistence.database.engine import db_cursor
from tests.services.test_session_service import DDL


@pytest.fixture
def client():
    with db_cursor(commit=True) as cursor:
        cursor.execute(DDL)
        cursor.execute("DELETE FROM quant.agent_session_events")
        cursor.execute("DELETE FROM quant.agent_sessions")

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_post_events_and_get_sessions(client):
    resp = client.post("/api/sessions/events", json={
        "events": [{
            "session_key": "agent:main:wake:default", "seq": 1,
            "event_type": "session_start",
            "payload": {"channel": "wake", "peerId": "default", "agentId": "main"},
            "created_at": "2026-07-24T02:00:00+00:00",
        }]
    })
    assert resp.status_code == 200
    assert resp.get_json()["data"]["accepted"] == 1

    resp = client.get("/api/sessions")
    data = resp.get_json()["data"]
    assert any(s["session_key"] == "agent:main:wake:default" for s in data["sessions"])

    resp = client.get("/api/sessions/agent:main:wake:default/events")
    events = resp.get_json()["data"]["events"]
    assert events[0]["event_type"] == "session_start"

    resp = client.get("/api/sessions/agent:main:wake:default/diagnosis")
    assert resp.get_json()["data"]["session_key"] == "agent:main:wake:default"


def test_post_events_rejects_empty(client):
    resp = client.post("/api/sessions/events", json={"events": []})
    assert resp.status_code == 400
