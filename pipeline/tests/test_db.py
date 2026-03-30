"""Tests for the pipeline SQLite database wrapper."""

from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from pipeline.db import Database


class DatabaseTests(unittest.TestCase):
    """Verify schema migration and stock persistence behavior."""

    def setUp(self) -> None:
        """Create a temporary SQLite database path for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"

    def tearDown(self) -> None:
        """Clean up the temporary database directory."""
        self.temp_dir.cleanup()

    def test_migrate_adds_new_stock_columns_to_existing_table(self) -> None:
        """Database migration should add missing analytics columns."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE stocks (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    industry TEXT,
                    market_cap REAL,
                    pe REAL,
                    pb REAL,
                    is_st INTEGER DEFAULT 0,
                    list_date TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

        database = Database(str(self.db_path))
        cursor = database.conn.cursor()
        cursor.execute("PRAGMA table_info(stocks)")
        columns = {row[1] for row in cursor.fetchall()}
        database.close()

        expected_columns = {
            "sector",
            "roe",
            "net_profit_growth",
            "gross_margin",
            "debt_ratio",
            "avg_turnover_rate",
            "avg_volume",
            "avg_amount",
        }
        self.assertTrue(expected_columns.issubset(columns))

    def test_migrate_adds_turnover_rate_to_existing_daily_klines_table(self) -> None:
        """Database migration should add missing turnover_rate to daily klines."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE daily_klines (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    amount REAL,
                    PRIMARY KEY (symbol, date)
                )
                """
            )
            conn.commit()

        database = Database(str(self.db_path))
        cursor = database.conn.cursor()
        cursor.execute("PRAGMA table_info(daily_klines)")
        columns = {row[1] for row in cursor.fetchall()}
        database.close()

        self.assertIn("turnover_rate", columns)

    def test_upsert_stocks_and_query_helpers_work(self) -> None:
        """Upsert should insert and update rows while helper queries stay accurate."""
        database = Database(str(self.db_path))

        inserted = database.upsert_stocks(
            [
                {
                    "symbol": "600519",
                    "name": "贵州茅台",
                    "market": "A",
                    "industry": "白酒",
                    "sector": "消费",
                    "market_cap": 20000.5,
                    "pe": 22.1,
                    "pb": 8.6,
                    "roe": 30.2,
                    "net_profit_growth": 12.4,
                    "gross_margin": 91.0,
                    "debt_ratio": 18.5,
                    "avg_turnover_rate": 0.35,
                    "avg_volume": 123456.0,
                    "avg_amount": 98765.0,
                    "list_date": "2001-08-27",
                },
                {
                    "symbol": "00700",
                    "name": "腾讯控股",
                    "market": "HK",
                },
            ]
        )

        self.assertEqual(inserted, 2)
        self.assertEqual(database.count_stocks(), 2)
        self.assertEqual(database.count_stocks("A"), 1)
        self.assertEqual(database.count_stocks("HK"), 1)
        self.assertEqual(database.get_all_symbols("A"), ["600519"])
        self.assertEqual(database.get_all_symbols("HK"), ["00700"])

        updated = database.upsert_stocks(
            [
                {
                    "symbol": "600519",
                    "name": "贵州茅台股份",
                    "market": "A",
                    "industry": "白酒",
                    "sector": "高端消费",
                    "roe": 31.5,
                }
            ]
        )

        self.assertEqual(updated, 1)
        row = database.conn.execute(
            "SELECT name, sector, roe FROM stocks WHERE symbol = ?",
            ("600519",),
        ).fetchone()
        database.close()

        self.assertEqual(row["name"], "贵州茅台股份")
        self.assertEqual(row["sector"], "高端消费")
        self.assertEqual(row["roe"], 31.5)

    def test_print_status_reports_counts_kline_coverage_and_latest_update(self) -> None:
        """Status output should summarize stock counts and update metadata."""
        database = Database(str(self.db_path))
        database.upsert_stocks(
            [
                {"symbol": "000001", "name": "平安银行", "market": "A"},
                {"symbol": "0005", "name": "汇丰控股", "market": "HK"},
            ]
        )
        database.conn.execute(
            """
            INSERT INTO daily_klines (symbol, date, open, high, low, close, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("000001", "2026-03-28", 1.0, 1.2, 0.9, 1.1, 1000.0, 2000.0),
        )
        database.conn.commit()

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            database.print_status()

        output = buffer.getvalue()
        database.close()

        self.assertIn("数据库状态", output)
        self.assertIn("A股数量: 1", output)
        self.assertIn("港股数量: 1", output)
        self.assertIn("K线数据覆盖股票数: 1", output)
        self.assertIn("最后更新时间:", output)

    def test_get_klines_returns_turnover_rate_column(self) -> None:
        """K-line queries should include turnover_rate when present in the schema."""
        database = Database(str(self.db_path))
        database.conn.execute(
            """
            INSERT INTO daily_klines (
                symbol, date, open, high, low, close, volume, amount, turnover_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("000001", "2026-03-28", 1.0, 1.2, 0.9, 1.1, 1000.0, 2000.0, 3.5),
        )
        database.conn.commit()

        klines = database.get_klines("000001", 10)
        database.close()

        self.assertIn("turnover_rate", klines.columns)
        self.assertEqual(float(klines.iloc[0]["turnover_rate"]), 3.5)


if __name__ == "__main__":
    unittest.main()
