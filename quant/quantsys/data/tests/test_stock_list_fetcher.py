"""Tests for the stock list fetcher."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd

from quantsys.data.fetchers.stock_list import StockListFetcher


class StockListFetcherTests(unittest.TestCase):
    """Verify stock list routing, mapping, retry, and progress output."""

    def test_run_routes_a_market_results_into_database(self) -> None:
        """run should fetch A-share rows, upsert them, and start technical updates."""

        class FakeDatabase:
            def __init__(self) -> None:
                self.received: list[dict[str, Any]] | None = None
                self.requested_market: str | None = None

            def upsert_stocks(self, stocks: list[dict[str, Any]]) -> int:
                self.received = stocks
                return len(stocks)

            def get_all_symbols(self, market: str | None = None) -> list[str]:
                self.requested_market = market
                return []

        database = FakeDatabase()
        fetcher = StockListFetcher(database)
        expected_rows = [{"symbol": "600519", "name": "贵州茅台", "market": "A"}]

        with patch.object(fetcher, "_fetch_a_stocks", return_value=expected_rows):
            fetcher.run()

        self.assertEqual(database.received, expected_rows)
        self.assertEqual(database.requested_market, "A")

    def test_run_rejects_unsupported_market(self) -> None:
        """run should reject unsupported market codes."""

        class FakeDatabase:
            def upsert_stocks(self, stocks: list[dict[str, Any]]) -> int:
                return len(stocks)

        fetcher = StockListFetcher(FakeDatabase())

        with self.assertRaisesRegex(ValueError, "不支持的市场"):
            fetcher.run(market="US")

    def test_fetch_a_stocks_maps_rows_and_prints_progress_every_100(self) -> None:
        """A-share fetch should normalize Sina AkShare rows and emit progress updates."""
        database = MagicMock()
        fetcher = StockListFetcher(database)
        # Sina format: code includes exchange prefix (sh/sz/bj)
        frame = pd.DataFrame(
            [
                {
                    "代码": f"sh{index:06d}" if index < 600000 else f"sz{index:06d}",
                    "名称": f"股票{index}",
                }
                for index in range(1, 201)
            ]
        )
        stdout = io.StringIO()

        with patch.object(fetcher, "_fetch_a_stocks_em", return_value=None):
            with patch("quantsys.data.fetchers.stock_list.ak.stock_zh_a_spot", return_value=frame):
                with redirect_stdout(stdout):
                    stocks = fetcher._fetch_a_stocks()

        self.assertEqual(len(stocks), 200)
        # Sina mapper strips exchange prefix
        self.assertEqual(stocks[0]["symbol"], "000001")
        self.assertEqual(stocks[0]["market"], "A")
        # Sina has no industry/PE/PB/market_cap — fields are None
        self.assertIsNone(stocks[0]["industry"])
        self.assertIsNone(stocks[0]["market_cap"])
        self.assertIsNone(stocks[0]["pe"])
        self.assertIsNone(stocks[0]["pb"])
        output = stdout.getvalue()
        self.assertIn("A股(新浪)进度: 100/200", output)
        self.assertIn("A股(新浪)进度: 200/200", output)

    def test_fetch_hk_stocks_maps_rows(self) -> None:
        """HK fetch should normalize AkShare rows into database payloads."""
        database = MagicMock()
        fetcher = StockListFetcher(database)
        frame = pd.DataFrame(
            [
                {
                    "代码": "00700",
                    "名称": "腾讯控股",
                    "总市值": 5600000000000,
                    "市盈率": 18.2,
                    "市净率": 3.1,
                }
            ]
        )

        with patch("quantsys.data.fetchers.stock_list.ak.stock_hk_spot_em", return_value=frame):
            stocks = fetcher._fetch_hk_stocks()

        self.assertEqual(
            stocks,
            [
                {
                    "symbol": "00700",
                    "name": "腾讯控股",
                    "market": "HK",
                    "market_cap": 56000.0,
                    "total_mv": 56000.0,
                    "circulating_mv": None,
                    "pe": 18.2,
                    "pb": 3.1,
                    "industry": None,
                }
            ],
        )

    def test_fetch_a_stocks_em_maps_rich_stock_fields(self) -> None:
        """East Money A-share rows should preserve industry and valuation fields."""
        database = MagicMock()
        fetcher = StockListFetcher(database)
        frame = pd.DataFrame(
            [
                {
                    "代码": "600519",
                    "名称": "贵州茅台",
                    "总市值": 2_200_000_000_000,
                    "流通市值": 2_150_000_000_000,
                    "市盈率-动态": 25.5,
                    "市净率": 8.2,
                    "所属行业": "酿酒行业",
                }
            ]
        )

        with patch("quantsys.data.fetchers.stock_list.ak.stock_zh_a_spot_em", return_value=frame):
            stocks = fetcher._fetch_a_stocks_em()

        self.assertEqual(
            stocks,
            [
                {
                    "symbol": "600519",
                    "name": "贵州茅台",
                    "market": "A",
                    "market_cap": 22000.0,
                    "total_mv": 22000.0,
                    "circulating_mv": 21500.0,
                    "pe": 25.5,
                    "pb": 8.2,
                    "industry": "酿酒行业",
                    "sector": "酿酒行业",
                }
            ],
        )

    def test_fetch_stock_fundamentals_maps_latest_financial_metrics(self) -> None:
        """Financial indicator rows should map latest metrics into stock columns."""
        database = MagicMock()
        fetcher = StockListFetcher(database)
        frame = pd.DataFrame(
            [
                {
                    "报告期": "2025-03-31",
                    "净资产收益率": "10.39%",
                    "销售毛利率": "91.2%",
                    "资产负债率": "14.1%",
                    "净利润同比增长率": "11.6%",
                },
                {
                    "报告期": "2025-06-30",
                    "净资产收益率": "19.03%",
                    "销售毛利率": "90.8%",
                    "资产负债率": "14.8%",
                    "净利润同比增长率": "8.8%",
                },
            ]
        )

        with patch(
            "quantsys.data.fetchers.stock_list.ak.stock_financial_abstract_ths",
            return_value=frame,
        ):
            result = fetcher._fetch_stock_fundamentals("600519")

        self.assertEqual(
            result,
            {
                "symbol": "600519",
                "roe": 19.03,
                "gross_margin": 90.8,
                "debt_ratio": 14.8,
                "net_profit_growth": 8.8,
            },
        )

    def test_fetch_stock_fundamentals_passes_start_year_to_akshare(self) -> None:
        """AkShare financial indicator API should receive a start_year argument."""
        database = MagicMock()
        fetcher = StockListFetcher(database)
        frame = pd.DataFrame(
            [
                {
                    "报告期": "2025-06-30",
                    "净资产收益率": "19.03%",
                    "销售毛利率": "90.8%",
                    "资产负债率": "14.8%",
                    "净利润同比增长率": "8.8%",
                }
            ]
        )

        with patch(
            "quantsys.data.fetchers.stock_list.ak.stock_financial_abstract_ths",
            return_value=frame,
        ) as indicator:
            fetcher._fetch_stock_fundamentals("600519")

        self.assertEqual(indicator.call_args.kwargs["symbol"], "600519")
        self.assertEqual(indicator.call_args.kwargs["indicator"], "按报告期")

    def test_backfill_fundamentals_flushes_each_progress_batch(self) -> None:
        """Fundamental backfill should persist successful rows incrementally."""
        database = MagicMock()
        database.upsert_stocks.side_effect = lambda rows: len(rows)
        fetcher = StockListFetcher(database)
        fetcher._PROGRESS_INTERVAL = 2

        with patch.object(
            fetcher,
            "_fetch_stock_fundamentals",
            side_effect=[
                {"symbol": "000001", "roe": 1.0},
                {"symbol": "000002", "roe": 2.0},
                {"symbol": "000003", "roe": 3.0},
            ],
        ):
            count = fetcher.backfill_fundamentals(["000001", "000002", "000003"])

        self.assertEqual(count, 3)
        self.assertEqual(database.upsert_stocks.call_count, 2)
        self.assertEqual(
            database.upsert_stocks.call_args_list[0].args[0],
            [{"symbol": "000001", "roe": 1.0}, {"symbol": "000002", "roe": 2.0}],
        )
        self.assertEqual(
            database.upsert_stocks.call_args_list[1].args[0],
            [{"symbol": "000003", "roe": 3.0}],
        )

    def test_backfill_industries_maps_board_constituents_to_stock_rows(self) -> None:
        """Industry backfill should persist industry and sector per constituent."""
        database = MagicMock()
        database.upsert_stocks.side_effect = lambda rows: len(rows)
        fetcher = StockListFetcher(database)
        boards = pd.DataFrame([{"板块名称": "酿酒行业"}, {"板块名称": "银行"}])
        liquor = pd.DataFrame(
            [
                {"代码": "600519", "名称": "贵州茅台"},
                {"代码": "000858", "名称": "五粮液"},
            ]
        )
        banks = pd.DataFrame([{"代码": "000001", "名称": "平安银行"}])

        with patch(
            "quantsys.data.fetchers.stock_list.ak.stock_board_industry_name_em",
            return_value=boards,
        ), patch(
            "quantsys.data.fetchers.stock_list.ak.stock_board_industry_cons_em",
            side_effect=[liquor, banks],
        ):
            count = fetcher.backfill_industries()

        self.assertEqual(count, 3)
        self.assertEqual(database.upsert_stocks.call_count, 1)
        self.assertEqual(
            database.upsert_stocks.call_args.args[0],
            [
                {
                    "symbol": "600519",
                    "name": "贵州茅台",
                    "market": "A",
                    "industry": "酿酒行业",
                    "sector": "酿酒行业",
                },
                {
                    "symbol": "000858",
                    "name": "五粮液",
                    "market": "A",
                    "industry": "酿酒行业",
                    "sector": "酿酒行业",
                },
                {
                    "symbol": "000001",
                    "name": "平安银行",
                    "market": "A",
                    "industry": "银行",
                    "sector": "银行",
                },
            ],
        )

    def test_fetch_a_stocks_retries_with_exponential_backoff(self) -> None:
        """Fetch should retry transient AkShare failures up to three attempts."""
        database = MagicMock()
        fetcher = StockListFetcher(database)
        frame = pd.DataFrame(
            [
                {
                    "代码": "sh600519",
                    "名称": "贵州茅台",
                }
            ]
        )

        with patch(
            "quantsys.data.fetchers.stock_list.ak.stock_zh_a_spot",
            side_effect=[RuntimeError("timeout"), RuntimeError("timeout"), frame],
        ) as fetch_mock, patch("quantsys.data.fetchers.stock_list.time.sleep") as sleep_mock:
            stocks = fetcher._fetch_a_stocks()

        self.assertEqual(fetch_mock.call_count, 3)
        self.assertEqual(sleep_mock.call_args_list[0].args[0], 1)
        self.assertEqual(sleep_mock.call_args_list[1].args[0], 2)
        # Sina mapper strips exchange prefix
        self.assertEqual(stocks[0]["symbol"], "600519")

    def test_fetch_hk_stocks_raises_after_three_failures(self) -> None:
        """Fetch should surface a readable error after exhausting retries."""
        database = MagicMock()
        fetcher = StockListFetcher(database)

        with patch(
            "quantsys.data.fetchers.stock_list.ak.stock_hk_spot_em",
            side_effect=RuntimeError("service unavailable"),
        ), patch("quantsys.data.fetchers.stock_list.time.sleep") as sleep_mock:
            with self.assertRaisesRegex(RuntimeError, "港股列表拉取失败"):
                fetcher._fetch_hk_stocks()

        self.assertEqual([call.args[0] for call in sleep_mock.call_args_list], [1, 2])

    def test_update_technical_indicators_limits_to_100_symbols_and_prints_progress(self) -> None:
        """Technical updates should process only the first 100 symbols and print every 10."""

        class FakeDatabase:
            def __init__(self) -> None:
                self.requested_market: str | None = None

            def get_all_symbols(self, market: str | None = None) -> list[str]:
                self.requested_market = market
                return [f"{index:06d}" for index in range(1, 106)]

        database = FakeDatabase()
        fetcher = StockListFetcher(database)
        calculator = MagicMock()
        stdout = io.StringIO()

        with patch(
            "quantsys.data.fetchers.technicals.TechnicalCalculator",
            return_value=calculator,
        ):
            with redirect_stdout(stdout):
                fetcher._update_technical_indicators("HK")

        self.assertEqual(database.requested_market, "HK")
        self.assertEqual(calculator.calculate_and_update.call_count, 100)
        self.assertEqual(
            [call.args[0] for call in calculator.calculate_and_update.call_args_list[:3]],
            ["000001", "000002", "000003"],
        )
        self.assertEqual(calculator.calculate_and_update.call_args_list[-1].args[0], "000100")
        output = stdout.getvalue()
        self.assertIn("[StockList] 计算技术指标...", output)
        self.assertIn("进度: 10/100", output)
        self.assertIn("进度: 100/100", output)

    def test_update_technical_indicators_continues_after_single_symbol_failure(self) -> None:
        """A single technical update failure should not stop later symbols."""

        class FakeDatabase:
            def get_all_symbols(self, market: str | None = None) -> list[str]:
                return ["000001", "000002", "000003"]

        fetcher = StockListFetcher(FakeDatabase())
        calculator = MagicMock()
        calculator.calculate_and_update.side_effect = [
            RuntimeError("boom"),
            {"avg_volume": 1.0},
            {"avg_volume": 2.0},
        ]
        stdout = io.StringIO()

        with patch(
            "quantsys.data.fetchers.technicals.TechnicalCalculator",
            return_value=calculator,
        ):
            with redirect_stdout(stdout):
                fetcher._update_technical_indicators("A")

        self.assertEqual(
            [call.args[0] for call in calculator.calculate_and_update.call_args_list],
            ["000001", "000002", "000003"],
        )
        self.assertIn("000001", stdout.getvalue())
        self.assertIn("boom", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
