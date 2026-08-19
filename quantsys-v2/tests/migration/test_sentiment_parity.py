"""sentiment 域 parity 测试（agent 迁移）

情绪/资金数据为实时网络数据：成功响应用 assert_structural_parity（结构+状态码）。
"""
from tests.migration.parity import assert_structural_parity

SYMBOL = "600519"


def test_fund_flow(fastapi_client):
    assert_structural_parity(fastapi_client, "GET",
                             f"/api/stock/{SYMBOL}/fund-flow", params={"days": 5})


def test_margin(fastapi_client):
    assert_structural_parity(fastapi_client, "GET",
                             f"/api/stock/{SYMBOL}/margin", params={"days": 5})


def test_lhb(fastapi_client):
    assert_structural_parity(fastapi_client, "GET",
                             f"/api/stock/{SYMBOL}/lhb", params={"days": 30})


def test_fund_holdings(fastapi_client):
    assert_structural_parity(fastapi_client, "GET",
                             f"/api/stock/{SYMBOL}/fund-holdings")


def test_top_holders(fastapi_client):
    assert_structural_parity(fastapi_client, "GET",
                             f"/api/stock/{SYMBOL}/top-holders",
                             params={"holder_type": "all"})


def test_holder_changes(fastapi_client):
    assert_structural_parity(fastapi_client, "GET",
                             f"/api/stock/{SYMBOL}/holder-changes", params={"periods": 4})


def test_top_fund_stocks(fastapi_client):
    assert_structural_parity(fastapi_client, "GET",
                             "/api/sentiment/top-fund-stocks",
                             params={"fund_type": "all", "limit": 10})
