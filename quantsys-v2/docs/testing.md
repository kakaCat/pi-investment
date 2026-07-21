# Testing Guide for quantsys-v2

## Overview

This document describes how to set up and run the test suite for quantsys-v2.

## Test Infrastructure

- **Test Framework**: pytest
- **Coverage Tool**: pytest-cov
- **Mocking**: pytest-mock
- **Total Tests**: 992 tests (957 passing, 24 skipped, 11 business logic failures)

## Database Setup

### Prerequisites

1. PostgreSQL installed and running
2. A dedicated test database (recommended: `quant_test`)

### Create Test Database

```bash
# Connect to PostgreSQL
psql -h localhost -U <your_username> -d postgres

# Create test database
CREATE DATABASE quant_test;

# Exit psql
\q
```

### Initialize Test Database Schema

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2

# Create quant schema
psql -h localhost -U <your_username> -d quant_test -c "CREATE SCHEMA IF NOT EXISTS quant;"

# Create base tables
psql -h localhost -U <your_username> -d quant_test -c "
CREATE TABLE IF NOT EXISTS quant.stocks (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT NOT NULL,
    sector TEXT,
    industry TEXT,
    list_date DATE,
    is_active BOOLEAN DEFAULT true,
    is_st BOOLEAN DEFAULT false,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quant.daily_klines (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume BIGINT NOT NULL,
    amount DOUBLE PRECISION,
    turnover_rate DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(symbol, trade_date)
);
"

# Create all other tables
psql -h localhost -U <your_username> -d quant_test -f scripts/create_missing_tables.sql
psql -h localhost -U <your_username> -d quant_test -f scripts/create_scheduler_tables.sql

# Create additional required tables
psql -h localhost -U <your_username> -d quant_test -c "
CREATE TABLE IF NOT EXISTS quant.factors (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    factor_name TEXT NOT NULL,
    factor_value DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(symbol, trade_date, factor_name)
);

CREATE TABLE IF NOT EXISTS quant.factor_values (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    trade_date DATE NOT NULL,
    factor_date DATE,
    factor_name TEXT NOT NULL,
    factor_value DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(symbol, trade_date, factor_name)
);

CREATE TABLE IF NOT EXISTS quant.signals (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    signal_date DATE NOT NULL,
    signal_type TEXT NOT NULL,
    action TEXT,
    signal_strength DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    price DOUBLE PRECISION,
    reason TEXT,
    strategy_id TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quant.trading_signals (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    signal_date DATE NOT NULL,
    signal_type TEXT NOT NULL,
    action TEXT,
    signal_strength DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    price DOUBLE PRECISION,
    reason TEXT,
    strategy_id TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quant.signal_executions (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT,
    symbol TEXT NOT NULL,
    execution_date DATE NOT NULL,
    status TEXT NOT NULL,
    execution_price DOUBLE PRECISION,
    quantity INTEGER,
    commission DOUBLE PRECISION DEFAULT 0,
    pnl DOUBLE PRECISION,
    close_date DATE,
    close_price DOUBLE PRECISION,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
"
```

## Environment Configuration

### 1. Create `.env.test` File

The test suite automatically loads environment variables from `.env.test`:

```bash
# .env.test
PGHOST=localhost
PGPORT=5432
PGDATABASE=quant_test
PGUSER=<your_username>
PGPASSWORD=<your_password_if_needed>

PYTHONDONTWRITEBYTECODE=1
```

**Important**: Replace `<your_username>` with your actual PostgreSQL username (e.g., `mac`, `postgres`).

### 2. Verify Configuration

The `conftest.py` file automatically loads `.env.test` before running tests. You can verify the configuration:

```bash
# Check if environment variables are loaded
python3 -c "
import os
from pathlib import Path

env_file = Path('.env.test')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.strip().split('=', 1)
                print(f'{key}={value}')
"
```

## Running Tests

### Run All Tests

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_scheduler.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_scheduler.py::TestSchedulerTaskCRUD -v
```

### Run Specific Test

```bash
pytest tests/test_scheduler.py::TestSchedulerTaskCRUD::test_add_and_get_task -v
```

### Run with Coverage Report

```bash
pytest tests/ -v --cov=. --cov-report=html
# Open htmlcov/index.html in browser to view coverage
```

### Run Only Unit Tests

```bash
pytest tests/ -v -m unit
```

### Run Only Integration Tests

```bash
pytest tests/ -v -m integration
```

### Skip Slow Tests

```bash
pytest tests/ -v -m "not slow"
```

## Test Results Summary

As of 2026-05-21:

- **Total Tests**: 992
- **Passed**: 957 (96.5%)
- **Failed**: 11 (1.1%)
- **Skipped**: 24 (2.4%)
- **Errors**: 0

### Remaining Failures

The 11 remaining failures are business logic issues, not infrastructure problems:

1. **Factor Registry Tests (8 failures)**: Tests expect 50 technical factors but 79 are registered (includes optimized variants with `_opt` suffix)
2. **Position Sizer Tests (3 failures)**: Kelly criterion and fixed percent sizer edge cases

These are test expectation mismatches that need to be updated to reflect the current implementation.

## Troubleshooting

### Database Connection Errors

If you see errors like:
```
RuntimeError: No database URL configured
```

**Solution**: Ensure `.env.test` exists and contains valid database credentials.

### Missing Tables

If you see errors like:
```
psycopg2.errors.UndefinedTable: relation "quant.scheduler_tasks" does not exist
```

**Solution**: Run the table creation scripts as shown in the "Initialize Test Database Schema" section.

### Missing Columns

If you see errors like:
```
psycopg2.errors.UndefinedColumn: column "pnl" does not exist
```

**Solution**: The schema may be incomplete. Refer to the SQL commands in the "Initialize Test Database Schema" section.

### Permission Denied

If you see:
```
FATAL: role "postgres" does not exist
```

**Solution**: Update `PGUSER` in `.env.test` to match your PostgreSQL username (check with `psql -h localhost -U $USER -d postgres -c "\du"`).

## Test Database Maintenance

### Reset Test Database

To start fresh:

```bash
# Drop and recreate
psql -h localhost -U <your_username> -d postgres -c "DROP DATABASE IF EXISTS quant_test;"
psql -h localhost -U <your_username> -d postgres -c "CREATE DATABASE quant_test;"

# Re-run initialization scripts (see "Initialize Test Database Schema" section)
```

### Clean Test Data

Tests should clean up after themselves, but if you need to manually clean:

```bash
psql -h localhost -U <your_username> -d quant_test -c "
TRUNCATE TABLE quant.scheduler_runs CASCADE;
TRUNCATE TABLE quant.scheduler_tasks CASCADE;
TRUNCATE TABLE quant.signal_executions CASCADE;
TRUNCATE TABLE quant.signals CASCADE;
TRUNCATE TABLE quant.trading_signals CASCADE;
TRUNCATE TABLE quant.factors CASCADE;
TRUNCATE TABLE quant.factor_values CASCADE;
"
```

## CI/CD Integration

For continuous integration, set environment variables in your CI configuration:

```yaml
# Example for GitHub Actions
env:
  PGHOST: localhost
  PGPORT: 5432
  PGDATABASE: quant_test
  PGUSER: postgres
  PGPASSWORD: postgres
```

## Best Practices

1. **Always use a dedicated test database** - Never run tests against production data
2. **Keep `.env.test` out of version control** - Add it to `.gitignore`
3. **Run tests before committing** - Ensure your changes don't break existing functionality
4. **Write tests for new features** - Maintain high test coverage
5. **Use fixtures for common setup** - See `conftest.py` for examples

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
