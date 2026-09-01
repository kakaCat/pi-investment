"""
Pytest configuration for quantsys-v2 test suite.

This file automatically loads test environment variables from .env.test
before running any tests.

DATABASE SEPARATION:
- Test database: quant_test (configured in .env.test)
- Production database: quant_investment (configured in .env)
- pytest automatically uses test database via this conftest.py
- All other scenarios (API, scripts) use production database
"""
import os
import sys
from pathlib import Path

import pytest

collect_ignore = []
try:
    import empyrical
except ImportError:
    collect_ignore.append("tests/services/test_risk_metrics_service.py")


def pytest_configure(config):
    """Load test environment variables before running tests."""
    # Get the project root directory
    project_root = Path(__file__).parent

    # Add project root to sys.path so imports work
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    env_test_file = project_root / ".env.test"

    # Load .env.test if it exists
    if env_test_file.exists():
        with open(env_test_file) as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Parse KEY=VALUE
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # Only set if not already set (allow override from shell)
                    if key not in os.environ:
                        os.environ[key] = value

    # 强制验证测试数据库配置
    pgdatabase = os.environ.get("PGDATABASE", "")
    if not pgdatabase:
        print("\n" + "="*70)
        print("ERROR: PGDATABASE environment variable is not set!")
        print("Please ensure .env.test exists and contains PGDATABASE=quant_test")
        print("="*70 + "\n")
        sys.exit(1)

    if not pgdatabase.endswith("_test"):
        print("\n" + "="*70)
        print("ERROR: Test database validation failed!")
        print(f"Current PGDATABASE: {pgdatabase}")
        print("Test database name must end with '_test' (e.g., 'quant_test')")
        print("This safety check prevents tests from running against production data.")
        print("Please check your .env.test configuration.")
        print("="*70 + "\n")
        sys.exit(1)

    print(f"✓ Test database validated: {pgdatabase}")


@pytest.fixture(scope="session")
def db_connection():
    """Provide a database connection for tests that need it."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from infrastructure.persistence.database.engine import _resolve_db_dsn

    dsn = _resolve_db_dsn()
    if not dsn:
        pytest.skip("No database configuration found")

    conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)

    # Ensure required tables exist for tests
    _ensure_test_tables(conn)

    yield conn
    conn.close()


def _ensure_test_tables(conn):
    """Ensure required tables exist in test database."""
    cursor = conn.cursor()

    # Create stock_fundamentals table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quant.stock_fundamentals (
            symbol TEXT PRIMARY KEY,
            pe_ratio DOUBLE PRECISION,
            roe DOUBLE PRECISION,
            gross_margin DOUBLE PRECISION,
            debt_ratio DOUBLE PRECISION,
            update_time DATE NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    # Create index_constituents table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quant.index_constituents (
            index_code TEXT NOT NULL,
            constituent_symbol TEXT NOT NULL,
            weight DOUBLE PRECISION DEFAULT 0,
            update_time TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (index_code, constituent_symbol)
        )
    """)

    # Create stop_loss_rules table if not exists (mirrors production schema)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quant.stop_loss_rules (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('fixed_price', 'fixed_percent', 'trailing_stop')),
            stop_loss_percent REAL,
            trailing_percent REAL,
            atr_multiplier REAL,
            status TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'inactive', 'triggered')),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cursor.close()


@pytest.fixture(scope="function")
def clean_db(db_connection):
    """Clean up test data after each test."""
    yield
    # Cleanup logic can be added here if needed
    # For now, tests are responsible for their own cleanup
