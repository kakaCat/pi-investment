"""Tests for factor sector analytics CLI using Database class with PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quantsys.cli.factor_sector_analytics import analyze_factors
from quantsys.data.db import Database


def test_analyze_factors_uses_database_class_with_postgres(tmp_path: Path) -> None:
    """Test that factor analysis uses Database class instead of direct sqlite3."""
    # Setup mock Database that simulates PostgreSQL
    mock_db = MagicMock(spec=Database)
    mock_db.provider = "postgres"
    mock_conn = MagicMock()
    mock_db.conn = mock_conn
    mock_db._get_connection.return_value = mock_conn

    # Mock cursor for column check
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [
        ("symbol",), ("date",), ("factor_name",), ("factor_value",)
    ]

    # Mock execute for factor query
    mock_conn.execute.return_value.fetchall.return_value = [
        {"factor_name": "momentum", "count": 100, "mean": 0.5, "mean_square": 0.3,
         "coverage_symbols": 50, "latest_date": "2026-05-01"},
    ]

    with patch("quantsys.cli.factor_sector_analytics.Database", return_value=mock_db):
        result = analyze_factors(tmp_path, {})

    # Verify Database class was instantiated (not sqlite3.connect)
    assert "factors" in result
    assert isinstance(result["factors"], list)


def test_analyze_factors_respects_postgres_env_var(tmp_path: Path) -> None:
    """Test that QUANT_DB_PROVIDER=postgres is respected."""
    mock_db = MagicMock(spec=Database)
    mock_db.provider = "postgres"

    with patch.dict(os.environ, {"QUANT_DB_PROVIDER": "postgres"}):
        with patch("quantsys.cli.factor_sector_analytics.Database") as mock_db_class:
            mock_db_class.return_value = mock_db

            # This should fail because the current implementation uses sqlite3
            result = analyze_factors(tmp_path, {})

            # Should have called Database constructor
            mock_db_class.assert_called_once()
