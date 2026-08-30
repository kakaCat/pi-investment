"""DataProvider API 单元测试

测试 /api/provider/* 端点的路由存在性和基本响应格式。
使用 FastAPI TestClient + mock DataProviderManager，不需要启动服务器。
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_manager():
    """创建 mock DataProviderManager"""
    mgr = MagicMock()
    mgr.get_provider_health.return_value = {"success": True, "data": {"healthy": True}}
    mgr.get_provider_stats.return_value = {"success": True, "data": {"total_requests": 0}}
    mgr.get_quote.return_value = {"success": True, "data": {"symbol": "000001", "price": 10.5}}
    mgr.get_klines.return_value = {"success": True, "data": []}
    mgr.get_financial.return_value = {"success": True, "data": {"symbol": "000001"}}
    mgr.get_sector_list.return_value = {"success": True, "data": {"sectors": []}}
    mgr.get_sector_stocks.return_value = {"success": True, "data": {"stocks": []}}
    mgr.get_market_overview.return_value = {"success": True, "data": {"index": "sh000001"}}
    mgr.get_macro_data.return_value = {"success": True, "data": {}}
    mgr.get_market_news.return_value = {"success": True, "data": {"news": []}}
    mgr.get_dividends.return_value = {"success": True, "data": {"dividends": []}}
    mgr.get_hk_market_overview.return_value = {"success": True, "data": {}}
    mgr.get_trading_calendar.return_value = {"success": True, "data": {"trading_days": []}}
    return mgr


@pytest.fixture
def client(mock_manager):
    """创建测试客户端（mock DataProviderManager）

    patch 在 fixture 级别激活，整个测试生命周期内 mock 都生效。
    """
    with patch(
        "adapters.outbound.datasources.get_data_provider_manager",
        return_value=mock_manager,
    ), patch(
        "adapters.outbound.datasources.manager.get_data_provider_manager",
        return_value=mock_manager,
    ):
        app = FastAPI()
        from adapters.inbound.fastapi_app.routes.data_provider_async import router
        app.include_router(router)
        yield TestClient(app)


class TestDataProviderRoutes:
    """测试所有 DataProvider API 路由"""

    def test_health_endpoint(self, client):
        response = client.get("/api/provider/health")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_stats_endpoint(self, client):
        response = client.get("/api/provider/stats")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_quote_endpoint(self, client):
        response = client.get("/api/provider/quote/000001")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_kline_endpoint(self, client):
        response = client.get(
            "/api/provider/kline/000001",
            params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_financial_endpoint(self, client):
        response = client.get("/api/provider/financial/000001")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_sector_list_endpoint(self, client):
        response = client.get("/api/provider/sectors")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_sector_stocks_endpoint(self, client):
        response = client.get("/api/provider/sector/银行/stocks")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_market_overview_endpoint(self, client):
        response = client.get("/api/provider/market/overview")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_market_macro_endpoint(self, client):
        response = client.get("/api/provider/market/macro")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_market_news_endpoint(self, client):
        response = client.get("/api/provider/market/news")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_dividend_endpoint(self, client):
        response = client.get("/api/provider/dividend/000001")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_hk_overview_endpoint(self, client):
        response = client.get("/api/provider/hk/overview")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_trading_calendar_endpoint(self, client):
        response = client.get("/api/provider/trading-calendar")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_all_routes_registered(self, client):
        """通过实际请求验证所有关键路由可达"""
        endpoints = [
            "/api/provider/health",
            "/api/provider/stats",
            "/api/provider/quote/000001",
            "/api/provider/kline/000001?start_date=2024-01-01&end_date=2024-01-31",
            "/api/provider/financial/000001",
            "/api/provider/sectors",
            "/api/provider/sector/银行/stocks",
            "/api/provider/market/overview",
            "/api/provider/market/macro",
            "/api/provider/market/news",
            "/api/provider/dividend/000001",
            "/api/provider/hk/overview",
            "/api/provider/trading-calendar",
        ]
        for endpoint in endpoints:
            resp = client.get(endpoint)
            assert resp.status_code == 200, f"{endpoint} returned {resp.status_code}"


class TestDataProviderResponseFormat:
    """测试响应格式一致性"""

    def test_health_response_shape(self, client):
        data = client.get("/api/provider/health").json()
        assert "success" in data

    def test_stats_response_shape(self, client):
        data = client.get("/api/provider/stats").json()
        assert "success" in data

    def test_quote_response_shape(self, client):
        data = client.get("/api/provider/quote/000001").json()
        assert "success" in data

    def test_kline_response_shape(self, client):
        data = client.get(
            "/api/provider/kline/000001",
            params={"start_date": "2024-01-01", "end_date": "2024-01-31"},
        ).json()
        assert "success" in data

    def test_financial_response_shape(self, client):
        data = client.get("/api/provider/financial/000001").json()
        assert "success" in data
