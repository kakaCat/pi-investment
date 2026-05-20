# Quant PostgreSQL Migration Runbook

This folder contains the PostgreSQL schema and SQLite-to-PostgreSQL migration
helper for the internal quant research/signal platform.

## Current Local State

- PostgreSQL database: `quant_investment`
- Source SQLite database: `.pi-invest/stock-db/stocks.db`
- Source SQLite size: about `5.5G` plus a `128M` WAL file
- Last verified full core import: `5,847` stocks, `2,756,661` daily kline rows, `15,837,684` factor rows
- Full core import runtime on this machine: `561.55s`
- Current integrity checks: `0` orphan rows and `0` duplicate PostgreSQL primary keys
- Backup before full import: `.pi-invest/postgres-backups/quant_investment_before_full_20260519_222654.dump`

## Runtime Architecture

- The Python quant API is the database owner. PostgreSQL is the default
  provider; start it with `PGDATABASE=quant_investment` or a
  `QUANT_DATABASE_URL` connection string to read from PostgreSQL.
- The Node/Web API is a BFF/compatibility layer for the frontend. It should call
  the Python API for quant data instead of opening SQLite or PostgreSQL directly.
- The Node/Web API uses `QUANT_PY_API_BASE_URL` to locate the Python API. If unset,
  it defaults to `http://127.0.0.1:5001`.
- SQLite is retained only as the historical migration source. The runtime
  `Database` abstraction is PostgreSQL-only and rejects
  `QUANT_DB_PROVIDER=sqlite`.

Example local startup:

```bash
PGDATABASE=quant_investment PYTHONPATH=quant python quant/api/server.py
QUANT_PY_API_BASE_URL=http://127.0.0.1:5001 npm run api
```

Current migration boundary: the primary Python API, ETL writes, factor reads,
signal generation, ML training reads, strategy backtest scripts, the legacy
`quant_api.py` bridge, confidence calibration, and data-update helpers are
provider-aware and have PostgreSQL smoke coverage. Remaining SQLite SQL is
expected in migration helpers, the Flask API compatibility wrapper, and the
explicitly SQLite-only `quant/scripts/migrate_db_data.py`.

## Create Or Refresh Schema

```bash
createdb quant_investment
psql quant_investment -v ON_ERROR_STOP=1 -f scripts/postgres/create-quant-db.sql
psql quant_investment -f scripts/postgres/verify-quant-db.sql
```

If the database already exists, only run the `psql ... create-quant-db.sql`
command. The schema script uses `IF NOT EXISTS` for tables and indexes.

## Migration Safety Rules

- Do not run a full import before the 50-stock and 300-stock smoke imports pass.
- Use `--symbol-limit` for smoke imports. It selects one consistent stock universe
  and filters related tables to that universe.
- Use `--truncate` only when intentionally replacing the target sample or target
  database contents.
- The helper normalizes SQLite date strings such as `20240507` to `2024-05-07`
  and deduplicates rows by PostgreSQL primary-key semantics.
- Related tables are filtered through the source `stocks` table. Source rows for
  symbols missing from `stocks`, for example orphan ETF code `512880`, are skipped
  to preserve PostgreSQL foreign-key integrity.

## Dry Run

Dry-run mode compares source and target counts without copying data.

```bash
python3 scripts/postgres/migrate-sqlite-to-postgres.py \
  --table stocks \
  --table daily_klines \
  --table factor_values \
  --symbol-limit 50 \
  --batch-size 10000
```

## Sample Imports

Start with 50 stocks:

```bash
python3 scripts/postgres/migrate-sqlite-to-postgres.py \
  --table stocks \
  --table daily_klines \
  --table factor_values \
  --symbol-limit 50 \
  --execute \
  --truncate \
  --batch-size 10000

psql quant_investment -f scripts/postgres/verify-quant-db.sql
```

Then expand to 300 stocks:

```bash
python3 scripts/postgres/migrate-sqlite-to-postgres.py \
  --table stocks \
  --table daily_klines \
  --table factor_values \
  --symbol-limit 300 \
  --execute \
  --truncate \
  --batch-size 50000

psql quant_investment -f scripts/postgres/verify-quant-db.sql
```

## Full Import

Only run this after the 300-stock import validates cleanly. For the current local
database, the highest-value full import is the core table set:

```bash
python3 scripts/postgres/migrate-sqlite-to-postgres.py \
  --table stocks \
  --table daily_klines \
  --table factor_values \
  --execute \
  --truncate \
  --batch-size 50000

psql quant_investment -f scripts/postgres/verify-quant-db.sql
```

Optional low-value tables can be migrated later if they contain data:

```bash
python3 scripts/postgres/migrate-sqlite-to-postgres.py \
  --table daily_quotes \
  --table minute_klines \
  --table signals \
  --execute \
  --batch-size 50000
```

## Rollback Sample Data

For local smoke imports, reset imported quant tables with:

```bash
psql quant_investment -c "TRUNCATE quant.signals, quant.factor_values, quant.daily_quotes, quant.minute_klines, quant.daily_klines, quant.stocks RESTART IDENTITY CASCADE;"
```

Do not run the rollback command against production data unless a backup exists.

## Required Validation

After each import, verify:

- `verify-quant-db.sql` reports `0` orphan rows.
- Duplicate primary-key checks return `0`.
- Daily kline and factor date ranges are plausible.
- Row counts match the expected sample size after date normalization and dedupe.

## Runtime Smoke Checks

Run these before treating a local PostgreSQL refresh as usable:

```bash
PYTHONPATH=quant python scripts/postgres/smoke-postgres-runtime.py --skip-calibration

PYTHONPATH=quant python scripts/postgres/smoke-postgres-runtime.py \
  --calibration-symbols 20 \
  --calibration-lookback-days 20 \
  --calibration-min-samples-per-bin 5
```

The smoke script checks the provider-aware `Database` layer, the legacy
`QuantAPI` bridge, weekly backtest kline loading, and an optional bounded
confidence-calibration run against `PGDATABASE` (default: `quant_investment`).

Manual spot checks:

```bash
PYTHONPATH=quant PGDATABASE=quant_investment \
  python quant/api/quant_api.py get_klines '{"symbol":"000001","limit":3}'

PYTHONPATH=quant PGDATABASE=quant_investment \
  python - <<'PY'
from scripts.weekly_backtest import WeeklyBacktester
bt = WeeklyBacktester('quant')
try:
    frame = bt.load_kline_data('000001', days=5)
    print(frame.shape)
finally:
    bt.close()
PY
```

Confidence calibration should always be bounded for local runs:

```bash
PYTHONPATH=quant PGDATABASE=quant_investment \
  python -m quantsys.ml.confidence_calibrator \
  --lookback-days 180 \
  --max-symbols 500 \
  --forward-days 5 \
  --output .pi-invest/quant/confidence_config.json
```

Use smaller values such as `--lookback-days 20 --max-symbols 50` for fast smoke
tests.
