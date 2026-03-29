"""Tests for the daily kline fetcher."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from pipeline.db import Database
from pipeline.fetchers.klines import KlineFetcher


class KlineFetcherTests(unittest.TestCase):
    """Verify batch kline updates, market routing, and persistence."""

    def setUp(self) -> None:
        """Create a fresh database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"
        self.database = Database(str(self.db_path))

    def tearDown(self) -> None:
        """Release temporary database resources."""
        self.database.close()
        self.temp_dir.cleanup()

    def test_run_defaults_to_all_symbols_and_continues_after_failures(self) -> None:
        """run should process all symbols by default and keep going after errors."""
        self.database.upsert_stocks(
            [
                {"symbol": f"{index:06d}", "name": f"股票{index}", "market": "A"}
                for index in range(1, 56)
            ]
        )
        fetcher = KlineFetcher(self.database)
        stdout = io.StringIO()

        with patch.object(
            fetcher,
            "_update_symbol",
            side_effect=[3, RuntimeError("boom"), *([1] * 53)],
        ) as update_symbol:
            with redirect_stdout(stdout):
                fetcher.run()

        self.assertEqual(update_symbol.call_count, 55)
        self.assertEqual(update_symbol.call_args_list[0].args, ("000001", 730))
        self.assertEqual(update_symbol.call_args_list[-1].args, ("000055", 730))
        output = stdout.getvalue()
        self.assertIn("[Klines] 开始更新 55 只股票的K线数据...", output)
        self.assertIn("[2/55] 000002 失败: boom", output)
        self.assertIn("[Klines] 完成，成功 54/55", output)

    def test_update_symbol_persists_a_share_daily_klines(self) -> None:
        """_update_symbol should fetch A-share history and upsert daily_klines rows."""
        self.database.upsert_stocks(
            [{"symbol": "600519", "name": "贵州茅台", "market": "A"}]
        )
        fetcher = KlineFetcher(self.database)
        frame = pd.DataFrame(
            [
                {
                    "日期": "2026-03-27",
                    "开盘": 1450.0,
                    "最高": 1466.0,
                    "最低": 1442.0,
                    "收盘": 1460.0,
                    "成交量": 123456.0,
                    "成交额": 789000000.0,
                },
                {
                    "日期": "2026-03-28",
                    "开盘": 1460.0,
                    "最高": 1472.0,
                    "最低": 1451.0,
                    "收盘": 1468.0,
                    "成交量": 120000.0,
                    "成交额": 800000000.0,
                },
            ]
        )

        with patch(
            "pipeline.fetchers.klines.ak.stock_zh_a_hist",
            return_value=frame,
        ) as fetch_mock:
            inserted = fetcher._update_symbol("600519", days=30)

        row = self.database.conn.execute(
            """
            SELECT open, high, low, close, volume, amount
            FROM daily_klines
            WHERE symbol = ? AND date = ?
            """,
            ("600519", "2026-03-28"),
        ).fetchone()

        self.assertEqual(inserted, 2)
        self.assertEqual(fetch_mock.call_args.kwargs["symbol"], "600519")
        self.assertEqual(fetch_mock.call_args.kwargs["period"], "daily")
        self.assertEqual(fetch_mock.call_args.kwargs["adjust"], "qfq")
        self.assertEqual(
            dict(row),
            {
                "open": 1460.0,
                "high": 1472.0,
                "low": 1451.0,
                "close": 1468.0,
                "volume": 120000.0,
                "amount": 800000000.0,
            },
        )

    def test_update_symbol_uses_hk_history_api_for_hk_stocks(self) -> None:
        """_update_symbol should route Hong Kong symbols to the HK AkShare API."""
        self.database.upsert_stocks(
            [{"symbol": "00700", "name": "腾讯控股", "market": "HK"}]
        )
        fetcher = KlineFetcher(self.database)
        frame = pd.DataFrame(
            [
                {
                    "日期": "2026-03-28",
                    "开盘": 320.0,
                    "最高": 325.0,
                    "最低": 318.0,
                    "收盘": 323.0,
                    "成交量": 8800000.0,
                    "成交额": 2800000000.0,
                }
            ]
        )

        with patch(
            "pipeline.fetchers.klines.ak.stock_hk_hist",
            return_value=frame,
        ) as fetch_mock:
            inserted = fetcher._update_symbol("00700", days=15)

        row = self.database.conn.execute(
            "SELECT close FROM daily_klines WHERE symbol = ? AND date = ?",
            ("00700", "2026-03-28"),
        ).fetchone()

        self.assertEqual(inserted, 1)
        self.assertEqual(fetch_mock.call_args.kwargs["symbol"], "00700")
        self.assertEqual(fetch_mock.call_args.kwargs["period"], "daily")
        self.assertEqual(fetch_mock.call_args.kwargs["adjust"], "qfq")
        self.assertEqual(row["close"], 323.0)


if __name__ == "__main__":
    unittest.main()
