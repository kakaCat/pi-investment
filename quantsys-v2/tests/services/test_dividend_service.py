import pytest
import pandas as pd
from unittest.mock import Mock
from application.services.dividend_service import DividendService
from application.services.dividend_data_source import EastMoneyDividendSource, DividendDataSource


class TestDividendServiceInit:
    def test_service_initializes_with_eastmoney_source(self):
        """Test that service initializes with EastMoneyDividendSource by default"""
        service = DividendService()

        assert service is not None
        assert isinstance(service.data_source, EastMoneyDividendSource)


class MockDividendSource(DividendDataSource):
    """Mock data source for testing"""

    def __init__(self, data: pd.DataFrame = None):
        self.data = data if data is not None else pd.DataFrame()

    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        if symbol == "INVALID":
            return pd.DataFrame()
        return self.data


class TestGetStockDividends:
    def test_get_stock_dividends_success(self):
        """Test successful dividend query"""
        # Create mock data
        mock_data = pd.DataFrame([
            {
                "股票代码": "000001",
                "股票简称": "浦发银行",
                "分红年度": "2023",
                "每股派息": 21.0,
                "送股比例": 0.0,
                "转增比例": 0.0,
                "股息率": "1.5",
                "公告日期": "2024-03-28",
                "除权除息日": "2024-06-30",
                "股权登记日": "2024-06-29",
                "派息日": "2024-06-30"
            },
            {
                "股票代码": "000001",
                "股票简称": "浦发银行",
                "分红年度": "2022",
                "每股派息": 19.0,
                "送股比例": 0.0,
                "转增比例": 0.0,
                "股息率": "1.4",
                "公告日期": "2023-03-28",
                "除权除息日": "2023-06-30",
                "股权登记日": "2023-06-29",
                "派息日": "2023-06-30"
            }
        ])

        mock_source = MockDividendSource(mock_data)
        service = DividendService(data_source=mock_source)
        result = service.get_stock_dividends("000001.SH", years=5)

        assert result["success"] is True
        assert result["symbol"] == "000001.SH"
        assert "name" in result
        assert "dividends" in result
        assert "summary" in result
        assert isinstance(result["dividends"], list)
        assert len(result["dividends"]) == 2

    def test_get_stock_dividends_with_summary(self):
        """Test that summary is calculated correctly"""
        # Create mock data with 3 years
        mock_data = pd.DataFrame([
            {
                "股票代码": "000001",
                "股票简称": "浦发银行",
                "分红年度": "2023",
                "每股派息": 21.0,
                "送股比例": 0.0,
                "转增比例": 0.0,
                "股息率": "1.5",
                "公告日期": "2024-03-28",
                "除权除息日": "2024-06-30",
                "股权登记日": "2024-06-29",
                "派息日": "2024-06-30"
            },
            {
                "股票代码": "000001",
                "股票简称": "浦发银行",
                "分红年度": "2022",
                "每股派息": 19.0,
                "送股比例": 0.0,
                "转增比例": 0.0,
                "股息率": "1.4",
                "公告日期": "2023-03-28",
                "除权除息日": "2023-06-30",
                "股权登记日": "2023-06-29",
                "派息日": "2023-06-30"
            },
            {
                "股票代码": "000001",
                "股票简称": "浦发银行",
                "分红年度": "2021",
                "每股派息": 17.0,
                "送股比例": 0.0,
                "转增比例": 0.0,
                "股息率": "1.3",
                "公告日期": "2022-03-28",
                "除权除息日": "2022-06-30",
                "股权登记日": "2022-06-29",
                "派息日": "2022-06-30"
            }
        ])

        mock_source = MockDividendSource(mock_data)
        service = DividendService(data_source=mock_source)
        result = service.get_stock_dividends("000001.SH", years=10)

        summary = result["summary"]
        assert "consecutive_years" in summary
        assert "avg_yield" in summary
        assert "total_cash_dividend" in summary
        assert summary["consecutive_years"] == 3
        assert summary["avg_yield"] > 0
        assert summary["total_cash_dividend"] > 0

    def test_get_stock_dividends_invalid_symbol(self):
        """Test handling of invalid symbol"""
        mock_source = MockDividendSource(pd.DataFrame())
        service = DividendService(data_source=mock_source)
        result = service.get_stock_dividends("INVALID", years=5)

        assert result["success"] is False
        assert "error" in result


class TestScreenDividendStocks:
    def test_screen_dividend_stocks_success(self):
        """Test successful dividend screening"""
        service = DividendService()
        params = {
            "min_yield": 3.0,
            "min_years": 3,
            "limit": 10
        }
        result = service.screen_dividend_stocks(params)

        assert result["success"] is True
        assert "total" in result
        assert "stocks" in result
        assert isinstance(result["stocks"], list)
        assert len(result["stocks"]) <= 10

    def test_screen_dividend_stocks_filters_correctly(self):
        """Test that filters are applied correctly"""
        service = DividendService()
        params = {
            "min_yield": 5.0,
            "min_years": 5,
            "limit": 50
        }
        result = service.screen_dividend_stocks(params)

        if result["success"] and result["stocks"]:
            for stock in result["stocks"]:
                assert stock["latest_yield"] >= 5.0
                assert stock["consecutive_years"] >= 5

    def test_screen_dividend_stocks_sorted_by_yield(self):
        """Test that results are sorted by yield descending"""
        service = DividendService()
        params = {"min_yield": 2.0, "limit": 20}
        result = service.screen_dividend_stocks(params)

        if result["success"] and len(result["stocks"]) > 1:
            yields = [s["latest_yield"] for s in result["stocks"]]
            assert yields == sorted(yields, reverse=True)


class TestGetDividendCalendar:
    def test_get_dividend_calendar_success(self):
        """Test successful dividend calendar query"""
        service = DividendService()
        result = service.get_dividend_calendar(
            start_date="2026-06-01",
            end_date="2026-06-30",
            event="ex_dividend"
        )

        assert result["success"] is True
        assert result["period"] == "2026-06-01 至 2026-06-30"
        assert result["event_type"] == "除权除息日"
        assert "events" in result
        assert isinstance(result["events"], list)

    def test_get_dividend_calendar_sorted_by_date(self):
        """Test that events are sorted by date"""
        service = DividendService()
        result = service.get_dividend_calendar(
            start_date="2026-01-01",
            end_date="2026-12-31",
            event="ex_dividend"
        )

        if result["success"] and len(result["events"]) > 1:
            dates = [e["date"] for e in result["events"]]
            assert dates == sorted(dates)

    def test_get_dividend_calendar_different_events(self):
        """Test different event types"""
        service = DividendService()

        events = ["ex_dividend", "record_date", "pay_date"]
        event_names = ["除权除息日", "股权登记日", "派息日"]

        for event, expected_name in zip(events, event_names):
            result = service.get_dividend_calendar(
                start_date="2026-06-01",
                end_date="2026-06-30",
                event=event
            )
            assert result["event_type"] == expected_name


def _icbc_like_df():
    """ICBC-style data with semi-annual payments (interim + final per year).

    Yields are in PERCENT (the established contract). Two 2024 payments total ~4.99%.
    """
    rows = [
        ("2024", 1.434, 2.94, "2025-01-07"),
        ("2024", 1.646, 2.05, "2025-07-14"),
        ("2023", 3.064, 4.94, "2024-07-16"),
        ("2022", 3.035, 6.23, "2023-07-17"),
        ("2021", 2.933, 6.12, "2022-07-12"),
    ]
    return pd.DataFrame([
        {
            "股票代码": "601398",
            "股票简称": "工商银行",
            "分红年度": year,
            "每股派息": cash,
            "送股比例": 0.0,
            "转增比例": 0.0,
            "股息率": yld,
            "公告日期": "",
            "除权除息日": ex,
            "股权登记日": "",
            "派息日": "",
        }
        for year, cash, yld, ex in rows
    ])


class TestScreenRegression:
    """Regression tests for the high-dividend screen returning 0 stocks."""

    def _service(self, df):
        svc = DividendService(data_source=MockDividendSource(df))
        svc._get_stock_pool = lambda: ["601398.SH"]  # avoid network
        return svc

    def test_screen_finds_high_yield_stock_with_percent_filter(self):
        """The reported bug: screen with min_yield=3.0 must find a ~5% yield stock."""
        svc = self._service(_icbc_like_df())
        result = svc.screen_dividend_stocks({"min_yield": 3.0, "limit": 10})

        assert result["success"] is True
        assert result["total"] == 1
        assert result["stocks"][0]["symbol"] == "601398.SH"

    def test_latest_yield_is_latest_fiscal_year_total(self):
        """latest_yield must aggregate ALL of the latest fiscal year's payments
        (interim + final), not just the single most recent payment."""
        svc = self._service(_icbc_like_df())
        stock = svc._query_single_stock("601398.SH")

        # 2024 total = 2.94 + 2.05 = 4.99
        assert stock["latest_yield"] == pytest.approx(4.99, rel=1e-2)

    def test_consecutive_years_counts_distinct_fiscal_years(self):
        """consecutive_years must count distinct fiscal years, not payment records.
        5 records across 4 distinct years (2021-2024) -> 4, not 5."""
        svc = self._service(_icbc_like_df())
        stock = svc._query_single_stock("601398.SH")

        assert stock["consecutive_years"] == 4

    def test_min_payout_ratio_does_not_nuke_results_when_unavailable(self):
        """avg_payout_ratio is always 0.0 (akshare/EastMoney don't provide it).
        Passing min_payout_ratio must not silently filter everything to 0."""
        svc = self._service(_icbc_like_df())
        result = svc.screen_dividend_stocks({"min_yield": 3.0, "min_payout_ratio": 30, "limit": 10})

        assert result["success"] is True
        assert result["total"] == 1
