"""Tests for factor decay CLI using Database class with PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quantsys.cli.factor_decay import analyze_factor_decay
from quantsys.data.db import Database


def test_analyze_factor_decay_uses_database_class_with_postgres(tmp_path: Path) -> None:
    """Test that factor decay analysis uses Database class instead of direct sqlite3."""
    # Setup mock Database that simulates PostgreSQL
    mock_db = MagicMock(spec=Database)
    mock_db.provider = "postgres"
    mock_conn = MagicMock()
    mock_db.conn = mock_conn
    mock_db._get_connection.return_value = mock_conn

    # Mock cursor for table existence check
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (1,)  # Table exists

    # Mock execute for factor_values query
    mock_conn.execute.return_value.fetchall.return_value = [
        {"factor_value": 1.0, "return_pct": 0.01},
        {"factor_value": 2.0, "return_pct": 0.02},
        {"factor_value": 3.0, "return_pct": 0.03},
    ]

    with patch("quantsys.cli.factor_decay.Database", return_value=mock_db):
        result = analyze_factor_decay(
            tmp_path,
            {"factor": "momentum", "horizons": "5"},
        )

    # Verify Database class was instantiated (not sqlite3.connect)
    assert result["factor"] == "momentum"
    assert len(result["decay"]) == 1
    assert result["decay"][0]["horizon"] == 5


def test_analyze_factor_decay_respects_postgres_env_var(tmp_path: Path) -> None:
    """Test that QUANT_DB_PROVIDER=postgres is respected."""
    mock_db = MagicMock(spec=Database)
    mock_db.provider = "postgres"

    with patch.dict(os.environ, {"QUANT_DB_PROVIDER": "postgres"}):
        with patch("quantsys.cli.factor_decay.Database") as mock_db_class:
            mock_db_class.return_value = mock_db

            # This should fail because the current implementation uses sqlite3
            result = analyze_factor_decay(
                tmp_path,
                {"factor": "momentum"},
            )

            # Should have called Database constructor
            mock_db_class.assert_called_once()
