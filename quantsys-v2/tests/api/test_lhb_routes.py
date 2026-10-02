"""LHB API 路由测试（FastAPI 版）

2026-10-02（REQ-261001145152-3982 审查）：本文件原为 **Flask 时代**写法，4 条测试全部 ERROR：

1. 用了 `client` fixture 却**没有定义**（本目录各测试文件都自带一个）→ fixture not found；
2. patch 目标 `api.routes.sentiment.lhb_service` —— 那条路径（`api/routes/...`）随 Flask 层
   在 2026-08-19（54851df0）一起删除，早已不存在；
3. 断言用 `response.get_json()`（Flask API），且打的端点是 `/api/lhb/daily`——
   而线上只有 `/api/stock/{symbol}/lhb` 与 `/api/provider/lhb/daily/{date}`。

现改为：FastAPI TestClient + 真实端点 + 真实 patch 目标
（`sentiment_async.lhb_service`，路由里正是 `from adapters.shared.services import lhb_service`
后在端点内调用它）。第 4 条原意图「缺日期必须报错」在 FastAPI 下不成立——
live 路由把日期放在**路径参数**里，缺日期是 404 而非 400；故改为「服务异常必须被兜住」。
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from adapters.inbound.fastapi_app.routes.sentiment_async import router

PATCH_TARGET = 'adapters.inbound.fastapi_app.routes.sentiment_async.lhb_service'


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def provider_client():
    """provider 域的 router（prefix=/api/provider）——daily 端点在这里，不在 sentiment_async"""
    from adapters.inbound.fastapi_app.routes.data_provider_async import router as provider_router

    app = FastAPI()
    app.include_router(provider_router)
    return TestClient(app, raise_server_exceptions=False)


def test_api_stock_lhb_success(client):
    """个股龙虎榜：成功返回 200 与 payload"""
    with patch(PATCH_TARGET) as mock_service:
        mock_service.get_stock_lhb.return_value = {
            'success': True,
            'symbol': '600737',
            'name': '中粮糖业',
            'records': [{'date': '2026-05-31', 'reason': '日涨幅偏离值达7%'}],
        }

        response = client.get('/api/stock/600737/lhb?days=30')

        assert response.status_code == 200
        data = response.json()
        # api_response 契约：{"success": True, "data": <驼峰化数据>}（shared.py:69）
        assert data['success'] is True
        assert data['data']['symbol'] == '600737'


def test_api_stock_lhb_no_data(client):
    """个股龙虎榜：无数据时仍应 200 且如实返回 success=False"""
    with patch(PATCH_TARGET) as mock_service:
        mock_service.get_stock_lhb.return_value = {
            'success': False,
            'symbol': '600737',
            'records': [],
            'message': '无龙虎榜数据',
        }

        response = client.get('/api/stock/600737/lhb')

        assert response.status_code == 200
        data = response.json()
        # 外层是传输层 success（恒 True）；"无数据"由**内层**数据表达
        assert data['success'] is True
        assert data['data']['success'] is False


def test_api_daily_lhb_success(provider_client):
    """按日期汇总龙虎榜：走 provider router（prefix=/api/provider），成功 200"""
    payload = {'success': True, 'date': '2026-05-31', 'total_stocks': 1}
    with patch(
        'adapters.inbound.fastapi_app.routes.data_provider_async._call',
        return_value=payload,
    ):
        response = provider_client.get('/api/provider/lhb/daily/20260531')

        assert response.status_code == 200
        assert response.json()['total_stocks'] == 1


def test_api_stock_lhb_service_error_is_not_500_swallowed(client):
    """服务抛异常时不得静默返回“成功”（原「缺日期报错」意图在 FastAPI 下的等价物）

    原 intent：参数缺失必须**响亮报错**而不是当作正常结果。
    live 路由的日期在路径参数里（缺则是 404），故改为守住更值钱的那条：
    服务异常时响应**不能是 200 success**。
    """
    with patch(PATCH_TARGET) as mock_service:
        mock_service.get_stock_lhb.side_effect = RuntimeError('数据源不可用')

        response = client.get('/api/stock/600737/lhb')

        assert response.status_code != 200 or response.json().get('success') is not True
