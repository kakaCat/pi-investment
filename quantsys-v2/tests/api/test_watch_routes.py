"""watch Flask 路由测试（蓝图级 test_client，不经 server.py）"""
import pytest
from flask import Flask

from adapters.inbound.api.routes.watch import watch_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(watch_bp)
    return app.test_client()


VALID_CONDITIONS = [
    {'type': 'price_break', 'params': {'direction': 'above', 'price': 1800.0}},
    {'type': 'pnl_pct', 'params': {'direction': 'below', 'pct': -8.0}},
]


@pytest.fixture
def created_rule(client):
    resp = client.post('/api/watch/rules', json={
        'symbol': '600519.SH',
        'conditions': VALID_CONDITIONS,
        'context': '测试盯盘',
        'cost_price': 1700.0,
    })
    assert resp.status_code == 200, resp.get_json()
    rule_id = resp.get_json()['rule']['id']
    yield rule_id
    client.delete(f'/api/watch/rules/{rule_id}')


class TestCreate:
    def test_create_success(self, created_rule):
        assert isinstance(created_rule, int)

    def test_missing_symbol_400(self, client):
        resp = client.post('/api/watch/rules', json={'conditions': VALID_CONDITIONS})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_invalid_condition_400(self, client):
        resp = client.post('/api/watch/rules', json={
            'symbol': '600519.SH',
            'conditions': [{'type': 'magic', 'params': {}}],
        })
        assert resp.status_code == 400

    def test_empty_conditions_400(self, client):
        resp = client.post('/api/watch/rules', json={'symbol': '600519.SH', 'conditions': []})
        assert resp.status_code == 400

    def test_conditions_not_list_400(self, client):
        resp = client.post('/api/watch/rules', json={'symbol': '600519.SH', 'conditions': 'abc'})
        assert resp.status_code == 400


class TestList:
    def test_list_contains_created(self, client, created_rule):
        resp = client.get('/api/watch/rules')
        assert resp.status_code == 200
        ids = [r['id'] for r in resp.get_json()['rules']]
        assert created_rule in ids

    def test_filter_by_symbol(self, client, created_rule):
        resp = client.get('/api/watch/rules?symbol=600519.SH')
        rules = resp.get_json()['rules']
        assert len(rules) > 0
        assert all(r['symbol'] == '600519.SH' for r in rules)


class TestUpdate:
    def test_disable_rule(self, client, created_rule):
        resp = client.put(f'/api/watch/rules/{created_rule}', json={'enabled': False})
        assert resp.status_code == 200
        assert resp.get_json()['rule']['enabled'] is False

    def test_update_nonexistent_404(self, client):
        resp = client.put('/api/watch/rules/99999999', json={'enabled': False})
        assert resp.status_code == 404

    def test_update_invalid_conditions_400(self, client, created_rule):
        resp = client.put(f'/api/watch/rules/{created_rule}',
                          json={'conditions': [{'type': 'magic'}]})
        assert resp.status_code == 400

    def test_update_invalid_expires_at_400(self, client, created_rule):
        resp = client.put(f'/api/watch/rules/{created_rule}', json={'expires_at': 'garbage'})
        assert resp.status_code == 400


class TestDelete:
    def test_delete(self, client, created_rule):
        resp = client.delete(f'/api/watch/rules/{created_rule}')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_delete_nonexistent_404(self, client):
        assert client.delete('/api/watch/rules/99999999').status_code == 404


class TestTriggers:
    def test_list_triggers(self, client):
        resp = client.get('/api/watch/triggers?limit=5')
        assert resp.status_code == 200
        assert 'triggers' in resp.get_json()

    def test_invalid_limit_falls_back(self, client):
        resp = client.get('/api/watch/triggers?limit=abc')
        assert resp.status_code == 200
