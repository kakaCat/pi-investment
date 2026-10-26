"""回归测试：/api/v2/stock/{symbol}/financials 的报表形状（2026-10-19）

背景：agent 工具 data_fetch_financial(dataType=statements) 曾对任意 A 股只拿到表头、
无数据。根因是路由只走 ``mgr.get_financial()``（9 个指标字段，报表数组被丢弃且全 None）。

本测试锁定修复后的契约：
- ``data`` 下**扁平**返回 income_statement / balance_sheet / cash_flow（agent-ts
  quant-v2-client.getFinancials() 的消费格式，字段名兼容中文）；
- ``statement_type=income`` 时另外两张表为空数组；
- ``periods`` 截断生效；
- 报表源失败才兜底指标链路，且显式标注 degraded；
- 两条链路都无有效数据时 success=false（不再假成功）。

全离线：mock 掉 DataProviderManager 与 stocks 表仓储，不依赖网络/数据库。
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes import financials_async
from qs_market_data.adapters.outbound.datasources.models import MarketData

SYMBOL = "688981"
SYMBOL_WITH_SUFFIX = "688981.SH"

# 新浪报表行（最新在前，行内是中文字段名）
INCOME_ROWS = [
    {"报告日": "20260630", "营业总收入": 102.0, "营业收入": 100.0, "净利润": 21.0},
    {"报告日": "20260331", "营业总收入": 88.0, "营业收入": 86.0, "净利润": 18.0},
    {"报告日": "20251231", "营业总收入": 400.0, "营业收入": 395.0, "净利润": 80.0},
    {"报告日": "20250930", "营业总收入": 300.0, "营业收入": 295.0, "净利润": 60.0},
]
BALANCE_ROWS = [
    {"报告日": "20260630", "资产总计": 5000.0, "负债合计": 2000.0},
    {"报告日": "20260331", "资产总计": 4900.0, "负债合计": 1950.0},
    {"报告日": "20251231", "资产总计": 4800.0, "负债合计": 1900.0},
    {"报告日": "20250930", "资产总计": 4700.0, "负债合计": 1850.0},
]
CASH_ROWS = [
    {"报告日": "20260630", "经营活动产生的现金流量净额": 30.0},
    {"报告日": "20260331", "经营活动产生的现金流量净额": 26.0},
    {"报告日": "20251231", "经营活动产生的现金流量净额": 110.0},
    {"报告日": "20250930", "经营活动产生的现金流量净额": 82.0},
]

ALL_NONE_INDICATORS = {
    "symbol": SYMBOL,
    "roe": None,
    "gross_margin": None,
    "net_profit_margin": None,
    "debt_ratio": None,
    "revenue_growth": None,
    "ocf_to_profit": None,
    "current_ratio": None,
    "roa": None,
    "operating_margin": None,
}


def _statements_ok_result():
    """_try_providers 成功路径的真实形状：data 是 MarketData。"""
    return {
        "success": True,
        "data": MarketData(
            data_type="sina_statements",
            data={
                "income": INCOME_ROWS,
                "balance": BALANCE_ROWS,
                "cashflow": CASH_ROWS,
            },
            source="akshare-financial",
            timestamp="2026-10-19T23:50:00",
        ),
        "source": "akshare-financial",
        "attempted_sources": ["akshare-financial"],
        "empty_sources": [],
        "provider_errors": {},
        "empty": False,
    }


@pytest.fixture
def manager():
    mgr = MagicMock()
    mgr.get_sina_financial_statements.return_value = _statements_ok_result()
    # 指标链路故意给全 None：报表命中时不应走它，也不能因此变成假成功
    mgr.get_financial.return_value = {
        "success": True,
        "data": dict(ALL_NONE_INDICATORS),
        "source": "sina",
    }
    return mgr


@pytest.fixture
def stock_repo():
    repo = MagicMock()
    repo.get_by_symbol.return_value = None
    return repo


@pytest.fixture
def client(manager, stock_repo):
    with patch.object(
        financials_async, "get_data_provider_manager", return_value=manager
    ), patch.object(financials_async, "get_stock_repo", return_value=stock_repo):
        app = FastAPI()
        app.include_router(financials_async.router)
        yield TestClient(app)


class TestStatementsShape:
    def test_all_statements_are_flat_and_contain_chinese_fields(self, client):
        resp = client.get(
            f"/api/v2/stock/{SYMBOL}/financials",
            params={"statement_type": "all", "periods": "4"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

        data = body["data"]
        assert data["symbol"] == SYMBOL

        # 三大报表都非空
        assert len(data["income_statement"]) == 4
        assert len(data["balance_sheet"]) == 4
        assert len(data["cash_flow"]) == 4

        # 行内保留了中文字段名（agent-ts 依赖中文/英文双兼容取值）
        first_income = data["income_statement"][0]
        assert "营业总收入" in first_income
        assert first_income["营业总收入"] == 102.0
        assert "资产总计" in data["balance_sheet"][0]
        assert "经营活动产生的现金流量净额" in data["cash_flow"][0]

        # 扁平契约：不能再套一层 data / 不能用 camelCase
        assert "data" not in data
        assert "incomeStatement" not in data
        assert data["source"] == "akshare-financial"
        assert data["degraded"] is False
        assert body["source"] == "akshare-financial"

    def test_statement_type_income_empties_other_statements(self, client):
        resp = client.get(
            f"/api/v2/stock/{SYMBOL}/financials",
            params={"statement_type": "income"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert len(data["income_statement"]) == 4
        assert "营业总收入" in data["income_statement"][0]
        assert data["balance_sheet"] == []
        assert data["cash_flow"] == []

    def test_statement_type_cash_flow_maps_provider_key(self, client):
        resp = client.get(
            f"/api/v2/stock/{SYMBOL}/financials",
            params={"statement_type": "cash_flow"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert len(data["cash_flow"]) == 4
        assert data["cash_flow"][0]["报告日"] == "20260630"
        assert data["income_statement"] == []
        assert data["balance_sheet"] == []

    def test_periods_truncates_rows_latest_first(self, client):
        resp = client.get(
            f"/api/v2/stock/{SYMBOL}/financials",
            params={"statement_type": "all", "periods": "2"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert [r["报告日"] for r in data["income_statement"]] == [
            "20260630",
            "20260331",
        ]
        assert len(data["balance_sheet"]) == 2
        assert len(data["cash_flow"]) == 2
        assert data["periods"] == 2

    def test_requested_statement_empty_but_others_present_stays_honest(
        self, client, manager
    ):
        """报表源有数据、但请求的单表为空：返回空数组 + empty=True，不降级指标。"""
        manager.get_sina_financial_statements.return_value = {
            "success": True,
            "data": MarketData(
                data_type="sina_statements",
                data={"income": INCOME_ROWS, "balance": [], "cashflow": []},
                source="akshare-financial",
            ),
            "source": "akshare-financial",
            "attempted_sources": ["akshare-financial"],
            "empty_sources": [],
            "provider_errors": {},
            "empty": False,
        }

        resp = client.get(
            f"/api/v2/stock/{SYMBOL}/financials",
            params={"statement_type": "balance"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]

        assert data["balance_sheet"] == []
        assert data["income_statement"] == []
        assert data["cash_flow"] == []
        assert data["degraded"] is False
        assert data["empty"] is True
        assert "balance" in data["empty_reason"]
        # 报表源已有数据，不应调用指标兜底链路
        manager.get_financial.assert_not_called()

    def test_symbol_with_suffix_is_cleaned_for_statements(self, client, manager):
        resp = client.get(
            f"/api/v2/stock/{SYMBOL_WITH_SUFFIX}/financials",
            params={"statement_type": "all"},
        )
        assert resp.status_code == 200
        manager.get_sina_financial_statements.assert_called_once_with(SYMBOL)

    def test_pe_pb_supplemented_from_stocks_table(self, client, stock_repo):
        stock_repo.get_by_symbol.return_value = SimpleNamespace(pe=45.6, pb=3.2)

        resp = client.get(
            f"/api/v2/stock/{SYMBOL}/financials",
            params={"statement_type": "all"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert data["pe"] == 45.6
        assert data["pb"] == 3.2
        assert data["pe_ttm"] == 45.6
        stock_repo.get_by_symbol.assert_called_once_with(SYMBOL)


class TestFallbackAndFailureHonesty:
    def test_statement_failure_falls_back_to_indicators_and_marks_degraded(
        self, client, manager
    ):
        manager.get_sina_financial_statements.return_value = {
            "success": False,
            "data": None,
            "error": "sina statements all providers failed",
            "attempted_sources": ["akshare-financial"],
            "empty_sources": [],
            "provider_errors": {"akshare-financial": "timeout"},
        }
        manager.get_financial.return_value = {
            "success": True,
            "data": {
                **ALL_NONE_INDICATORS,
                "roe": 12.5,
                "gross_margin": 33.2,
            },
            "source": "sina",
        }

        resp = client.get(
            f"/api/v2/stock/{SYMBOL}/financials",
            params={"statement_type": "all"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

        data = body["data"]
        assert data["degraded"] is True
        assert data["fallback"] == "indicators"
        assert "sina statements all providers failed" in data["degraded_reason"]
        assert data["income_statement"] == []
        assert data["balance_sheet"] == []
        assert data["cash_flow"] == []
        assert data["roe"] == 12.5
        # 指标兜底路径只调用一次
        manager.get_financial.assert_called_once_with(SYMBOL, report_type="latest")

    def test_all_null_sources_do_not_report_fake_success(self, client, manager):
        manager.get_sina_financial_statements.return_value = {
            "success": False,
            "data": None,
            "error": "sina statements all providers failed",
            "attempted_sources": ["akshare-financial"],
            "empty_sources": [],
            "provider_errors": {},
        }
        manager.get_financial.return_value = {
            "success": True,
            "data": dict(ALL_NONE_INDICATORS),
            "source": "sina",
        }

        resp = client.get(
            f"/api/v2/stock/{SYMBOL}/financials",
            params={"statement_type": "all"},
        )
        assert resp.status_code == 502
        body = resp.json()
        assert body["success"] is False
        assert "error" in body and body["error"]
        assert body["attempted_sources"] == ["akshare-financial"]
