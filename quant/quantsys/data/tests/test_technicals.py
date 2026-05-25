"""Tests for technical indicator calculation and persistence."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import pandas as pd

from quantsys.data.db import Database
from quantsys.data.fetchers.technicals import TechnicalCalculator


class TechnicalCalculatorTests(unittest.TestCase):
    """Verify 20-day technical metric calculation behavior."""

    def setUp(self) -> None:
        """Create a fresh temporary database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"
        self.database = Database(str(self.db_path))
        self.database.upsert_stocks(
            [{"symbol": "600519", "name": "贵州茅台", "market": "A"}]
        )
        self.calculator = TechnicalCalculator(self.database)

    def tearDown(self) -> None:
        """Release temporary database resources."""
        self.database.close()
        self.temp_dir.cleanup()

    def test_calculate_and_update_persists_20_day_averages(self) -> None:
        """Calculator should average the latest 20 kline rows and update stocks."""
        for offset in range(20):
            day = offset + 1
            self.database.conn.execute(
                """
                INSERT INTO daily_klines (
                    symbol, date, open, high, low, close, volume, amount, turnover_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "600519",
                    f"2026-03-{day:02d}",
                    10.0,
                    11.0,
                    9.0,
                    10.5,
                    float(1000 + offset),
                    float(20000 + offset * 1000),
                    float(offset + 1),
                ),
            )
        self.database.conn.commit()

        result = self.calculator.calculate_and_update("600519")
        row = self.database.conn.execute(
            """
            SELECT avg_turnover_rate, avg_volume, avg_amount
            FROM stocks
            WHERE symbol = ?
            """,
            ("600519",),
        ).fetchone()

        self.assertEqual(result, dict(row))
        self.assertAlmostEqual(result["avg_turnover_rate"], 10.5)
        self.assertAlmostEqual(result["avg_volume"], 1009.5)
        self.assertAlmostEqual(result["avg_amount"], 2.95)

    def test_calculate_and_update_skips_when_kline_rows_are_insufficient(self) -> None:
        """Calculator should skip symbols with fewer than 20 daily klines."""
        for day in range(1, 20):
            self.database.conn.execute(
                """
                INSERT INTO daily_klines (
                    symbol, date, open, high, low, close, volume, amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "600519",
                    f"2026-03-{day:02d}",
                    10.0,
                    11.0,
                    9.0,
                    10.5,
                    1000.0,
                    20000.0,
                ),
            )
        self.database.conn.commit()

        result = self.calculator.calculate_and_update("600519")
        row = self.database.conn.execute(
            """
            SELECT avg_turnover_rate, avg_volume, avg_amount
            FROM stocks
            WHERE symbol = ?
            """,
            ("600519",),
        ).fetchone()

        self.assertEqual(result, {})
        self.assertIsNone(row["avg_turnover_rate"])
        self.assertIsNone(row["avg_volume"])
        self.assertIsNone(row["avg_amount"])

    def test_calculate_and_update_handles_missing_turnover_rate_column(self) -> None:
        """Calculator should still update volume and amount when turnover is unavailable."""
        for day in range(1, 21):
            self.database.conn.execute(
                """
                INSERT INTO daily_klines (
                    symbol, date, open, high, low, close, volume, amount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "600519",
                    f"2026-03-{day:02d}",
                    10.0,
                    11.0,
                    9.0,
                    10.5,
                    float(2000 + day),
                    float(30000 + day * 1000),
                ),
            )
        self.database.conn.commit()

        result = self.calculator.calculate_and_update("600519")

        self.assertIsNone(result["avg_turnover_rate"])
        self.assertAlmostEqual(result["avg_volume"], 2010.5)
        self.assertAlmostEqual(result["avg_amount"], 4.05)

    def test_calculate_and_update_wraps_database_errors(self) -> None:
        """Calculator should raise a readable runtime error when the database fails."""
        self.database.conn.close()

        with self.assertRaisesRegex(RuntimeError, "Failed to calculate technicals"):
            self.calculator.calculate_and_update("600519")

        self.database.conn = None

    def test_calculate_and_update_uses_database_abstraction(self) -> None:
        """Calculator should not depend on SQLite-only cursor operations."""
        fake_db = Mock()
        fake_db.get_recent_klines.return_value = pd.DataFrame(
            [
                {
                    "volume": float(1000 + index),
                    "amount": float(20000 + index * 1000),
                    "turnover_rate": float(index + 1),
                }
                for index in range(20)
            ]
        )
        calculator = TechnicalCalculator(fake_db)

        result = calculator.calculate_and_update("600519")

        fake_db.get_recent_klines.assert_called_once_with("600519", 20)
        fake_db.update_stock_technicals.assert_called_once_with("600519", result)
        self.assertAlmostEqual(result["avg_turnover_rate"], 10.5)


if __name__ == "__main__":
    unittest.main()
