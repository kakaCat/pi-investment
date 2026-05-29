"""Tests for Python API PostgreSQL read-provider compatibility."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = PROJECT_ROOT / "quant"
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

from api import server


class PostgresProviderTests(unittest.TestCase):
    def test_default_provider_is_postgres(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(server.get_db_provider(), "postgres")

    def test_sqlite_provider_is_rejected_explicitly(self) -> None:
        with patch.dict(os.environ, {"QUANT_DB_PROVIDER": "sqlite"}):
            self.assertEqual(server.get_db_provider(), "postgres")

    def test_postgres_connection_rewrites_sqlite_placeholders_and_tables(self) -> None:
        calls: list[tuple[str, object | None]] = []

        class FakeCursor:
            def execute(self, sql: str, params: object | None = None) -> None:
                calls.append((sql, params))

            def fetchall(self) -> list[tuple[str]]:
                return [("ok",)]

        class FakeConnection:
            def cursor(self) -> FakeCursor:
                return FakeCursor()

            def close(self) -> None:
                pass

        def fake_connect(**kwargs: object) -> FakeConnection:
            calls.append(("connect", kwargs))
            return FakeConnection()

        with patch.dict(os.environ, {"QUANT_DB_PROVIDER": "postgres", "PGDATABASE": "quant_investment"}), patch(
            "psycopg2.connect", side_effect=fake_connect
        ):
            conn = server.get_db()
            cursor = conn.execute(
                "SELECT date, close FROM daily_klines WHERE symbol = ? ORDER BY date DESC LIMIT 1",
                ("000001",),
            )

        self.assertEqual(cursor.fetchall(), [("ok",)])
        self.assertEqual(calls[0][0], "connect")
        self.assertEqual(
            calls[1],
            (
                "SELECT date, close FROM quant_compat.daily_klines WHERE symbol = %s ORDER BY date DESC LIMIT 1",
                ("000001",),
            ),
        )


if __name__ == "__main__":
    unittest.main()
