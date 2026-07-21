# Database Migrations

This directory contains SQL migration scripts for the quantsys-v2 database schema.

## 📁 Directory Structure

```
scripts/migrations/
├── README.md                           # This file
├── MIGRATION_SUMMARY.md                # Detailed execution summary
├── 001_add_strategy_code_fields.sql    # Migration: Strategy code execution fields
├── run_migration.py                    # Python migration runner
└── quick_migrate.sh                    # Bash quick migration script
```

## 🚀 Quick Start

### Method 1: Using the quick migration script (Easiest)

```bash
# Migrate test database
./scripts/migrations/quick_migrate.sh quant_test

# Migrate production database
./scripts/migrations/quick_migrate.sh quant
```

### Method 2: Using Python runner

```bash
# Set database name
export PGDATABASE=quant_test

# Run migration
python3 scripts/migrations/run_migration.py 001_add_strategy_code_fields.sql
```

### Method 3: Direct SQL execution

```bash
psql -h localhost -U mac -d quant_test -f scripts/migrations/001_add_strategy_code_fields.sql
```

## 📋 Available Migrations

### 001_add_strategy_code_fields.sql

**Purpose**: Extend `quant.strategy_configs` table to support user-defined strategy code execution

**Changes**:
- Adds 8 new columns for code storage, validation, and metadata
- Creates 2 indexes for performance optimization
- Adds column comments for documentation

**Reference**: `docs/superpowers/specs/strategy-code-execution-engine.md` (Chapter 5)

**Status**: ✅ Created, ⏳ Pending execution

## 🔧 Database Configuration

The migration scripts support multiple configuration methods:

### Environment Variables (Priority Order)

1. **Full DSN** (Recommended for production):
   ```bash
   export QUANT_DATABASE_URL="postgresql://user:pass@host:port/dbname"
   # or
   export DATABASE_URL="postgresql://user:pass@host:port/dbname"
   # or
   export POSTGRES_DSN="postgresql://user:pass@host:port/dbname"
   ```

2. **Individual PostgreSQL variables** (Recommended for development):
   ```bash
   export PGHOST=localhost
   export PGPORT=5432
   export PGDATABASE=quant_test
   export PGUSER=mac
   export PGPASSWORD=
   ```

### Using .env files

```bash
# Load from .env.test
export $(cat .env.test | grep -v '^#' | xargs)
python3 scripts/migrations/run_migration.py 001_add_strategy_code_fields.sql
```

## ✅ Migration Features

### Safety Features
- ✅ Idempotent (safe to run multiple times)
- ✅ Uses `IF NOT EXISTS` clauses
- ✅ Transaction-wrapped execution
- ✅ Automatic rollback on error
- ✅ Post-migration verification

### Verification
After execution, the runner automatically verifies:
- All columns are created
- All indexes are created
- Column comments are added

### Output Example
```
📄 Migration file: 001_add_strategy_code_fields.sql
🔗 Database DSN: localhost:5432/quant_test

============================================================
✅ Database connection established

🚀 Executing migration...

✅ Migration executed successfully!

📊 Verified new columns (8):
  ✓ code_content              text                 NULL
  ✓ code_type                 character varying    NULL
  ✓ last_executed_at          timestamp            NULL
  ✓ metadata                  jsonb                NULL
  ✓ parsed_params             jsonb                NULL
  ✓ risk_config               jsonb                NULL
  ✓ validation_errors         text                 NULL
  ✓ validation_status         character varying    NULL

📇 Verified indexes (2):
  ✓ idx_strategy_code_type
  ✓ idx_strategy_validation_status

============================================================
✅ Migration completed successfully!
```

## 🔍 Troubleshooting

### Error: "Database configuration not found"
**Solution**: Set one of the database environment variables listed above.

### Error: "Migration file not found"
**Solution**: Ensure you're running the command from the project root directory.

### Error: "Permission denied"
**Solution**: Make scripts executable:
```bash
chmod +x scripts/migrations/run_migration.py
chmod +x scripts/migrations/quick_migrate.sh
```

### Error: "relation does not exist"
**Solution**: Ensure the `quant.strategy_configs` table exists before running the migration.

## 📖 Migration Naming Convention

Migrations follow the pattern: `NNN_descriptive_name.sql`

- `NNN`: Three-digit sequence number (001, 002, 003, ...)
- `descriptive_name`: Snake_case description of the change
- `.sql`: SQL file extension

## 🎯 Best Practices

1. **Always test migrations** on a test database first
2. **Backup production data** before running migrations
3. **Review SQL content** before execution
4. **Verify results** after migration
5. **Document changes** in migration comments
6. **Use transactions** for atomic changes
7. **Make migrations idempotent** (safe to re-run)

## 📚 Additional Resources

- **Design Document**: `docs/superpowers/specs/strategy-code-execution-engine.md`
- **Migration Summary**: `scripts/migrations/MIGRATION_SUMMARY.md`
- **Database Schema**: `quant.strategy_configs` table

## 🤝 Contributing

When adding new migrations:

1. Create a new SQL file with the next sequence number
2. Include descriptive comments in the SQL
3. Use `IF NOT EXISTS` for idempotency
4. Add verification queries at the end
5. Update this README with migration details
6. Test on development database first

## 📝 Notes

- Migrations are executed in numerical order
- Each migration should be atomic and reversible
- Always include rollback instructions in comments
- Document breaking changes clearly
