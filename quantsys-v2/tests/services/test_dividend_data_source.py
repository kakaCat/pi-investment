import pytest
import pandas as pd
from unittest.mock import patch, Mock
from application.services.dividend_data_source import EastMoneyDividendSource


def _eastmoney_response(rows):
    """Build a mock EastMoney RPT_SHAREBONUS_DET JSON response."""
    return {
        "code": 0,
        "result": {"data": rows},
    }


def _icbc_row(divident_ratio, report_date="2024-07-16 00:00:00", pretax=3.064):
    """EastMoney raw row. NOTE: DIVIDENT_RATIO is a decimal fraction (0.0494 = 4.94%)."""
    return {
        "SECURITY_CODE": "601398",
        "SECURITY_NAME_ABBR": "工商银行",
        "REPORT_DATE": report_date,
        "IMPL_PLAN_PROFILE": "10派3.064元",
        "BONUS_RATIO": 0,
        "IT_RATIO": 0,
        "PRETAX_BONUS_RMB": pretax,
        "DIVIDENT_RATIO": divident_ratio,
        "EX_DIVIDEND_DATE": "2024-07-16 00:00:00",
        "EQUITY_RECORD_DATE": "2024-07-15 00:00:00",
        "PUBLISH_DATE": "2024-07-16 00:00:00",
        "NOTICE_DATE": "2024-03-28 00:00:00",
        "PLAN_NOTICE_DATE": "2024-03-28 00:00:00",
    }


class TestEastMoneyDividendSource:
    """The live data source. Contract: 股息率 is returned in PERCENT (akshare-compatible)."""

    @patch("application.services.dividend_data_source.requests.get")
    def test_normalizes_yield_fraction_to_percent(self, mock_get):
        """Regression: EastMoney DIVIDENT_RATIO is a fraction (0.0494); downstream
        filters/formatters expect percent (4.94). Must be converted at the source."""
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = _eastmoney_response([_icbc_row(0.049419)])
        mock_get.return_value = mock_resp

        source = EastMoneyDividendSource()
        df = source.fetch_dividends("601398.SH")

        assert not df.empty
        assert df["股息率"].iloc[0] == pytest.approx(4.9419, rel=1e-3)

    @patch("application.services.dividend_data_source.requests.get")
    def test_strips_suffix_and_maps_columns(self, mock_get):
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = _eastmoney_response([_icbc_row(0.05)])
        mock_get.return_value = mock_resp

        source = EastMoneyDividendSource()
        df = source.fetch_dividends("601398.SH")

        for col in ["股票代码", "股票简称", "分红年度", "每股派息", "股息率", "除权除息日"]:
            assert col in df.columns
        # filter uses bare 6-digit code
        assert "601398" in mock_get.call_args.kwargs["params"]["filter"]

    @patch("application.services.dividend_data_source.requests.get")
    def test_empty_result_returns_empty_dataframe(self, mock_get):
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {"code": 0, "result": {"data": []}}
        mock_get.return_value = mock_resp

        source = EastMoneyDividendSource()
        df = source.fetch_dividends("601398.SH")

        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("application.services.dividend_data_source.requests.get")
    def test_normalizes_dates_to_date_only(self, mock_get):
        """EastMoney dates arrive as 'YYYY-MM-DD 00:00:00'. They must be normalized
        to 'YYYY-MM-DD' so downstream string range comparisons include events that
        fall exactly on the range end date."""
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = _eastmoney_response([_icbc_row(0.05)])
        mock_get.return_value = mock_resp

        source = EastMoneyDividendSource()
        df = source.fetch_dividends("601398.SH")

        assert df["除权除息日"].iloc[0] == "2024-07-16"
        assert df["股权登记日"].iloc[0] == "2024-07-15"
