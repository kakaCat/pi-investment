"""decisions FastAPI 路由 parity 测试（/api/decisions/*，走 DecisionService → PG）"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.decisions_async import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def recorded(client):
    resp = client.post('/api/decisions/record', json={
        'decision_type': 'screening',
        'reasoning': 'parity 测试决策',
        'context': {'market_phase': 'test'},
        'parameters': {'probe': True},
        'related_entity_type': 'pool',
        'related_entity_id': 'pytest-decisions-1',
        'session_key': 'pytest-session',
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body['success'] is True
    return body['data']


def test_record_decision_persists(client, recorded):
    assert recorded['decision_id'].startswith('DEC-')
    assert recorded['decision_type'] == 'screening'
    assert recorded['reasoning'] == 'parity 测试决策'
    assert recorded['session_key'] == 'pytest-session'


def test_record_decision_defaults_context_parameters(client):
    """agent 工具的 context/parameters 是可选的，缺省应按 {} 处理而不是报错"""
    resp = client.post('/api/decisions/record', json={
        'decision_type': 'screening',
        'reasoning': '省略 context/parameters',
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()['success'] is True


def test_get_decision(client, recorded):
    resp = client.get(f"/api/decisions/{recorded['decision_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['data']['decision_id'] == recorded['decision_id']


def test_get_decision_not_found_404(client):
    resp = client.get('/api/decisions/DEC-00000000000000-nonexistent')
    assert resp.status_code == 404
    assert resp.json()['success'] is False


def test_history_filter_by_entity(client, recorded):
    resp = client.get('/api/decisions/history?entity_type=pool&entity_id=pytest-decisions-1')
    assert resp.status_code == 200
    ids = [d['decision_id'] for d in resp.json()['data']]
    assert recorded['decision_id'] in ids


def test_report_requires_entity_params_400(client):
    resp = client.get('/api/decisions/report')
    assert resp.status_code == 400
    assert resp.json()['success'] is False


def test_report(client, recorded):
    resp = client.get('/api/decisions/report?entity_type=pool&entity_id=pytest-decisions-1')
    assert resp.status_code == 200
    data = resp.json()['data']
    assert data['total_decisions'] >= 1


def test_pool_changes(client):
    resp = client.get('/api/decisions/pool-changes/1')
    assert resp.status_code == 200
    assert resp.json()['success'] is True
    assert isinstance(resp.json()['data'], list)
