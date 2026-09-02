#!/usr/bin/env python3
"""
Migration runner for add_strategy_active_field.sql

Executes the SQL migration that adds an `is_active` column to
`quant.strategy_configs`. The migration and this runner are idempotent:
running them multiple times is safe.

Usage:
    python3 scripts/migrations/run_migration.py

Environment:
    Set any of the following to configure the database connection:
      - QUANT_DATABASE_URL
      - DATABASE_URL
      - POSTGRES_DSN
      - PGDATABASE (with optional PGHOST, PGPORT, PGUSER, PGPASSWORD)
"""

import sys
import os
from pathlib import Path

# Resolve project paths
SCRIPT_DIR = Path(__file__).resolve().parent
MIGRATIONS_DIR = SCRIPT_DIR

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ModuleNotFoundError as e:  # pragma: no cover
    print("❌ psycopg2 is not installed.")
    print(f"   Details: {e}")
    print("\nPlease activate the quantsys-v2 virtual environment:")
    print("   cd quantsys-v2 && source activate-py313.sh")
    sys.exit(1)


def _resolve_db_dsn() -> str | None:
    """Resolve a PostgreSQL connection string from environment variables."""
    for env_var in ("QUANT_DATABASE_URL", "DATABASE_URL", "POSTGRES_DSN"):
        dsn = os.environ.get(env_var)
        if dsn:
            return dsn

    dbname = os.environ.get("PGDATABASE")
    if not dbname:
        return None

    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    user = os.environ.get("PGUSER", "")
    password = os.environ.get("PGPASSWORD", "")

    dsn = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    return dsn


def _read_sql_file(filename: str) -> str:
    """Read the migration SQL from disk."""
    sql_path = MIGRATIONS_DIR / filename
    if not sql_path.exists():
        raise FileNotFoundError(f"Migration file not found: {sql_path}")
    return sql_path.read_text(encoding="utf-8")


def _is_already_applied(cursor) -> bool:
    """Check whether the is_active column already exists on quant.strategy_configs."""
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'quant'
          AND table_name = 'strategy_configs'
          AND column_name = 'is_active'
        """
    )
    return cursor.fetchone() is not None


def run_migration(filename: str = "add_strategy_active_field.sql") -> bool:
    """Execute the migration and verify the result."""
    dsn = _resolve_db_dsn()
    if not dsn:
        print("❌ Database configuration not found!")
        print("\nPlease set one of the following environment variables:")
        print("  - QUANT_DATABASE_URL")
        print("  - DATABASE_URL")
        print("  - POSTGRES_DSN")
        print("  - PGDATABASE (with optional PGHOST, PGPORT, PGUSER, PGPASSWORD)")
        return False

    sql_content = _read_sql_file(filename)

    print(f"📄 Migration file: {filename}")
    print(f"🔗 Database DSN: {dsn.split('@')[-1] if '@' in dsn else dsn}")
    print(f"\n{'=' * 60}")

    conn = None
    try:
        conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        cursor = conn.cursor()
        print("✅ Database connection established")

        if _is_already_applied(cursor):
            print("ℹ️  Migration already applied (is_active column exists).")
            print("   Re-running to ensure idempotency...")

        print("\n🚀 Executing migration...\n")
        cursor.execute(sql_content)
        conn.commit()
        print("✅ Migration SQL executed successfully!")

        # Verify column
        cursor.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'quant'
              AND table_name = 'strategy_configs'
              AND column_name = 'is_active'
            """
        )
        column = cursor.fetchone()
        if column:
            print("\n📊 Verified column:")
            print(
                f"  ✓ {column['column_name']:<20} "
                f"{column['data_type']:<15} "
                f"{'NULL' if column['is_nullable'] == 'YES' else 'NOT NULL':<10} "
                f"default={column['column_default']}"
            )
        else:
            print("\n⚠️  Warning: Could not verify is_active column")

        # Verify index
        cursor.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'quant'
              AND tablename = 'strategy_configs'
              AND indexname = 'idx_strategy_configs_is_active'
            """
        )
        index = cursor.fetchone()
        if index:
            print("\n📇 Verified index:")
            print(f"  ✓ {index['indexname']}")
        else:
            print("\n⚠️  Warning: Could not verify is_active index")

        cursor.close()
        print(f"\n{'=' * 60}")
        print("✅ Migration completed successfully!")
        return True

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        print(f"\n❌ Database error: {e}")
        print(f"\nError details:")
        print(f"  Code: {e.pgcode}")
        print(f"  Message: {e.pgerror}")
        return False
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"\n❌ Unexpected error: {e}")
        return False
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    migration_file = sys.argv[1] if len(sys.argv) > 1 else "add_strategy_active_field.sql"
    success = run_migration(migration_file)
    sys.exit(0 if success else 1)
