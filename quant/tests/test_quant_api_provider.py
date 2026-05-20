"""Tests for the legacy JSON-RPC QuantAPI bridge."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.quant_api import QuantAPI
from quantsys.data.db import Database


class HelperOnlyDB:
    """Fake provider exposing only Database helper methods QuantAPI should use."""

    provider = "postgres"

    def __init__(self) -> None:
        self.last_klines_args = None

    def get_latest_factor_date_for_symbol(self, symbol: str):
        return "2026-05-18" if symbol == "600036" else None

    def get_factor_values(self, symbol: str, date: str):
        if symbol == "600036" and date == "2026-05-18":
            return {"RSI": 42.0}
        return {}

    def get_backtest_klines(self, symbol: str, start_date=None, end_date=None, limit=None):
        self.last_klines_args = (symbol, start_date, end_date, limit)
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "timestamp": "2026-05-17",
                    "open": 1.0,
                    "high": 2.0,
                    "low": 0.5,
                    "close": 1.5,
                    "volume": 100.0,
                    "amount": 150.0,
                },
                {
                    "timestamp": "2026-05-18",
                    "open": 2.0,
                    "high": 3.0,
                    "low": 1.5,
                    "close": 2.5,
                    "volume": 200.0,
                    "amount": float("nan"),
                },
            ]
        )

    def get_stock_rows(self, market=None, has_data=False):
        rows = [
            {"symbol": "600036", "name": "招商银行", "market": "A"},
            {"symbol": "00700", "name": "腾讯控股", "market": "HK"},
        ]
        if market:
            rows = [row for row in rows if row["market"] == market]
        return rows


class QuantAPIProviderTests(unittest.TestCase):
    """Verify QuantAPI uses provider-safe database access."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "stocks.db"
        self.env_patch = patch.dict("os.environ", {"QUANT_DB_PROVIDER": "postgres"})
        self.env_patch.start()
        self.db_mock_patch = patch("quantsys.data.db.psycopg2")
        self.db_mock = self.db_mock_patch.start()
        self.db_mock.connect.return_value.cursor.return_value.fetchall.return_value = []
        self.database = Database(str(self.db_path))
        self.api = QuantAPI.__new__(QuantAPI)
        self.api.db = self.database

    def tearDown(self) -> None:
        self.database.close()
        self.db_mock_patch.stop()
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def test_get_stock_factors_uses_latest_factor_date(self) -> None:
        self.database.upsert_stocks([{"symbol": "600036", "name": "招商银行", "market": "A"}])
        self.database.upsert_factor_values(
            [
                ("600036", "2026-05-17", "RSI", 35.0),
                ("600036", "2026-05-18", "RSI", 42.0),
                ("600036", "2026-05-18", "MA5", 37.5),
            ]
        )

        result = self.api.get_stock_factors("600036")

        self.assertEqual(result["symbol"], "600036")
        self.assertEqual(result["date"], "2026-05-18")
        self.assertEqual(result["factors"], {"RSI": 42.0, "MA5": 37.5})

    def test_get_klines_preserves_descending_json_shape_with_dates(self) -> None:
        self.database.upsert_stocks([{"symbol": "600036", "name": "招商银行", "market": "A"}])
        self.database.upsert_daily_klines(
            [
                {
                    "symbol": "600036",
                    "date": "2026-05-17",
                    "open": 1.0,
                    "high": 2.0,
                    "low": 0.5,
                    "close": 1.5,
                    "volume": 100.0,
                    "amount": 150.0,
                },
                {
                    "symbol": "600036",
                    "date": "2026-05-18",
                    "open": 2.0,
                    "high": 3.0,
                    "low": 1.5,
                    "close": 2.5,
                    "volume": 200.0,
                    "amount": 250.0,
                },
            ]
        )

        result = self.api.get_klines("600036", start_date="2026-05-17", limit=10)

        self.assertEqual(result["symbol"], "600036")
        self.assertEqual(result["count"], 2)
        self.assertEqual([row["date"] for row in result["klines"]], ["2026-05-18", "2026-05-17"])
        self.assertEqual(
            set(result["klines"][0]),
            {"date", "open", "high", "low", "close", "volume", "amount"},
        )

    def test_get_stock_list_filters_has_data_and_market(self) -> None:
        self.database.upsert_stocks(
            [
                {"symbol": "600036", "name": "招商银行", "market": "A"},
                {"symbol": "00700", "name": "腾讯控股", "market": "HK"},
                {"symbol": "000001", "name": "平安银行", "market": "A"},
            ]
        )
        self.database.upsert_daily_klines(
            [
                {
                    "symbol": "600036",
                    "date": "2026-05-18",
                    "open": 1.0,
                    "high": 1.0,
                    "low": 1.0,
                    "close": 1.0,
                    "volume": 1.0,
                    "amount": 1.0,
                }
            ]
        )

        result = self.api.get_stock_list(market="A", has_data=True)

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["stocks"], [{"symbol": "600036", "name": "招商银行", "market": "A"}])

    def test_bridge_methods_do_not_require_raw_database_connection(self) -> None:
        api = QuantAPI.__new__(QuantAPI)
        api.db = HelperOnlyDB()

        factors = api.get_stock_factors("600036")
        klines = api.get_klines("600036", limit=2)
        stocks = api.get_stock_list(market="A", has_data=True)

        self.assertEqual(factors["date"], "2026-05-18")
        self.assertEqual(factors["factors"], {"RSI": 42.0})
        self.assertEqual([row["date"] for row in klines["klines"]], ["2026-05-18", "2026-05-17"])
        self.assertIsNone(klines["klines"][0]["amount"])
        self.assertEqual(stocks["stocks"], [{"symbol": "600036", "name": "招商银行", "market": "A"}])


if __name__ == "__main__":
    unittest.main()
