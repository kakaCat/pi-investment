"""watch FastAPI 路由 parity 测试"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.watch_async import router

VALID_CONDITIONS = [
    {'type': 'price_break', 'params': {'direction': 'above', 'price': 1800.0}},
]


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def created_rule(client):
    resp = client.post('/api/watch/rules', json={
        'symbol': '000001.SZ', 'conditions': VALID_CONDITIONS, 'context': 'parity 测试',
    })
    assert resp.status_code == 200, resp.json()
    rule_id = resp.json()['rule']['id']
    yield rule_id
    client.delete(f'/api/watch/rules/{rule_id}')


def test_create_and_list(client, created_rule):
    resp = client.get('/api/watch/rules?symbol=000001.SZ')
    assert resp.status_code == 200
    ids = [r['id'] for r in resp.json()['rules']]
    assert created_rule in ids


def test_create_invalid_condition_400(client):
    resp = client.post('/api/watch/rules', json={
        'symbol': '600519.SH', 'conditions': [{'type': 'magic', 'params': {}}],
    })
    assert resp.status_code == 400
    assert resp.json()['success'] is False


def test_create_conditions_not_list_400(client):
    resp = client.post('/api/watch/rules', json={'symbol': '600519.SH', 'conditions': 'abc'})
    assert resp.status_code == 400


def test_create_missing_symbol_400(client):
    resp = client.post('/api/watch/rules', json={'conditions': VALID_CONDITIONS})
    assert resp.status_code == 400


def test_update_disable(client, created_rule):
    resp = client.put(f'/api/watch/rules/{created_rule}', json={'enabled': False})
    assert resp.status_code == 200
    assert resp.json()['rule']['enabled'] is False


def test_update_invalid_expires_at_400(client, created_rule):
    resp = client.put(f'/api/watch/rules/{created_rule}', json={'expires_at': 'garbage'})
    assert resp.status_code == 400


def test_update_nonexistent_404(client):
    assert client.put('/api/watch/rules/99999999', json={'enabled': False}).status_code == 404


def test_patch_supported(client, created_rule):
    resp = client.patch(f'/api/watch/rules/{created_rule}', json={'context': 'patch 更新'})
    assert resp.status_code == 200
    assert resp.json()['rule']['context'] == 'patch 更新'


def test_delete(client, created_rule):
    assert client.delete(f'/api/watch/rules/{created_rule}').json()['success'] is True


def test_delete_nonexistent_404(client):
    assert client.delete('/api/watch/rules/99999999').status_code == 404


def test_list_triggers(client):
    resp = client.get('/api/watch/triggers?limit=5')
    assert resp.status_code == 200
    assert 'triggers' in resp.json()


def test_list_triggers_invalid_limit_falls_back(client):
    resp = client.get('/api/watch/triggers?limit=abc')
    assert resp.status_code == 200
