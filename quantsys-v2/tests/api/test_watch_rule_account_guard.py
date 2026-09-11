"""规则账户硬校验的 API 层契约（2026-09-11，w-aebfddcd）

没有账户的规则不能进入买卖；观察类规则仍可无账户。
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.watch_async import router

VALID = [{"type": "price_break", "params": {"direction": "below", "price": 10.0}}]


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_entry_rule_without_account_400(client):
    resp = client.post('/api/watch/rules', json={
        'symbol': '000001.SZ', 'conditions': VALID, 'intent': 'entry'})
    assert resp.status_code == 400
    assert '不能进入买卖' in resp.json()['error']


def test_entry_rule_with_account_ok(client):
    resp = client.post('/api/watch/rules', json={
        'symbol': '000001.SZ', 'conditions': VALID, 'intent': 'entry',
        'linked_account': 'agent_virtual'})
    assert resp.status_code == 200, resp.json()
    rule_id = resp.json()['data']['rule']['id']
    assert resp.json()['data']['rule']['linked_account'] == 'agent_virtual'
    client.delete(f'/api/watch/rules/{rule_id}')


def test_observe_rule_without_account_ok(client):
    resp = client.post('/api/watch/rules', json={
        'symbol': '000002.SZ', 'conditions': VALID, 'intent': 'trend_observe'})
    assert resp.status_code == 200, resp.json()
    client.delete(f"/api/watch/rules/{resp.json()['data']['rule']['id']}")


def test_buy_action_hint_without_account_400(client):
    """没写 intent 但 action_on_trigger=buy 的规则照样拦（防绕过）"""
    resp = client.post('/api/watch/rules', json={
        'symbol': '000003.SZ', 'conditions': VALID,
        'action_hint': {'action_on_trigger': 'buy'}})
    assert resp.status_code == 400


def test_patch_turning_observe_into_trade_without_account_400(client):
    resp = client.post('/api/watch/rules', json={
        'symbol': '000004.SZ', 'conditions': VALID, 'intent': 'trend_observe'})
    rule_id = resp.json()['data']['rule']['id']
    try:
        bad = client.patch(f'/api/watch/rules/{rule_id}', json={'intent': 'entry'})
        assert bad.status_code == 400
        # 补上账户后即可
        ok = client.patch(f'/api/watch/rules/{rule_id}',
                          json={'intent': 'entry', 'linked_account': 'agent_brain'})
        assert ok.status_code == 200, ok.json()
        # 但不许再把账户清空
        bad2 = client.patch(f'/api/watch/rules/{rule_id}', json={'linked_account': None})
        assert bad2.status_code == 400
    finally:
        client.delete(f'/api/watch/rules/{rule_id}')
