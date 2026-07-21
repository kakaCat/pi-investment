"""market_data 域 parity 测试（market.py / quote_market.py → market_data_async.py 迁移）

行情/港股数据为实时网络数据：成功响应用 assert_structural_parity（结构+状态码），
确定性错误路径（缺参 400、既有 500 bug）用 assert_parity（逐值比对）。
"""
import pytest
from tests.migration.parity import assert_parity, assert_structural_parity


# ============ A 股市场数据（实时网络 → 结构比对） ============

def test_sectors(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/market/sectors")


def test_macro(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/market/macro")


def test_news(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/market/news",
                             params={"limit": 5})


def test_margin(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/market/margin")


def test_hot_stocks(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/market/hot-stocks",
                             params={"market": "A股", "mode": "first"})


def test_sector_flow(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/market/sector-flow")


def test_concepts(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/market/concepts")


def test_concept_stocks(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             "/api/market/concept/锂电池/stocks")


def test_north_flow(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/market/north-flow")


# ============ 指数历史（确定性错误路径 → 逐值比对） ============

def test_index_history_missing_params(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", "/api/market/index-history")


def test_index_history(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/market/index-history",
                             params={"symbol": "sh000300",
                                     "start_date": "2026-06-01", "end_date": "2026-06-10"})


# ============ 港股数据（实时网络 → 结构比对） ============

def test_hk_overview(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/hk/overview")


def test_hk_south_flow(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/hk/south-flow")


def test_hk_hot_rank(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/hk/hot-rank")


def test_hk_technical(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/hk/00700/technical")


def test_hk_financials(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/hk/00700/financials")


def test_hk_analysis(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/hk/00700/analysis")


# ============ 板块成分 / 市场概览（quote_market.py） ============

def test_sector_stocks(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/market/sector/银行",
                             params={"limit": 5})


def test_sector_stocks_not_found(flask_client, fastapi_client):
    # 不存在的板块：两边均应走同一错误路径（404/502，结构一致）
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             "/api/market/sector/不存在的板块xyz")


def test_stocks_market_overview(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", "/api/stocks/market/overview")
