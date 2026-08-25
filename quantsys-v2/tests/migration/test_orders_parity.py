"""orders + portfolio 域 parity 测试（P5）

⚠️ DEPRECATED（2026-08-25）:
本文件原用于 Flask↔FastAPI 迁移比对，Flask 已删除（2026-08），现仅作 FastAPI
端点 <500 冒烟守卫。其中大部分端点已属于旧订单体系（quant.orders / quant.holdings），
将在 Phase 3（2026-09-25）随旧路由一并下线，本文件届时删除。

- /api/orders/create 已返回 410 Gone（2026-08-25 废弃），相关测试已移除。
- 新交易走 /api/simulation/accounts/{account_name}/trade，覆盖见 test_api_smoke.py。
- 新持仓/汇总走 /api/portfolio/positions|summary（需 account_name），见 simulation 域测试。
"""
from tests.migration.parity import assert_parity

ORDERS_LIST = "/api/orders/list"
ORDER_DETAIL = "/api/orders/detail/999999"
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
