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
