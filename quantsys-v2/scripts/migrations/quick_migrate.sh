#!/bin/bash
# Quick migration execution script
# Usage: ./scripts/migrations/quick_migrate.sh [database_name]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Default to quant_test if no argument provided
DB_NAME="${1:-quant_test}"

echo "=================================================="
echo "  Strategy Code Fields Migration"
echo "=================================================="
echo ""
echo "Target Database: $DB_NAME"
echo ""

# Set database environment variable
export PGDATABASE="$DB_NAME"
export PGHOST="${PGHOST:-127.0.0.1}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-mac}"

# Run migration
cd "$PROJECT_ROOT"
python3 scripts/migrations/run_migration.py 001_add_strategy_code_fields.sql

echo ""
echo "=================================================="
echo "  Migration Complete!"
echo "=================================================="
