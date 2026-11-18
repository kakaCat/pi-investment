from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes import t_trade_async
from qs_trading.domain.trading.exceptions import TradingError


def client_with(service, watch):
    app = FastAPI()
    app.include_router(t_trade_async.router)
    original = t_trade_async._build_services
    t_trade_async._build_services = lambda: (service, watch)
    client = TestClient(app)
    client._original_build_services = original
    return client


def cycle_dict(cycle_id=7):
    return {
        "id": cycle_id, "t_trade_id": cycle_id, "account": "agent_brain",
        "symbol": "002007", "status": "waiting_sell", "mode": "auto_sim",
    }


def test_create_returns_cycle_and_rule_sync():
    cycle = SimpleNamespace(to_dict=lambda: cycle_dict())
    service = SimpleNamespace(create_cycle=Mock(return_value=cycle))
    watch = SimpleNamespace(reconcile=Mock(return_value={"status": "ok"}))
    client = client_with(service, watch)
    try:
        response = client.post("/api/t-trades", json={
            "account": "agent_brain", "symbol": "002007", "upper_price": 13.55,
            "lower_price": 12.19, "shares": 100, "reason": "明确区间内验证反向做T",
        })
        assert response.status_code == 201, response.text
        assert response.json()["data"]["cycle"]["id"] == 7
        assert response.json()["data"]["rule_sync"] == {"status": "ok"}
    finally:
        t_trade_async._build_services = client._original_build_services


def test_execute_maps_remind_only_authorization_to_403():
    service = SimpleNamespace(execute=Mock(side_effect=TradingError("禁止代下单", 403)))
    client = client_with(service, SimpleNamespace())
    try:
        response = client.post("/api/t-trades/7/execute", json={})
        assert response.status_code == 403
        assert response.json()["success"] is False
    finally:
        t_trade_async._build_services = client._original_build_services


def test_execute_returns_trade_fact_even_when_rule_sync_needs_retry():
    cycle = SimpleNamespace(to_dict=lambda: cycle_dict())
    service = SimpleNamespace(
        execute=Mock(return_value={"trade": {"trade_id": 11}, "cycle": cycle_dict()}),
        get_cycle=Mock(return_value=cycle),
    )
    watch = SimpleNamespace(reconcile=Mock(side_effect=RuntimeError("rule unavailable")))
    client = client_with(service, watch)
    try:
        response = client.post("/api/t-trades/7/execute", json={})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["trade"]["trade_id"] == 11
        assert data["rule_sync"]["status"] == "error"
        assert data["rule_sync"]["retry"] == "reconcile"
    finally:
        t_trade_async._build_services = client._original_build_services


def test_record_fill_requires_and_passes_real_trade_id():
    cycle = SimpleNamespace(to_dict=lambda: cycle_dict())
    service = SimpleNamespace(record_fill=Mock(return_value=cycle))
    watch = SimpleNamespace(reconcile=Mock(return_value={"status": "ok"}))
    client = client_with(service, watch)
    try:
        response = client.post("/api/t-trades/7/record-fill", json={"trade_id": 19})
        assert response.status_code == 200
        service.record_fill.assert_called_once_with(7, 19)
    finally:
        t_trade_async._build_services = client._original_build_services
