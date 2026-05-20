"""Tests for the legacy DBManager compatibility wrapper."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from quantsys.data.data.storage.db_manager import DBManager


class FakePostgresCursor:
    """Minimal cursor stub for PostgreSQL-branch DBManager tests."""

    def __init__(
        self,
        rows: list[tuple] | None = None,
        rowcount: int = 0,
        fetchone_rows: list[tuple] | None = None,
    ) -> None:
        self.rows = rows or []
        self.fetchone_rows = fetchone_rows
        self.fetchone_index = 0
        self.rowcount = rowcount
        self.executed: list[tuple[str, list | tuple | None]] = []
        self.closed = False

    def execute(self, query: str, params: list | tuple | None = None) -> None:
        self.executed.append((query, params))

    def fetchone(self):
        if self.fetchone_rows is not None:
            row = self.fetchone_rows[self.fetchone_index]
            self.fetchone_index += 1
            return row
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self) -> None:
        self.closed = True


class FakePostgresConnection:
    """Minimal connection stub that returns preconfigured cursors."""

    def __init__(self, cursors: list[FakePostgresCursor]) -> None:
        self.cursors = cursors
        self.committed = False
        self.rolled_back = False

    def cursor(self) -> FakePostgresCursor:
        return self.cursors.pop(0)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class DBManagerTests(unittest.TestCase):
    """Verify DBManager delegates writes through provider-aware Database APIs."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_save_klines_delegates_to_database_upsert(self) -> None:
        fake_database = Mock()
        fake_database.upsert_daily_klines.return_value = 1

        with patch("quantsys.data.data.storage.db_manager.Database", return_value=fake_database):
            manager = DBManager(str(self.db_path))

        frame = pd.DataFrame([
            {
                "date": "2026-05-19",
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 100.0,
                "amount": 150.0,
                "turnover_rate": 3.0,
            }
        ])

        saved = manager.save_klines("000001", frame)

        self.assertEqual(saved, 1)
        fake_database.upsert_daily_klines.assert_called_once_with([
            {
                "symbol": "000001",
                "date": "2026-05-19",
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 100.0,
                "amount": 150.0,
                "turnover_rate": 3.0,
            }
        ])

    def test_save_and_load_klines_sqlite_regression(self) -> None:
        manager = DBManager(str(self.db_path))
        try:
            manager.db.upsert_stocks([{"symbol": "000001", "name": "平安银行", "market": "A"}])
            saved = manager.save_klines(
                "000001",
                pd.DataFrame([
                    {
                        "date": "2026-05-19",
                        "open": 1.0,
                        "high": 2.0,
                        "low": 0.5,
                        "close": 1.5,
                        "volume": 100.0,
                        "amount": 150.0,
                        "turnover_rate": 3.0,
                    }
                ]),
            )
            loaded = manager.load_klines("000001")
        finally:
            manager.close()

        self.assertEqual(saved, 1)
        self.assertEqual(len(loaded.index), 1)
        self.assertEqual(float(loaded.iloc[0]["close"]), 1.5)

    def test_load_klines_uses_postgres_table_and_trade_date(self) -> None:
        fake_database = Mock()
        fake_database.provider = "postgres"
        fake_database._get_connection.return_value = object()

        with patch("quantsys.data.data.storage.db_manager.Database", return_value=fake_database):
            manager = DBManager(str(self.db_path))

        with patch("quantsys.data.data.storage.db_manager.pd.read_sql_query") as read_sql:
            read_sql.return_value = pd.DataFrame()
            manager.load_klines("000001", start_date="20260501", end_date="20260519")

        query = read_sql.call_args.args[0]
        params = read_sql.call_args.kwargs["params"]
        self.assertIn("FROM quant.daily_klines", query)
        self.assertIn("trade_date::text AS date", query)
        self.assertIn("trade_date >=", query)
        self.assertIn("trade_date <=", query)
        self.assertNotIn(" daily_klines\n", query.replace("quant.daily_klines", ""))
        self.assertEqual(params, ["000001", "2026-05-01", "2026-05-19"])

    def test_delete_klines_uses_postgres_delete_syntax(self) -> None:
        cursor = FakePostgresCursor(rowcount=3)
        connection = FakePostgresConnection([cursor])
        fake_database = Mock()
        fake_database.provider = "postgres"
        fake_database._get_connection.return_value = connection

        with patch("quantsys.data.data.storage.db_manager.Database", return_value=fake_database):
            manager = DBManager(str(self.db_path))

        deleted = manager.delete_klines("000001", start_date="20260501", end_date="20260519")

        self.assertEqual(deleted, 3)
        query, params = cursor.executed[0]
        self.assertIn("DELETE FROM quant.daily_klines", query)
        self.assertIn("trade_date >=", query)
        self.assertIn("trade_date <=", query)
        self.assertIn("%s", query)
        self.assertNotIn("?", query)
        self.assertEqual(params, ["000001", "2026-05-01", "2026-05-19"])
        self.assertTrue(connection.committed)
        self.assertTrue(cursor.closed)

    def test_get_symbols_uses_postgres_boolean_filters(self) -> None:
        cursor = FakePostgresCursor(rows=[("000001",), ("000002",)])
        connection = FakePostgresConnection([cursor])
        fake_database = Mock()
        fake_database.provider = "postgres"
        fake_database._get_connection.return_value = connection

        with patch("quantsys.data.data.storage.db_manager.Database", return_value=fake_database):
            manager = DBManager(str(self.db_path))

        symbols = manager.get_symbols(market="A", min_market_cap=100.0)

        self.assertEqual(symbols, ["000001", "000002"])
        query, params = cursor.executed[0]
        self.assertIn("FROM quant.stocks", query)
        self.assertIn("market = %s", query)
        self.assertIn("market_cap >= %s", query)
        self.assertIn("is_st = false", query)
        self.assertIn("is_suspended = false", query)
        self.assertNotIn("?", query)
        self.assertEqual(params, ["A", 100.0])

    def test_get_stock_info_uses_postgres_schema(self) -> None:
        cursor = FakePostgresCursor(
            rows=[("000001", "平安银行", "A", "银行", None, 100.0, 8.0, 1.0, False, False, "1991-04-03")]
        )
        connection = FakePostgresConnection([cursor])
        fake_database = Mock()
        fake_database.provider = "postgres"
        fake_database._get_connection.return_value = connection

        with patch("quantsys.data.data.storage.db_manager.Database", return_value=fake_database):
            manager = DBManager(str(self.db_path))

        info = manager.get_stock_info("000001")

        self.assertEqual(info["symbol"], "000001")
        query, params = cursor.executed[0]
        self.assertIn("FROM quant.stocks", query)
        self.assertIn("list_date::text", query)
        self.assertEqual(params, ("000001",))

    def test_get_statistics_uses_database_counts_and_postgres_tables(self) -> None:
        cursor = FakePostgresCursor(fetchone_rows=[(5601,), (2756661,), ("2026-05-19",)])
        connection = FakePostgresConnection([cursor])
        fake_database = Mock()
        fake_database.provider = "postgres"
        fake_database._get_connection.return_value = connection
        fake_database.count_stocks.side_effect = [5847, 5847, 0]

        with patch("quantsys.data.data.storage.db_manager.Database", return_value=fake_database):
            manager = DBManager(str(self.db_path))

        stats = manager.get_statistics()

        self.assertEqual(stats["total_stocks"], 5847)
        self.assertEqual(stats["stocks_with_klines"], 5601)
        self.assertEqual(stats["total_kline_records"], 2756661)
        self.assertEqual(stats["last_update"], "2026-05-19")
        executed_queries = [query for query, _ in cursor.executed]
        self.assertEqual(len(executed_queries), 3)
        self.assertTrue(all("quant." in query for query in executed_queries))


if __name__ == "__main__":
    unittest.main()
