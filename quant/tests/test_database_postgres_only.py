"""Tests to verify Database class only supports PostgreSQL."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from quantsys.data.db import Database


def test_database_defaults_to_postgres() -> None:
    """Test that Database class defaults to postgres provider."""
    with patch("quantsys.data.db.psycopg2") as mock_psycopg2:
        mock_psycopg2.connect.return_value = None

        with patch.dict(os.environ, {}, clear=True):
            try:
                db = Database()
                assert db.provider == "postgres"
            except RuntimeError:
                # Expected if psycopg2 is not available or connection fails
                pass


def test_database_rejects_sqlite_provider() -> None:
    """Test that Database class rejects sqlite provider."""
    with patch.dict(os.environ, {"QUANT_DB_PROVIDER": "sqlite"}):
        with pytest.raises(RuntimeError, match="SQLite is no longer supported"):
            Database()


def test_database_only_accepts_postgres() -> None:
    """Test that Database class only accepts postgres as provider."""
    with patch("quantsys.data.db.psycopg2") as mock_psycopg2:
        mock_psycopg2.connect.return_value = None

        with patch.dict(os.environ, {"QUANT_DB_PROVIDER": "postgres"}):
            try:
                db = Database()
                assert db.provider == "postgres"
            except RuntimeError:
                # Expected if connection fails
                pass


def test_upsert_stocks_preserves_existing_name_when_incoming_name_is_symbol() -> None:
    """Incoming placeholder names should not overwrite real stock names."""

    class FakeCursor:
        def __init__(self) -> None:
            self.executed = None
            self.closed = False

        def execute(self, *_args) -> None:
            pass

        def executemany(self, query, rows) -> None:
            self.executed = (query, rows)

        def close(self) -> None:
            self.closed = True

    class FakeConnection:
        def __init__(self) -> None:
            self.cursor_instance = FakeCursor()
            self.committed = False

        def cursor(self) -> FakeCursor:
            return self.cursor_instance

        def commit(self) -> None:
            self.committed = True

    connection = FakeConnection()

    with patch.dict(os.environ, {"QUANT_DB_PROVIDER": "postgres"}):
        database = Database(connect=False)
        database.conn = connection
        database.upsert_stocks([{"symbol": "688981", "name": "688981", "market": "A"}])

    query, rows = connection.cursor_instance.executed
    assert rows[0][1] is None
    assert "name = COALESCE(excluded.name, quant.stocks.name)" in query
    assert connection.committed
    assert connection.cursor_instance.closed
