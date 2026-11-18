from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes import quote_market_async
import qs_market_data.adapters.outbound.datasources as datasources
from qs_market_data.adapters.outbound.datasources.manager import DataProviderManager


def test_minute_period_uses_minute_provider_chain():
    manager = DataProviderManager.__new__(DataProviderManager)
    expected = {"success": True, "data": [], "source": "tencent_minute"}
    manager.get_minute_klines = Mock(return_value=expected)
    result = manager.get_klines("002007", "5m", "2026-11-02", "2026-11-02")
    assert result is expected
    manager.get_minute_klines.assert_called_once_with(
        "002007", "5m", "2026-11-02", "2026-11-02", limit=500,
    )


def test_history_serializes_minute_timestamp_not_daily_date(monkeypatch):
    bar = SimpleNamespace(
        trade_datetime="2026-11-02 10:05:00", open=12.10, high=12.22,
        low=12.08, close=12.20, volume=120000,
    )
    provider = SimpleNamespace(
        get_klines=Mock(return_value={"success": True, "data": [bar], "source": "sina_minute"})
    )
    monkeypatch.setattr(datasources, "get_data_provider_manager", lambda: provider)
    app = FastAPI()
    app.include_router(quote_market_async.router)
    response = TestClient(app).get("/api/stock/002007/history?period=5m&limit=2")
    assert response.status_code == 200, response.text
    row = response.json()["data"]["data"][0]
    assert row["date"] == "2026-11-02 10:05:00"
    assert row["close"] == 12.20
