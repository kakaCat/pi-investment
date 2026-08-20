#!/usr/bin/env python3
"""
Migration runner script for quantsys-v2

Usage:
    python3 scripts/migrations/run_migration.py 001_add_strategy_code_fields.sql
"""

import sys
import os
from pathlib import Path

# Add project root to path

import psycopg2
from psycopg2.extras import RealDictCursor
from infrastructure.persistence.database.engine import _resolve_db_dsn


def run_migration(migration_file: str):
    """Execute a SQL migration file"""

    # Resolve database connection
    dsn = _resolve_db_dsn()
    if not dsn:
        print("❌ Database configuration not found!")
        print("\nPlease set one of the following environment variables:")
        print("  - QUANT_DATABASE_URL")
        print("  - DATABASE_URL")
        print("  - POSTGRES_DSN")
        print("  - PGDATABASE (with optional PGHOST, PGPORT, PGUSER, PGPASSWORD)")
        return False

    # Read migration file
    migration_path = Path(__file__).parent / migration_file
    if not migration_path.exists():
        print(f"❌ Migration file not found: {migration_path}")
        return False

    with open(migration_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    print(f"📄 Migration file: {migration_file}")
    print(f"🔗 Database DSN: {dsn.split('@')[-1] if '@' in dsn else dsn}")
    print(f"\n{'='*60}")

    # Execute migration
    try:
        conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        print("✅ Database connection established")
        print(f"\n🚀 Executing migration...\n")

        # Execute the SQL
        cursor.execute(sql_content)
        conn.commit()

        print("✅ Migration executed successfully!")

        # Verify the changes
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'quant'
            AND table_name = 'strategy_configs'
            AND column_name IN (
                'code_content', 'code_type', 'parsed_params',
                'risk_config', 'metadata', 'validation_status',
                'validation_errors', 'last_executed_at'
            )
            ORDER BY column_name
        """)

        columns = cursor.fetchall()

        if columns:
            print(f"\n📊 Verified new columns ({len(columns)}):")
            for col in columns:
                print(f"  ✓ {col['column_name']:<25} {col['data_type']:<20} {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")
        else:
            print("\n⚠️  Warning: Could not verify new columns")

        # Check indexes
        cursor.execute("""
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'quant'
            AND tablename = 'strategy_configs'
            AND indexname IN ('idx_strategy_code_type', 'idx_strategy_validation_status')
        """)

        indexes = cursor.fetchall()
        if indexes:
            print(f"\n📇 Verified indexes ({len(indexes)}):")
            for idx in indexes:
                print(f"  ✓ {idx['indexname']}")

        cursor.close()
        conn.close()

        print(f"\n{'='*60}")
        print("✅ Migration completed successfully!")
        return True

    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}")
        print(f"\nError details:")
        print(f"  Code: {e.pgcode}")
        print(f"  Message: {e.pgerror}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 run_migration.py <migration_file.sql>")
        print("\nAvailable migrations:")
        migrations_dir = Path(__file__).parent
        for sql_file in sorted(migrations_dir.glob("*.sql")):
            print(f"  - {sql_file.name}")
        sys.exit(1)

    migration_file = sys.argv[1]
    success = run_migration(migration_file)
    sys.exit(0 if success else 1)
