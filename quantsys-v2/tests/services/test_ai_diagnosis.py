"""AI 诊断端点测试：成功/超时/未配置 key/缓存命中"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from infrastructure.persistence.database.engine import db_cursor
from application.services.session_service import SessionService
from tests.services.test_session_service import DDL


@pytest.fixture
def service():
    with db_cursor(commit=True) as cursor:
        cursor.execute(DDL)
        cursor.execute("ALTER TABLE quant.agent_sessions ADD COLUMN IF NOT EXISTS ai_diagnosis JSONB")
        cursor.execute("ALTER TABLE quant.agent_sessions ADD COLUMN IF NOT EXISTS ai_diagnosis_at TIMESTAMPTZ")
        cursor.execute("DELETE FROM quant.agent_session_events")
        cursor.execute("DELETE FROM quant.agent_sessions")
    s = SessionService()
    s.ingest_events([{
        "session_key": "agent:main:wake:e2e", "seq": 1, "event_type": "session_start",
        "payload": {"channel": "wake", "peerId": "e2e", "agentId": "main"},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, {
        "session_key": "agent:main:wake:e2e", "seq": 2, "event_type": "tool_call",
        "payload": {"toolName": "pool_manage", "durationMs": 100, "success": True},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }])
    yield s


def test_ai_diagnosis_success(service, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'sk-test')
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {'choices': [{'message': {'content': '做得好：X\n问题：Y\n建议：Z'}}]}

    with patch('application.services.llm_service.requests.post', return_value=fake_resp):
        result = service.ai_diagnosis('agent:main:wake:e2e')

    assert '做得好' in result['analysis']
    assert result['cached'] is False


def test_ai_diagnosis_cached_no_second_call(service, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'sk-test')
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {'choices': [{'message': {'content': '分析内容'}}]}

    with patch('application.services.llm_service.requests.post', return_value=fake_resp) as mock_post:
        service.ai_diagnosis('agent:main:wake:e2e')
        second = service.ai_diagnosis('agent:main:wake:e2e')

    assert mock_post.call_count == 1  # 第二次走缓存
    assert second['cached'] is True


def test_ai_diagnosis_no_api_key(service, monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    with pytest.raises(RuntimeError, match='DEEPSEEK_API_KEY'):
        service.ai_diagnosis('agent:main:wake:e2e')


def test_ai_diagnosis_refresh_forces_regenerate(service, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'sk-test')
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {'choices': [{'message': {'content': '新分析'}}]}

    with patch('application.services.llm_service.requests.post', return_value=fake_resp) as mock_post:
        service.ai_diagnosis('agent:main:wake:e2e')
        service.ai_diagnosis('agent:main:wake:e2e', refresh=True)

    assert mock_post.call_count == 2
