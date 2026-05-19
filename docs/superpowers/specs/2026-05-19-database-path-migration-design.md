# Database Path Migration Design

**Date:** 2026-05-19  
**Status:** Approved  
**Author:** Claude (Kiro)

## Overview

Consolidate all database path references from the legacy `quant/quantsys/data/stocks.db` to the canonical `.pi-invest/stock-db/stocks.db` location. This migration includes data consolidation, path replacement across the codebase, and cleanup of obsolete database files.

## Background

The project currently has two database locations:
- **Canonical:** `.pi-invest/stock-db/stocks.db` (975MB, 5,847 stocks, 5.2M K-line records, last updated 2026-05-14)
- **Legacy:** `quant/quantsys/data/stocks.db` (37MB, 5,518 stocks, 49K K-line records, last updated 2026-05-19)

The legacy database contains recent incremental data (2026-05-15 to 2026-05-19) that must be preserved before migration.

## Goals

1. Preserve all data from both databases
2. Unify all code to use `.pi-invest/stock-db/stocks.db`
3. Remove obsolete database files
4. Ensure zero data loss

## Non-Goals

- Refactoring database access patterns
- Introducing configuration abstraction
- Changing database schema

## Implementation Plan

### Phase 1: Data Consolidation

**1.1 Create Migration Script**

Create `quant/scripts/migrate_db_data.py` with the following logic:

```python
# Pseudocode
source_db = "quant/quantsys/data/stocks.db"
target_db = ".pi-invest/stock-db/stocks.db"

# Extract incremental K-line data (2026-05-15 to 2026-05-19)
incremental_klines = query(source_db, "SELECT * FROM daily_klines WHERE date >= '2026-05-15'")

# Extract new stocks not in target
source_stocks = query(source_db, "SELECT symbol FROM stocks")
target_stocks = query(target_db, "SELECT symbol FROM stocks")
new_stocks = source_stocks - target_stocks

# Insert into target using INSERT OR REPLACE
insert_or_replace(target_db, "daily_klines", incremental_klines)
insert_or_replace(target_db, "stocks", new_stocks)

# Log migration summary
print(f"Migrated {len(incremental_klines)} K-line records")
print(f"Migrated {len(new_stocks)} new stocks")
```

**1.2 Backup Strategy**

Before migration:
```bash
cp quant/quantsys/data/stocks.db quant/quantsys/data/stocks.db.backup
cp .pi-invest/stock-db/stocks.db .pi-invest/stock-db/stocks.db.backup
```

**1.3 Execute Migration**

```bash
python quant/scripts/migrate_db_data.py
```

**1.4 Verification**

- Confirm target database has records up to 2026-05-19
- Verify stock count matches or exceeds source
- Check no data loss in critical symbols

### Phase 2: Path Replacement

**2.1 Python Files**

Replace in all `.py` files:
- Pattern: `os.path.join(..., 'quantsys', 'data', 'stocks.db')`
- Replacement: `os.path.join(..., '.pi-invest', 'stock-db', 'stocks.db')`

Or:
- Pattern: `'quantsys/data/stocks.db'`
- Replacement: `'.pi-invest/stock-db/stocks.db'`

**Affected files:**
- `python/akshare_bridge.py` (4 occurrences)
- `quant/api/quant_api.py`
- `quant/api/server.py`
- `quant/scripts/*.py` (~20 scripts including):
  - `calculate_factors.py`
  - `ml_predict.py`
  - `risk_check.py`
  - `fetch_hs300_data.py`
  - `calculate_trading_days.py`
  - `analyze_stock_factors.py`
  - `generate_signals.py`
  - `calculate_historical_factors.py`
  - `ml_retrain.py`
  - `generate_enhanced_report.py`
  - `daily_update.py`
  - `test_ml_retrain.py`
  - `weekly_backtest.py`
  - `sync_watchlist_stocks.py`
  - `sync_portfolio_stocks.py`
  - `download_5year_data.py`
  - `scheduler.py`
- `quant/examples/01_first_backtest.py`

**2.2 TypeScript Files**

Update `src/api/web/server.ts`:
- Remove fallback logic that tries multiple paths
- Use single canonical path: `path.join(__dirname, '../../../.pi-invest/stock-db/stocks.db')`

**2.3 Verification**

```bash
# Confirm no legacy paths remain
grep -r "quantsys/data/stocks.db" --include="*.py" --include="*.ts" --include="*.js" .

# Should return 0 results (except in this spec doc)
```

### Phase 3: Cleanup

**3.1 Remove Obsolete Files**

```bash
rm quant/quantsys/data/stocks.db
rm quant/quantsys/data/quant.db
```

**3.2 Keep Backups**

Retain backup files for 7 days:
- `quant/quantsys/data/stocks.db.backup`
- `.pi-invest/stock-db/stocks.db.backup`

### Phase 4: Testing

**4.1 Smoke Tests**

Run key scripts to verify database access:
```bash
python quant/scripts/daily_update.py --dry-run
python python/akshare_bridge.py get_stock_info '{"symbol": "600519"}'
```

**4.2 Integration Tests**

- Start web server: `npm run dev`
- Test API endpoint: `GET /api/stocks/600519/factors`
- Verify data returned correctly

**4.3 Rollback Plan**

If issues arise:
```bash
# Restore backups
cp quant/quantsys/data/stocks.db.backup quant/quantsys/data/stocks.db
cp .pi-invest/stock-db/stocks.db.backup .pi-invest/stock-db/stocks.db

# Revert code changes
git checkout .
```

## Success Criteria

- [ ] All incremental data (2026-05-15 to 2026-05-19) preserved in canonical database
- [ ] Zero occurrences of `quantsys/data/stocks.db` in codebase (except docs)
- [ ] All scripts and APIs access data successfully
- [ ] Legacy database files removed
- [ ] Latest K-line date in canonical database is 2026-05-19

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data loss during migration | High | Create backups before migration; verify record counts |
| Missed path references | Medium | Use comprehensive grep; test all affected scripts |
| Dynamic path construction | Low | Manual review of path.join() patterns |
| Concurrent writes during migration | Low | Run migration during maintenance window |

## Timeline

- Phase 1 (Data Consolidation): 30 minutes
- Phase 2 (Path Replacement): 45 minutes
- Phase 3 (Cleanup): 5 minutes
- Phase 4 (Testing): 30 minutes

**Total estimated time:** 2 hours

## Future Considerations

- Consider adding a configuration constant for database path in future refactoring
- Monitor for any hardcoded paths in documentation or scripts
- Update developer onboarding docs to reference canonical path only
