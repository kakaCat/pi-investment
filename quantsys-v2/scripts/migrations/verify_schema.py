#!/usr/bin/env python3
"""
Verify strategy_configs table structure after migration

Usage:
    python3 scripts/migrations/verify_schema.py
"""

import sys
from pathlib import Path

# Add project root to path

import psycopg2
from psycopg2.extras import RealDictCursor
from infrastructure.persistence.database.engine import _resolve_db_dsn


def verify_schema():
    """Verify the strategy_configs table has all required fields"""

    # Resolve database connection
    dsn = _resolve_db_dsn()
    if not dsn:
        print("❌ Database configuration not found!")
        return False

    try:
        conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        cursor = conn.cursor()

        print(f"🔗 Connected to: {dsn.split('@')[-1] if '@' in dsn else dsn}")
        print(f"\n{'='*70}")

        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'quant'
                AND table_name = 'strategy_configs'
            )
        """)
        table_exists = cursor.fetchone()[0]

        if not table_exists:
            print("❌ Table quant.strategy_configs does not exist!")
            return False

        print("✅ Table quant.strategy_configs exists\n")

        # Get all columns
        cursor.execute("""
            SELECT
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'quant'
            AND table_name = 'strategy_configs'
            ORDER BY ordinal_position
        """)

        columns = cursor.fetchall()

        # Expected new columns from migration
        expected_new_columns = {
            'code_content': 'text',
            'code_type': 'character varying',
            'parsed_params': 'jsonb',
            'risk_config': 'jsonb',
            'metadata': 'jsonb',
            'validation_status': 'character varying',
            'validation_errors': 'text',
            'last_executed_at': 'timestamp without time zone'
        }

        print(f"📊 Table Structure ({len(columns)} columns):\n")
        print(f"{'Column Name':<30} {'Data Type':<25} {'Nullable':<10} {'Status'}")
        print(f"{'-'*30} {'-'*25} {'-'*10} {'-'*10}")

        found_new_columns = {}
        for col in columns:
            col_name = col['column_name']
            data_type = col['data_type']
            nullable = 'YES' if col['is_nullable'] == 'YES' else 'NO'

            # Check if this is a new column from migration
            status = ""
            if col_name in expected_new_columns:
                if data_type == expected_new_columns[col_name]:
                    status = "✅ NEW"
                    found_new_columns[col_name] = True
                else:
                    status = f"⚠️  TYPE MISMATCH"

            print(f"{col_name:<30} {data_type:<25} {nullable:<10} {status}")

        # Check for missing columns
        missing_columns = set(expected_new_columns.keys()) - set(found_new_columns.keys())

        print(f"\n{'='*70}")

        if missing_columns:
            print(f"\n⚠️  Missing columns ({len(missing_columns)}):")
            for col in missing_columns:
                print(f"  ❌ {col}")
            print("\n💡 Run the migration to add these columns:")
            print("   python3 scripts/migrations/run_migration.py 001_add_strategy_code_fields.sql")
        else:
            print(f"\n✅ All migration columns present ({len(expected_new_columns)})")

        # Check indexes
        cursor.execute("""
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'quant'
            AND tablename = 'strategy_configs'
            ORDER BY indexname
        """)

        indexes = cursor.fetchall()

        print(f"\n📇 Indexes ({len(indexes)}):\n")

        expected_indexes = ['idx_strategy_code_type', 'idx_strategy_validation_status']
        found_indexes = []

        for idx in indexes:
            idx_name = idx['indexname']
            status = ""
            if idx_name in expected_indexes:
                status = "✅ NEW"
                found_indexes.append(idx_name)

            print(f"  {idx_name:<40} {status}")

        missing_indexes = set(expected_indexes) - set(found_indexes)
        if missing_indexes:
            print(f"\n⚠️  Missing indexes ({len(missing_indexes)}):")
            for idx in missing_indexes:
                print(f"  ❌ {idx}")

        cursor.close()
        conn.close()

        print(f"\n{'='*70}")

        if not missing_columns and not missing_indexes:
            print("✅ Schema verification passed! Migration is complete.")
            return True
        else:
            print("⚠️  Schema verification incomplete. Migration may be needed.")
            return False

    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = verify_schema()
    sys.exit(0 if success else 1)
