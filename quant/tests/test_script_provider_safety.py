"""Provider-safety checks for ad-hoc quant scripts."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_ml_retrain_smoke_script_does_not_open_sqlite_directly() -> None:
    """The ML retrain smoke script should use the Database abstraction."""
    source = (PROJECT_ROOT / "quant" / "scripts" / "test_ml_retrain.py").read_text()

    assert "import sqlite3" not in source
    assert "sqlite3.connect" not in source
    assert "Database(" in source


def test_strategy_integration_loader_does_not_open_sqlite_directly() -> None:
    """The strategy integration loader should use provider-aware Database reads."""
    source = (PROJECT_ROOT / "quant" / "quantsys" / "strategies" / "test_integration.py").read_text()

    assert "import sqlite3" not in source
    assert "sqlite3.connect" not in source
    assert "get_backtest_klines" in source


def test_legacy_sqlite_migration_blocks_postgres_mode() -> None:
    """The legacy SQLite migration script should not run as a PostgreSQL importer."""
    source = (PROJECT_ROOT / "quant" / "scripts" / "migrate_db_data.py").read_text()

    assert "SQLite-only" in source
    assert "QUANT_DB_PROVIDER" in source
    assert "migrate-sqlite-to-postgres.py" in source


def test_confidence_calibrator_does_not_open_sqlite_directly() -> None:
    """Confidence calibration should read through the provider-aware Database layer."""
    source = (PROJECT_ROOT / "quant" / "quantsys" / "ml" / "confidence_calibrator.py").read_text()

    assert "import sqlite3" not in source
    assert "sqlite3.connect" not in source
    assert "Database(" in source
