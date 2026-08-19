"""orders + portfolio 域 parity 测试（P5）"""
import pytest
from tests.migration.parity import assert_parity

ORDERS_LIST = "/api/orders/list"
ORDER_DETAIL = "/api/orders/detail/999999"
ORDER_CREATE = "/api/orders/create"
TRADES = "/api/trades/list"
POSITIONS = "/api/portfolio/positions"
SUMMARY = "/api/portfolio/summary"
HISTORY = "/api/portfolio/history"
HOLDINGS = "/api/portfolio/holdings"
ALLOCATION = "/api/portfolio/allocation"
EQUITY = "/api/portfolio/equity-curve"


def test_orders_list(fastapi_client):
    assert_parity(fastapi_client, "GET", ORDERS_LIST, params={"page": 1, "pageSize": 5})


def test_order_detail_not_found(fastapi_client):
    assert_parity(fastapi_client, "GET", ORDER_DETAIL)


def test_create_order_missing_fields(fastapi_client):
    assert_parity(fastapi_client, "POST", ORDER_CREATE, json_body={"symbol": "600519"})


def test_create_order_from_signal_missing_id(fastapi_client):
    body = {"symbol": "600519", "action": "buy", "orderType": "limit", "quantity": 100, "fromSignal": True}
    assert_parity(fastapi_client, "POST", ORDER_CREATE, json_body=body)


def test_trades_list(fastapi_client):
    assert_parity(fastapi_client, "GET", TRADES, params={"page": 1, "pageSize": 5})


def test_positions(fastapi_client):
    assert_parity(fastapi_client, "GET", POSITIONS)


def test_summary(fastapi_client):
    assert_parity(fastapi_client, "GET", SUMMARY)


def test_history(fastapi_client):
    assert_parity(fastapi_client, "GET", HISTORY, params={"days": 30})


def test_holdings(fastapi_client):
    assert_parity(fastapi_client, "GET", HOLDINGS)


def test_allocation(fastapi_client):
    assert_parity(fastapi_client, "GET", ALLOCATION)


def test_equity_curve(fastapi_client):
    assert_parity(fastapi_client, "GET", EQUITY)
