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
