"""Offline tests for API data update failure accounting."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from api import server


class DataUpdateFailureAccountingTests(unittest.TestCase):
    """Verify fetch failures are surfaced in /api/data/update semantics."""

    def test_single_symbol_fetch_failure_is_reported_failed_not_updated(self) -> None:
        """A failed per-symbol fetch result should increment failed, not updated."""

        class FakeDatabase:
            def __init__(self, path: str) -> None:
                self.path = path

            def close(self) -> None:
                pass

        class FakeFetcher:
            def __init__(self, db: FakeDatabase) -> None:
                self.db = db

            def run(self, symbols: list[str], days: int, market: str | None = None) -> object:
                self.symbols = symbols
                self.days = days
                self.market = market
                return SimpleNamespace(
                    total=1,
                    succeeded=0,
                    failed=1,
                    failures=[{"symbol": symbols[0], "error": "akshare timeout"}],
                )

        with patch.object(server, "Database", FakeDatabase), patch.object(
            server, "KlineFetcher", FakeFetcher
        ), patch.object(
            server,
            "_resolve_stock_list",
            return_value=[{"symbol": "600519", "name": "贵州茅台"}],
        ), patch.object(
            server,
            "_check_kline_coverage",
            return_value={"existing_days": 0, "first_date": None, "last_date": None},
        ):
            result = server._execute_data_update("portfolio", days=30, force=True)

        self.assertTrue(result["success"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["details"][0]["status"], "failed")
        self.assertEqual(result["details"][0]["error"], "akshare timeout")


if __name__ == "__main__":
    unittest.main()
