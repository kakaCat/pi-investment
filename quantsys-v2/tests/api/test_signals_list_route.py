"""/api/signals 列表端点参数路径回归测试（2026-08-13）

生产事故：该端点四条取数路径中三条因「路由 ↔ repository 契约漂移」损坏——
- date=today：get_signals_by_date_range 返回 ORM Signal 对象，下游 s.get() → 500
  （与 DailyOrchestrator MARKET_OPEN 'Signal' object has no attribute 'get' 同根因）
- date=YYYY-MM-DD：路由传 signal_type= kwarg，repo 签名是 action → TypeError
- days=N：路由传 days= kwarg，get_latest_signals 只认 limit → TypeError
仅无参路径（limit）存活。前端 Dashboard 待处理任务因此持续报错。
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.signals_async import router
from adapters.inbound.fastapi_app.routes import signals_async as signals_module


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestSignalsListParamPaths:
    def test_no_param_path(self, client):
        """基线路径（事故中唯一存活的）"""
        resp = client.get('/api/signals', params={'limit': 5})
        assert resp.status_code == 200
        assert resp.json()['success'] is True

    def test_date_today_path(self, client):
        """date=today：ORM → dict 归一化后不得 500"""
        resp = client.get('/api/signals', params={'date': 'today', 'limit': 5})
        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True, body.get('error')
        assert 'items' in body['data']

    def test_date_explicit_path(self, client):
        """date=YYYY-MM-DD：signal_type → action kwarg 映射"""
        resp = client.get('/api/signals', params={'date': '2026-08-12', 'limit': 5})
        assert resp.status_code == 200
        assert resp.json()['success'] is True, resp.json().get('error')

    def test_date_explicit_with_signal_type_filter(self, client):
        """signal_type=buy 小写入参须 upper 后匹配库内大写契约"""
        resp = client.get('/api/signals',
                          params={'date': '2026-08-12', 'signal_type': 'buy'})
        assert resp.status_code == 200
        assert resp.json()['success'] is True, resp.json().get('error')

    def test_days_path(self, client):
        """days=N：get_latest_signals 无 days 参数，须走 date_range"""
        resp = client.get('/api/signals', params={'days': 7, 'limit': 5})
        assert resp.status_code == 200
        assert resp.json()['success'] is True, resp.json().get('error')


def test_scan_defaults_to_read_only_even_with_high_score_candidate(client, monkeypatch):
    monkeypatch.setattr(signals_module, '_read_watchlist',
                        lambda: {'items': [{'symbol': '600519'}]})
    monkeypatch.setattr(signals_module.stock_pool_service, 'get_hot_stocks', lambda: [])
    monkeypatch.setattr(
        signals_module.scoring_service, 'score_stocks',
        lambda **kwargs: [{'symbol': '600519', 'name': '贵州茅台', 'score': 90,
                           'risk_level': 'medium', 'signal_type': 'buy'}])
    response = client.post('/api/signals/scan', json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['total'] == 1
    assert 'watch_rule_results' not in body and 'watch_rules_created' not in body


@pytest.mark.parametrize('payload', [
    {'auto_create_rules': True},
    {'auto_create_rules': True, 'account_name': 'agent_brain'},
    {'auto_create_rules': True, 'decision_audit_id': 'DA-scan'},
])
def test_scan_auto_rule_write_requires_account_and_audit(client, payload):
    response = client.post('/api/signals/scan', json=payload)
    assert response.status_code == 400
    assert 'account_name' in response.json()['error']
    assert 'decision_audit_id' in response.json()['error']
