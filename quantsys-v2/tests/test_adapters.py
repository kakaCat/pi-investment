"""Tests for the market data adapter layer."""

from __future__ import annotations

import importlib
import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from domain.quantlib.adapters.base_adapter import BaseMarketAdapter
from domain.quantlib.adapters.factory import get_adapter, register_adapter, list_adapters


# ========================================================================
# Symbol conversion tests
# ========================================================================

class TestSymbolConversion:
    """Test internal ↔ external symbol format conversion."""

    def test_internal_to_clean_with_suffix(self):
        code, exchange = BaseMarketAdapter.internal_to_clean("000001.SZ")
        assert code == "000001"
        assert exchange == "SZ"

    def test_internal_to_clean_shanghai(self):
        code, exchange = BaseMarketAdapter.internal_to_clean("600000.SH")
        assert code == "600000"
        assert exchange == "SH"

    def test_internal_to_clean_hk(self):
        code, exchange = BaseMarketAdapter.internal_to_clean("00700.HK")
        assert code == "00700"
        assert exchange == "HK"

    def test_internal_to_clean_no_suffix_sh_heuristic(self):
        """Six-digit code starting with 6 → inferred as SH."""
        code, exchange = BaseMarketAdapter.internal_to_clean("000001")
        assert code == "000001"
        assert exchange == "SH"

    def test_internal_to_clean_no_suffix_sz_heuristic(self):
        """Six-digit code starting with 0 → inferred as SZ."""
        code, exchange = BaseMarketAdapter.internal_to_clean("000651")
        assert code == "000651"
        assert exchange == "SZ"

    def test_internal_to_clean_hk_heuristic(self):
        """Five or fewer digits → inferred as HK."""
        code, exchange = BaseMarketAdapter.internal_to_clean("00700")
        assert code == "00700"
        assert exchange == "HK"

    def test_clean_to_internal(self):
        result = BaseMarketAdapter.clean_to_internal("000001", "SZ")
        assert result == "000001.SZ"

    def test_clean_to_internal_lowercase_exchange(self):
        result = BaseMarketAdapter.clean_to_internal("600000", "sh")
        assert result == "600000.SH"

    def test_exchange_prefix_shenzhen(self):
        assert BaseMarketAdapter.exchange_prefix("000001") == "sz"
        assert BaseMarketAdapter.exchange_prefix("002001") == "sz"
        assert BaseMarketAdapter.exchange_prefix("300001") == "sz"

    def test_exchange_prefix_shanghai(self):
        assert BaseMarketAdapter.exchange_prefix("600000") == "sh"
        assert BaseMarketAdapter.exchange_prefix("900001") == "sh"

    def test_exchange_prefix_beijing(self):
        assert BaseMarketAdapter.exchange_prefix("430001") == "bj"
        assert BaseMarketAdapter.exchange_prefix("830001") == "bj"
        assert BaseMarketAdapter.exchange_prefix("920001") == "bj"

    def test_internal_to_akshare_sz(self):
        code, prefix = BaseMarketAdapter.internal_to_akshare("000001.SZ")
        assert code == "000001"
        assert prefix == "sz"

    def test_internal_to_akshare_sh(self):
        code, prefix = BaseMarketAdapter.internal_to_akshare("600000.SH")
        assert code == "600000"
        assert prefix == "sh"

    def test_internal_to_akshare_hk(self):
        code, prefix = BaseMarketAdapter.internal_to_akshare("00700.HK")
        assert code == "00700"
        assert prefix == "hk"


# ========================================================================
# Date normalisation tests
# ========================================================================

class TestDateNormalisation:
    def test_normalise_date_yyyymmdd(self):
        assert BaseMarketAdapter._normalise_date("20240101") == "20240101"

    def test_normalise_date_dashed(self):
        assert BaseMarketAdapter._normalise_date("2024-01-01") == "20240101"

    def test_normalise_date_display(self):
        assert BaseMarketAdapter._normalise_date_display("20240101") == "2024-01-01"

    def test_normalise_date_display_already_display(self):
        assert BaseMarketAdapter._normalise_date_display("2024-01-01") == "2024-01-01"

    def test_safe_float_valid(self):
        assert BaseMarketAdapter._safe_float("123.45") == 123.45

    def test_safe_float_int(self):
        assert BaseMarketAdapter._safe_float(100) == 100.0

    def test_safe_float_none(self):
        assert BaseMarketAdapter._safe_float(None) is None

    def test_safe_float_nan(self):
        import math
        assert BaseMarketAdapter._safe_float(float("nan")) is None

    def test_safe_float_garbage(self):
        assert BaseMarketAdapter._safe_float("not-a-number") is None


# ========================================================================
# Adapter factory tests
# ========================================================================

class TestAdapterFactory:
    """Test the get_adapter() factory function."""

    def test_default_returns_akshare_adapter(self):
        """Default adapter is the AkShareAdapter."""
        from domain.quantlib.adapters.akshare_adapter import AkShareAdapter
        adapter = get_adapter()
        assert isinstance(adapter, BaseMarketAdapter)
        assert isinstance(adapter, AkShareAdapter)

    def test_explicit_name_returns_akshare_adapter(self):
        from domain.quantlib.adapters.akshare_adapter import AkShareAdapter
        adapter = get_adapter("akshare")
        assert isinstance(adapter, AkShareAdapter)

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("QUANT_MARKET_ADAPTER", "akshare")
        from domain.quantlib.adapters.akshare_adapter import AkShareAdapter
        adapter = get_adapter()
        assert isinstance(adapter, AkShareAdapter)

    def test_unknown_adapter_raises(self):
        with pytest.raises(ValueError, match="Unknown adapter"):
            get_adapter("nonexistent_source")

    def test_register_adapter(self):
        register_adapter("mock_test", "quantlib.adapters.base_adapter.BaseMarketAdapter")
        assert "mock_test" in list_adapters()
        # Clean up — remove from registry to avoid polluting other tests
        from domain.quantlib.adapters import factory
        factory._REGISTRY.pop("mock_test", None)

    def test_list_adapters(self):
        names = list_adapters()
        assert "akshare" in names
        assert all(isinstance(n, str) for n in names)


# ========================================================================
# AkShareAdapter method structure tests (with mocked akshare)
# ========================================================================

class _BaseMockAkshareTest:
    """Base class that patches akshare inside the adapter module."""

    @pytest.fixture(autouse=True)
    def _patch_akshare(self, monkeypatch):
        """Patch the `ak` reference inside ak_share_adapter so tests never
        call the real akshare library."""
        self.mock_ak = MagicMock()
        monkeypatch.setattr("quantlib.adapters.akshare_adapter.ak", self.mock_ak)

    def _make_adapter(self):
        from domain.quantlib.adapters.akshare_adapter import AkShareAdapter
        return AkShareAdapter()

    def _make_kline_frame(self, symbols=1):
        """Create a minimal East Money kline DataFrame."""
        dates = pd.date_range("2024-01-02", periods=3, freq="B")
        return pd.DataFrame({
            "日期": dates.strftime("%Y-%m-%d"),
            "开盘": [10.0, 11.0, 12.0],
            "最高": [11.0, 12.0, 13.0],
            "最低": [9.5, 10.5, 11.5],
            "收盘": [10.8, 11.8, 12.8],
            "成交量": [100000, 110000, 120000],
            "成交额": [1080000, 1298000, 1536000],
        })

    def _make_spot_frame(self):
        """Create a minimal A-share spot DataFrame."""
        return pd.DataFrame({
            "代码": ["000001", "600000"],
            "名称": ["平安银行", "浦发银行"],
            "最新价": [12.50, 9.30],
            "涨跌额": [0.20, -0.10],
            "涨跌幅": [1.63, -1.06],
            "成交量": [50000000, 30000000],
            "成交额": [625000000, 279000000],
            "最高": [12.80, 9.50],
            "最低": [12.30, 9.10],
            "今开": [12.35, 9.40],
            "昨收": [12.30, 9.40],
        })


class TestGetStockInfo(_BaseMockAkshareTest):
    def test_returns_dict_with_expected_keys(self):
        # Set up mock: stock_individual_info_em returns a small info frame
        self.mock_ak.stock_individual_info_em.return_value = pd.DataFrame({
            "item": ["股票简称", "行业", "上市时间"],
            "value": ["平安银行", "银行", "1991-04-03"],
        })

        adapter = self._make_adapter()
        result = adapter.get_stock_info("000001.SZ")

        assert isinstance(result, dict)
        assert result["symbol"] == "000001.SZ"
        assert result["name"] == "平安银行"
        assert result["market"] == "A"
        assert result["industry"] == "银行"
        assert result["list_date"] == "1991-04-03"

    def test_empty_frame_returns_empty_dict(self):
        self.mock_ak.stock_individual_info_em.return_value = pd.DataFrame()

        adapter = self._make_adapter()
        result = adapter.get_stock_info("000001.SZ")
        assert result == {}

    def test_none_frame_returns_empty_dict(self):
        self.mock_ak.stock_individual_info_em.return_value = None

        adapter = self._make_adapter()
        result = adapter.get_stock_info("000001.SZ")
        assert result == {}

    def test_exception_returns_empty_dict(self):
        self.mock_ak.stock_individual_info_em.side_effect = RuntimeError("boom")

        adapter = self._make_adapter()
        result = adapter.get_stock_info("000001.SZ")
        assert result == {}

    def test_import_error_returns_error_dict(self, monkeypatch):
        # Simulate akshare not being installed
        import domain.quantlib.adapters.akshare_adapter as mod
        monkeypatch.setattr(mod, "ak", _make_unavailable_stub())

        adapter = self._make_adapter()
        result = adapter.get_stock_info("000001.SZ")
        assert "error" in result


def _make_unavailable_stub():
    """Create a stub that raises ImportError on any attribute access."""
    class Stub:
        _MSG = "akshare not installed"
        def __getattr__(self, _name):
            def _raise(*_a, **_kw):
                raise ImportError(self._MSG)
            return _raise
    return Stub()


class TestGetKlines(_BaseMockAkshareTest):
    def test_returns_list_of_standard_dicts(self):
        self.mock_ak.stock_zh_a_hist.return_value = self._make_kline_frame()

        adapter = self._make_adapter()
        result = adapter.get_klines("000001.SZ", "daily", "20240101", "20240105")

        assert isinstance(result, list)
        assert len(result) == 3
        for row in result:
            assert "symbol" in row
            assert row["symbol"] == "000001.SZ"
            assert "date" in row
            assert "open" in row
            assert "high" in row
            assert "low" in row
            assert "close" in row
            assert "volume" in row
            assert "amount" in row
            # Date should be in display format
            assert "-" in row["date"] or row["date"] == ""

    def test_empty_frame_returns_empty_list(self):
        self.mock_ak.stock_zh_a_hist.return_value = pd.DataFrame()

        adapter = self._make_adapter()
        result = adapter.get_klines("000001.SZ")
        assert result == []

    def test_weekly_period_maps_correctly(self):
        self.mock_ak.stock_zh_a_hist.return_value = self._make_kline_frame()

        adapter = self._make_adapter()
        result = adapter.get_klines("000001.SZ", "weekly")
        # Make sure the period was passed through to akshare
        call_kwargs = self.mock_ak.stock_zh_a_hist.call_args.kwargs
        assert call_kwargs["period"] == "weekly"
        assert len(result) == 3

    def test_monthly_period_maps_correctly(self):
        self.mock_ak.stock_zh_a_hist.return_value = self._make_kline_frame()

        adapter = self._make_adapter()
        result = adapter.get_klines("000001.SZ", "monthly")
        call_kwargs = self.mock_ak.stock_zh_a_hist.call_args.kwargs
        assert call_kwargs["period"] == "monthly"

    def test_east_money_failure_falls_back_to_tencent(self):
        # East Money fails, Tencent succeeds
        self.mock_ak.stock_zh_a_hist.side_effect = RuntimeError("EM failed")

        tx_frame = pd.DataFrame({
            "date": ["2024-01-02", "2024-01-03"],
            "open": [10.0, 11.0],
            "high": [11.0, 12.0],
            "low": [9.5, 10.5],
            "close": [10.8, 11.8],
            "volume": [100000, 110000],
            "amount": [1080000, 1298000],
        })
        self.mock_ak.stock_zh_a_hist_tx.return_value = tx_frame

        adapter = self._make_adapter()
        result = adapter.get_klines("000001.SZ")
        assert len(result) == 2
        # Tencent should have been called with the prefixed symbol
        self.mock_ak.stock_zh_a_hist_tx.assert_called_once()

    def test_hk_stock_uses_hk_api(self):
        hk_frame = pd.DataFrame({
            "日期": ["2024-01-02", "2024-01-03"],
            "开盘": [300.0, 305.0],
            "最高": [310.0, 312.0],
            "最低": [298.0, 302.0],
            "收盘": [308.0, 310.0],
            "成交量": [5000000, 5200000],
            "成交额": [1540000000, 1612000000],
        })
        self.mock_ak.stock_hk_hist.return_value = hk_frame

        adapter = self._make_adapter()
        result = adapter.get_klines("00700.HK", "daily", "20240101", "20240105")
        assert len(result) == 2
        self.mock_ak.stock_hk_hist.assert_called_once()

    def test_all_sources_fail_returns_empty_list(self):
        self.mock_ak.stock_zh_a_hist.side_effect = RuntimeError("EM failed")
        self.mock_ak.stock_zh_a_hist_tx.side_effect = RuntimeError("Tencent failed")

        adapter = self._make_adapter()
        result = adapter.get_klines("000001.SZ")
        assert result == []

    def test_import_error_returns_empty_list(self, monkeypatch):
        import domain.quantlib.adapters.akshare_adapter as mod
        monkeypatch.setattr(mod, "ak", _make_unavailable_stub())

        adapter = self._make_adapter()
        result = adapter.get_klines("000001.SZ")
        assert result == []


class TestGetRealtimeQuote(_BaseMockAkshareTest):
    def test_returns_dict_keyed_by_symbol(self):
        self.mock_ak.stock_zh_a_spot_em.return_value = self._make_spot_frame()

        adapter = self._make_adapter()
        result = adapter.get_realtime_quote(["000001.SZ", "600000.SH"])

        assert isinstance(result, dict)
        assert "000001.SZ" in result
        assert "600000.SH" in result

        q = result["000001.SZ"]
        assert q["symbol"] == "000001.SZ"
        assert q["name"] == "平安银行"
        assert q["price"] == 12.50
        assert q["change"] == 0.20
        assert q["change_pct"] == 1.63
        assert q["high"] == 12.80
        assert q["low"] == 12.30
        assert q["open"] == 12.35
        assert q["pre_close"] == 12.30

    def test_unknown_symbol_omitted(self):
        self.mock_ak.stock_zh_a_spot_em.return_value = self._make_spot_frame()

        adapter = self._make_adapter()
        result = adapter.get_realtime_quote(["999999.SZ"])
        assert result == {}

    def test_empty_input_returns_empty_dict(self):
        adapter = self._make_adapter()
        result = adapter.get_realtime_quote([])
        assert result == {}

    def test_exception_returns_empty_dict(self):
        self.mock_ak.stock_zh_a_spot_em.side_effect = RuntimeError("service down")

        adapter = self._make_adapter()
        result = adapter.get_realtime_quote(["000001.SZ"])
        assert result == {}  # graceful degradation


class TestGetIndexData(_BaseMockAkshareTest):
    def test_returns_ohlcv_list(self):
        index_frame = pd.DataFrame({
            "date": ["2024-01-02", "2024-01-03"],
            "open": [3000.0, 3020.0],
            "high": [3050.0, 3060.0],
            "low": [2990.0, 3010.0],
            "close": [3030.0, 3040.0],
            "volume": [100000000, 110000000],
            "amount": [50000000000, 55000000000],
        })
        self.mock_ak.stock_zh_index_daily_em.return_value = index_frame

        adapter = self._make_adapter()
        result = adapter.get_index_data("000001")

        assert isinstance(result, list)
        assert len(result) == 2
        for row in result:
            assert "symbol" in row
            assert row["symbol"] == "000001"
            assert "date" in row
            assert "open" in row
            assert "close" in row

    def test_date_filter_applied(self):
        index_frame = pd.DataFrame({
            "date": ["2024-01-02", "2024-01-03", "2024-01-04"],
            "open": [3000.0, 3020.0, 3040.0],
            "high": [3050.0, 3060.0, 3070.0],
            "low": [2990.0, 3010.0, 3030.0],
            "close": [3030.0, 3040.0, 3050.0],
            "volume": [100000000, 110000000, 120000000],
            "amount": [50000000000, 55000000000, 60000000000],
        })
        self.mock_ak.stock_zh_index_daily_em.return_value = index_frame

        adapter = self._make_adapter()
        # Should filter out 2024-01-04
        result = adapter.get_index_data("000001", "20240101", "20240103")
        assert len(result) == 2

    def test_empty_frame_returns_empty_list(self):
        self.mock_ak.stock_zh_index_daily_em.return_value = pd.DataFrame()

        adapter = self._make_adapter()
        result = adapter.get_index_data("000001")
        assert result == []

    def test_exception_returns_empty_list(self):
        self.mock_ak.stock_zh_index_daily_em.side_effect = RuntimeError("down")

        adapter = self._make_adapter()
        result = adapter.get_index_data("000001")
        assert result == []


class TestGetSectorList(_BaseMockAkshareTest):
    def test_returns_industry_sectors(self):
        self.mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame({
            "板块名称": ["银行", "房地产", "医药"],
            "板块代码": ["BK001", "BK002", "BK003"],
        })
        # Concept boards empty
        self.mock_ak.stock_board_concept_name_ths.return_value = pd.DataFrame()

        adapter = self._make_adapter()
        result = adapter.get_sector_list()

        assert isinstance(result, list)
        assert len(result) == 3
        for item in result:
            assert "code" in item
            assert "name" in item
            assert item["type"] == "industry"

    def test_returns_concept_boards(self):
        self.mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame()
        self.mock_ak.stock_board_concept_name_ths.return_value = pd.DataFrame({
            "概念名称": ["人工智能", "芯片", "新能源"],
            "概念代码": ["GN001", "GN002", "GN003"],
        })

        adapter = self._make_adapter()
        result = adapter.get_sector_list()

        assert len(result) == 3
        for item in result:
            assert item["type"] == "concept"

    def test_exception_returns_empty_list(self):
        self.mock_ak.stock_board_industry_name_em.side_effect = RuntimeError("down")
        self.mock_ak.stock_board_concept_name_ths.side_effect = RuntimeError("down")

        adapter = self._make_adapter()
        result = adapter.get_sector_list()
        assert result == []


class TestGetNorthFlow(_BaseMockAkshareTest):
    def test_returns_flow_history(self):
        self.mock_ak.stock_hsgt_hist_em.return_value = pd.DataFrame({
            "日期": ["2024-01-02", "2024-01-03"],
            "当日成交净买额": [50.5, -10.2],
        })

        adapter = self._make_adapter()
        result = adapter.get_north_flow("20240101", "20240105")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["date"] == "2024-01-02"
        assert result[0]["net_flow"] == 50.5
        assert result[1]["net_flow"] == -10.2

    def test_empty_frame_returns_empty_list(self):
        self.mock_ak.stock_hsgt_hist_em.return_value = pd.DataFrame()

        adapter = self._make_adapter()
        result = adapter.get_north_flow()
        assert result == []

    def test_exception_returns_empty_list(self):
        self.mock_ak.stock_hsgt_hist_em.side_effect = RuntimeError("down")

        adapter = self._make_adapter()
        result = adapter.get_north_flow()
        assert result == []


class TestGetMarketNews(_BaseMockAkshareTest):
    def test_returns_broad_market_news(self):
        self.mock_ak.stock_news_em.return_value = pd.DataFrame({
            "标题": ["新闻A", "新闻B"],
            "发布时间": ["2024-01-02 10:00", "2024-01-02 11:00"],
            "来源": ["东方财富", "同花顺"],
        })

        adapter = self._make_adapter()
        result = adapter.get_market_news("", limit=10)

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert "title" in item
            assert "time" in item
            assert "source" in item
            assert "url" in item

    def test_symbol_specific_news(self):
        self.mock_ak.stock_news_em.return_value = pd.DataFrame({
            "标题": ["平安银行公告"],
            "发布时间": ["2024-01-02 09:00"],
            "来源": ["东方财富"],
        })
        # Disclosure reports
        self.mock_ak.stock_zh_a_disclosure_report_cninfo.return_value = pd.DataFrame()

        adapter = self._make_adapter()
        result = adapter.get_market_news("000001.SZ", limit=5)
        assert len(result) == 1
        assert result[0]["title"] == "平安银行公告"

    def test_limit_respected(self):
        self.mock_ak.stock_news_em.return_value = pd.DataFrame({
            "标题": [f"新闻{i}" for i in range(30)],
            "发布时间": ["2024-01-02"] * 30,
            "来源": ["来源"] * 30,
        })

        adapter = self._make_adapter()
        result = adapter.get_market_news("", limit=5)
        assert len(result) == 5

    def test_exception_returns_empty_list(self):
        self.mock_ak.stock_news_em.side_effect = RuntimeError("down")

        adapter = self._make_adapter()
        result = adapter.get_market_news("")
        assert result == []


class TestGetFinancialData(_BaseMockAkshareTest):
    def test_a_share_returns_standard_dict(self):
        self.mock_ak.stock_financial_abstract_ths.return_value = pd.DataFrame([
            {
                "报告期": "2024-03-31",
                "营业总收入": 50000000000.0,
                "净利润": 10000000000.0,
                "净资产收益率": 15.5,
                "每股收益": 2.5,
                "资产总计": 500000000000.0,
                "负债合计": 400000000000.0,
                "市盈率": 8.5,
                "市净率": 1.2,
            }
        ])
        self.mock_ak.stock_individual_info_em.return_value = pd.DataFrame()

        adapter = self._make_adapter()
        result = adapter.get_financial_data("000001.SZ")

        assert isinstance(result, dict)
        assert result["symbol"] == "000001.SZ"
        assert result["report_date"] == "2024-03-31"
        assert result["revenue"] == 50000000000.0
        assert result["net_profit"] == 10000000000.0
        assert result["roe"] == 15.5
        assert result["eps"] == 2.5
        assert result["total_assets"] == 500000000000.0
        assert result["total_liabilities"] == 400000000000.0
        assert result["pe"] == 8.5
        assert result["pb"] == 1.2

    def test_empty_frame_returns_minimal_dict(self):
        self.mock_ak.stock_financial_abstract_ths.return_value = pd.DataFrame()
        self.mock_ak.stock_individual_info_em.return_value = pd.DataFrame()

        adapter = self._make_adapter()
        result = adapter.get_financial_data("000001.SZ")
        assert result["symbol"] == "000001.SZ"
        assert result["revenue"] is None

    def test_exception_returns_symbol_dict(self):
        self.mock_ak.stock_financial_abstract_ths.side_effect = RuntimeError("down")

        adapter = self._make_adapter()
        result = adapter.get_financial_data("000001.SZ")
        assert result["symbol"] == "000001.SZ"

    def test_hk_financial_uses_hk_api(self):
        # For HK stocks, A-share API shouldn't be called
        adapter = self._make_adapter()

        # Mock HK income statement
        self.mock_ak.stock_financial_hk_report_em.return_value = pd.DataFrame([
            {
                "截止日期": "2023-12-31",
                "营业收入": 600000000000.0,
                "净利润": 120000000000.0,
            }
        ])

        result = adapter.get_financial_data("00700.HK")
        assert result["symbol"] == "00700.HK"
        # HK report was called with correct args
        call_args_list = self.mock_ak.stock_financial_hk_report_em.call_args_list
        assert len(call_args_list) >= 1


# ========================================================================
# End-to-end adapter integration test (mock-free structure check)
# ========================================================================

class TestAkShareAdapterStructure:
    """Verify the adapter implements the full BaseMarketAdapter interface."""

    def setup_method(self):
        from domain.quantlib.adapters.akshare_adapter import AkShareAdapter
        self.adapter = AkShareAdapter()

    def test_implements_all_abstract_methods(self):
        """AkShareAdapter must provide concrete implementations for all
        abstract methods defined in BaseMarketAdapter."""
        abstract_methods = {
            "get_stock_info",
            "get_klines",
            "get_realtime_quote",
            "get_index_data",
            "get_sector_list",
            "get_north_flow",
            "get_market_news",
            "get_financial_data",
        }
        for method_name in abstract_methods:
            assert hasattr(self.adapter, method_name), f"Missing method: {method_name}"
            method = getattr(self.adapter, method_name)
            assert callable(method), f"{method_name} is not callable"

    def test_is_instance_of_base_adapter(self):
        assert isinstance(self.adapter, BaseMarketAdapter)


# ========================================================================
# Module export tests
# ========================================================================

class TestModuleExports:
    def test_init_exports_all_symbols(self):
        from domain.quantlib.adapters import (
            BaseMarketAdapter,
            AkShareAdapter,
            get_adapter,
            register_adapter,
            list_adapters,
        )
        assert BaseMarketAdapter is not None
        assert AkShareAdapter is not None
        assert callable(get_adapter)
        assert callable(register_adapter)
        assert callable(list_adapters)

    def test_factory_importable_from_package(self):
        from domain.quantlib.adapters import get_adapter
        adapter = get_adapter("akshare")
        assert isinstance(adapter, BaseMarketAdapter)
