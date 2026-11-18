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
    rule_id = resp.json()['data']['rule']['id']
    yield rule_id
    client.delete(f'/api/watch/rules/{rule_id}')


def test_create_and_list(client, created_rule):
    resp = client.get('/api/watch/rules?symbol=000001.SZ')
    assert resp.status_code == 200
    ids = [r['id'] for r in resp.json()['data']['rules']]
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
    assert resp.json()['data']['rule']['enabled'] is False


def test_update_invalid_expires_at_400(client, created_rule):
    resp = client.put(f'/api/watch/rules/{created_rule}', json={'expires_at': 'garbage'})
    assert resp.status_code == 400


def test_update_nonexistent_404(client):
    assert client.put('/api/watch/rules/99999999', json={'enabled': False}).status_code == 404


def test_patch_supported(client, created_rule):
    resp = client.patch(f'/api/watch/rules/{created_rule}', json={'context': 'patch 更新'})
    assert resp.status_code == 200
    assert resp.json()['data']['rule']['context'] == 'patch 更新'


def test_delete(client, created_rule):
    assert client.delete(f'/api/watch/rules/{created_rule}').json()['success'] is True


def test_delete_nonexistent_404(client):
    assert client.delete('/api/watch/rules/99999999').status_code == 404


def test_list_triggers(client):
    resp = client.get('/api/watch/triggers?limit=5')
    assert resp.status_code == 200
    assert 'triggers' in resp.json()['data']


def test_list_triggers_invalid_limit_falls_back(client):
    resp = client.get('/api/watch/triggers?limit=abc')
    assert resp.status_code == 200


def test_create_empty_conditions_400(client):
    resp = client.post('/api/watch/rules', json={'symbol': '600519.SH', 'conditions': []})
    assert resp.status_code == 400


def test_update_invalid_conditions_400(client, created_rule):
    resp = client.put(f'/api/watch/rules/{created_rule}',
                      json={'conditions': [{'type': 'magic'}]})
    assert resp.status_code == 400


def test_list_filter_by_symbol(client, created_rule):
    resp = client.get('/api/watch/rules?symbol=000001.SZ')
    assert resp.status_code == 200
    rules = resp.json()['data']['rules']
    assert len(rules) > 0
    assert all(r['symbol'] == '000001.SZ' for r in rules)


# ── 回归守护（2026-09-14）：处置类端点曾整体 500 ──────────────────────
# 背景：这三个端点的函数体里 import 的是
#   qs_watch.application.services.watch_engine.disposition   ← 该模块不存在
# 正确路径是 qs_watch.domain.watch.services.disposition。
# 因路由层此前无任何测试覆盖，线上 500 持续 3 天（89a42a99 引入）才被人工核查发现。
# 本测试的价值不在业务断言，而在**强制路由真正执行到底**：
# 错误导入、缺符号、函数体异常都会在此暴露，而不是等线上 500。
DISPOSITION_ENDPOINTS = [
    '/api/watch/triggers/stats',
    '/api/watch/triggers/unresolved',
    '/api/watch/triggers/digest',
]


@pytest.mark.parametrize('path', DISPOSITION_ENDPOINTS)
def test_disposition_endpoints_reachable(path):
    """处置类端点必须返回 200（守护：错误导入路径曾使其整体 500）"""
    app = FastAPI()
    app.include_router(router)
    # raise_server_exceptions=False：让 500 以状态码呈现，便于断言与定位
    resp = TestClient(app, raise_server_exceptions=False).get(path)
    assert resp.status_code == 200, f'{path} -> {resp.status_code}: {resp.text[:200]}'
    assert resp.json().get('success') is True


def test_agent_complete_route_returns_v2_delivery(client, monkeypatch):
    monkeypatch.setattr(
        'adapters.inbound.fastapi_app.routes.watch_async._run_agent_completion',
        lambda trigger_id, payload: {
            'trigger_id': trigger_id, 'delivered': True,
            'deduplicated': False, 'agent_response': payload,
        },
    )

    resp = client.post('/api/watch/triggers/88/agent-complete', json={
        'action': '卖出', 'reason': '止损线已破', 'disposition': 'handled',
    })

    assert resp.status_code == 200
    assert resp.json()['data']['trigger_id'] == 88
    assert resp.json()['data']['delivered'] is True


def test_agent_complete_route_maps_completion_error(client, monkeypatch):
    from qs_watch.application.services.watch_engine.v2.agent_completion import (
        AgentCompletionError,
    )

    def fail(trigger_id, payload):
        raise AgentCompletionError('触发记录不存在', 404)

    monkeypatch.setattr(
        'adapters.inbound.fastapi_app.routes.watch_async._run_agent_completion', fail)

    resp = client.post('/api/watch/triggers/999/agent-complete', json={
        'action': '观察', 'reason': '等待确认',
    })

    assert resp.status_code == 404
    assert resp.json()['success'] is False


def test_agent_complete_http_to_v2_card_and_idempotent_retry(client, monkeypatch):
    from types import SimpleNamespace
    import adapters.inbound.fastapi_app.routes.watch_async as watch_module
    from adapters.inbound.fastapi_app import watch_bootstrap_v2

    rule = SimpleNamespace(
        id=26, symbol='000425.SZ', intent='exit_stop', account='agent_virtual',
        cost_price=10.0, invalidation_threshold_pct=20.0,
        conditions=[{'type': 'price_break', 'params': {'price': 9.0}}],
        position_state='holding', process_state='pending',
    )
    trigger = SimpleNamespace(
        id=88, rule_id=26, symbol=rule.symbol, condition=rule.conditions[0],
        trigger_price=8.8, detail={'intent': 'exit_stop', 'message': '下破 9.0'},
        agent_response=None, disposition='pending', notified=False,
    )

    class Triggers:
        def get_by_id(self, trigger_id):
            return trigger if trigger_id == 88 else None

        def save_agent_response(self, trigger_id, response):
            trigger.agent_response = dict(response)

        def mark_notified(self, trigger_id, notified):
            trigger.notified = notified

        def update_disposition(self, trigger_id, disposition, reason, by):
            trigger.disposition = disposition
            return trigger

    class Rules:
        def get_by_id(self, rule_id):
            return rule if rule_id == 26 else None

        def update_fields(self, rule_id, **fields):
            for key, value in fields.items():
                setattr(rule, key, value)
            return rule

    sent = []
    monkeypatch.setattr(watch_module, 'WatchTriggerRepository', Triggers)
    monkeypatch.setattr(watch_module, 'WatchRuleRepository', Rules)
    monkeypatch.setattr(
        watch_bootstrap_v2, 'build_feishu_sender',
        lambda webhook_url='': lambda title, body: sent.append((title, body)) or True,
    )
    payload = {'action': '卖出', 'reason': '止损线已破', 'disposition': 'handled'}

    first = client.post('/api/watch/triggers/88/agent-complete', json=payload)
    second = client.post('/api/watch/triggers/88/agent-complete', json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()['data']['deduplicated'] is False
    assert second.json()['data']['deduplicated'] is True
    assert len(sent) == 1
    assert 'Agent 裁决' in sent[0][1] and '止损线已破' in sent[0][1]
    assert trigger.agent_response['notification_delivered'] is True
    assert trigger.disposition == 'handled'
    assert rule.process_state == 'processed'
