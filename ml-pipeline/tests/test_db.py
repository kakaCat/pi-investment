"""Tests for the ml-pipeline SQLite database wrapper."""

from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "db.py"
SPEC = importlib.util.spec_from_file_location("ml_pipeline_db", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load database module from {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
Database = MODULE.Database


class DatabaseTests(unittest.TestCase):
    """Verify ml-pipeline schema compatibility for kline turnover rate."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_migrate_adds_turnover_rate_to_existing_daily_klines_table(self) -> None:
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

    def test_get_klines_returns_turnover_rate_column(self) -> None:
        database = Database(str(self.db_path))
        database.conn.execute(
            """
            INSERT INTO daily_klines (
                symbol, date, open, high, low, close, volume, amount, turnover_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("000001", "2026-03-28", 1.0, 1.2, 0.9, 1.1, 1000.0, 2000.0, 2.8),
        )
        database.conn.commit()

        klines = database.get_klines("000001", 10)
        database.close()

        self.assertIn("turnover_rate", klines.columns)
        self.assertEqual(float(klines.iloc[0]["turnover_rate"]), 2.8)


if __name__ == "__main__":
    unittest.main()
