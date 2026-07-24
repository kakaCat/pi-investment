"""SessionService 测试：事件摄入幂等、计数器、诊断聚合"""
import pytest
from datetime import datetime, timezone
from infrastructure.persistence.database.base_repository import BaseRepository
from application.services.session_service import SessionService

DDL = """
CREATE TABLE IF NOT EXISTS quant.agent_sessions (
  session_key TEXT PRIMARY KEY, channel VARCHAR(20) NOT NULL, peer_id VARCHAR(200) NOT NULL,
  agent_id VARCHAR(50) NOT NULL DEFAULT 'main',
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  message_count INT DEFAULT 0, tool_call_count INT DEFAULT 0, error_count INT DEFAULT 0
);
CREATE TABLE IF NOT EXISTS quant.agent_session_events (
  id BIGSERIAL PRIMARY KEY,
  session_key TEXT NOT NULL, seq INT NOT NULL,
  event_type VARCHAR(30) NOT NULL, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(session_key, seq)
);
"""


@pytest.fixture
def service():
    repo = BaseRepository()
    cursor = repo._get_cursor()
    cursor.execute(DDL)
    cursor.execute("DELETE FROM quant.agent_session_events")
    cursor.execute("DELETE FROM quant.agent_sessions")
    repo.db.commit()
    yield SessionService()


def _ev(seq, etype, payload, key="agent:main:wake:default"):
    return {
        "session_key": key, "seq": seq, "event_type": etype,
        "payload": payload, "created_at": datetime.now(timezone.utc).isoformat(),
    }


def test_ingest_events_creates_session_and_counts(service):
    result = service.ingest_events([
        _ev(1, "session_start", {"channel": "wake", "peerId": "default", "agentId": "main"}),
        _ev(2, "user_message", {"messageId": "m1", "text": "hi"}),
        _ev(3, "tool_call", {"toolName": "pool_manage", "durationMs": 1200, "success": True}),
        _ev(4, "assistant_reply", {"text": "done", "replyLength": 4}),
    ])
    assert result["accepted"] == 4

    session = service.get_session("agent:main:wake:default")
    assert session["channel"] == "wake"
    assert session["message_count"] == 1
    assert session["tool_call_count"] == 1
    assert session["error_count"] == 0


def test_ingest_events_idempotent(service):
    events = [_ev(1, "session_start", {"channel": "wake", "peerId": "default", "agentId": "main"})]
    service.ingest_events(events)
    result = service.ingest_events(events)  # 重复推送
    assert result["accepted"] == 0
    assert result["duplicates"] == 1

    session = service.get_session("agent:main:wake:default")
    assert session["message_count"] == 0


def test_diagnosis_aggregates(service):
    service.ingest_events([
        _ev(1, "session_start", {"channel": "wake", "peerId": "default", "agentId": "main"}),
        _ev(2, "tool_call", {"toolName": "a", "durationMs": 100, "success": True}),
        _ev(3, "tool_call", {"toolName": "b", "durationMs": 300, "success": False, "error": "timeout"}),
        _ev(4, "error", {"stage": "prompt", "message": "boom"}),
    ])
    diag = service.get_diagnosis("agent:main:wake:default")
    assert diag["tool_success_rate"] == 0.5
    assert diag["avg_tool_duration_ms"] == 200
    assert diag["error_count"] == 1
    assert diag["insight"]
