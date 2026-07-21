"""Test async connection pool pytest safety check"""
import pytest
import sys
import os
from infrastructure.persistence.database.async_base_repository import AsyncConnectionPool, TEST_DB_SUFFIX


def test_async_pool_rejects_production_db_in_pytest():
    """Should raise RuntimeError when pytest detected with production database"""
    # pytest is already in sys.modules since we're running under pytest
    assert "pytest" in sys.modules

    production_dsn = "postgresql://user:pass@localhost:5432/production_db"

    with pytest.raises(RuntimeError) as exc_info:
        AsyncConnectionPool(dsn=production_dsn)

    assert "Security check failed" in str(exc_info.value)
    assert "production_db" in str(exc_info.value)
    assert TEST_DB_SUFFIX in str(exc_info.value)


def test_async_pool_accepts_test_db_in_pytest():
    """Should succeed when pytest detected with test database"""
    assert "pytest" in sys.modules

    test_dsn = f"postgresql://user:pass@localhost:5432/quantsys{TEST_DB_SUFFIX}"

    # Should not raise
    pool = AsyncConnectionPool(dsn=test_dsn)
    assert pool.dsn == test_dsn


def test_async_pool_prevents_bypass_via_pgdatabase_fallback(monkeypatch):
    """
    CRITICAL: Should detect production DB even when DSN parsing fails

    Attack scenario:
    - Set DATABASE_URL to production DB
    - Set PGDATABASE to fake test name
    - Without fallback validation, this bypasses the safety check
    """
    assert "pytest" in sys.modules

    # Simulate the bypass attempt
    monkeypatch.setenv("PGDATABASE", "production_db")

    # DSN that might fail parsing or be malformed
    malformed_dsn = "postgresql://localhost/"  # No database name in DSN

    with pytest.raises(RuntimeError) as exc_info:
        AsyncConnectionPool(dsn=malformed_dsn)

    assert "Security check failed" in str(exc_info.value)
    assert "production_db" in str(exc_info.value)


def test_async_pool_validates_pgdatabase_when_dsn_has_no_db_name(monkeypatch):
    """Should fallback to PGDATABASE validation when DSN has no database name"""
    assert "pytest" in sys.modules

    monkeypatch.setenv("PGDATABASE", f"quantsys{TEST_DB_SUFFIX}")

    # DSN without database name
    dsn_no_db = "postgresql://localhost:5432/"

    # Should not raise because PGDATABASE ends with _test
    pool = AsyncConnectionPool(dsn=dsn_no_db)
    assert pool.dsn == dsn_no_db


def test_async_pool_regex_extracts_db_name_correctly():
    """Should correctly extract database name from various DSN formats using regex"""
    assert "pytest" in sys.modules

    # Test various valid formats with _test suffix
    test_cases = [
        f"postgresql://localhost/mydb{TEST_DB_SUFFIX}",
        f"postgresql://user:pass@localhost:5432/mydb{TEST_DB_SUFFIX}",
        f"postgresql://localhost/mydb{TEST_DB_SUFFIX}?sslmode=require",
        f"postgresql://user@host:5432/mydb{TEST_DB_SUFFIX}?connect_timeout=10",
    ]

    for dsn in test_cases:
        # Should not raise
        pool = AsyncConnectionPool(dsn=dsn)
        assert pool.dsn == dsn


def test_async_pool_rejects_empty_db_name_bypass(monkeypatch):
    """
    CRITICAL: Should reject empty database name to prevent default database bypass

    Attack scenario:
    - Provide DSN without database name: postgresql://localhost/
    - No PGDATABASE set
    - Without empty check, connects to default database (bypass!)
    """
    assert "pytest" in sys.modules

    # Ensure PGDATABASE is not set
    monkeypatch.delenv("PGDATABASE", raising=False)

    # DSN without database name
    empty_dsn = "postgresql://localhost:5432/"

    with pytest.raises(RuntimeError) as exc_info:
        AsyncConnectionPool(dsn=empty_dsn)

    assert "Cannot determine database name" in str(exc_info.value)
    assert "PGDATABASE is not set" in str(exc_info.value)
