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


def test_orders_list(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", ORDERS_LIST, params={"page": 1, "pageSize": 5})


def test_order_detail_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", ORDER_DETAIL)


def test_create_order_missing_fields(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", ORDER_CREATE, json_body={"symbol": "600519"})


def test_create_order_from_signal_missing_id(flask_client, fastapi_client):
    body = {"symbol": "600519", "action": "buy", "orderType": "limit", "quantity": 100, "fromSignal": True}
    assert_parity(flask_client, fastapi_client, "POST", ORDER_CREATE, json_body=body)


def test_trades_list(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", TRADES, params={"page": 1, "pageSize": 5})


def test_positions(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", POSITIONS)


def test_summary(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", SUMMARY)


def test_history(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", HISTORY, params={"days": 30})


def test_holdings(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", HOLDINGS)


def test_allocation(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", ALLOCATION)


def test_equity_curve(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", EQUITY)
