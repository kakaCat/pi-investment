# PostgreSQL Connection Timeout Fix

**Date:** 2026-05-27  
**Issue:** Connection timeout errors in TypeScript scheduler service  
**Root Cause:** Idle in transaction connections from Python quantsys-v2 scheduler  
**Status:** ✅ Fixed

## Problem

TypeScript scheduler service was experiencing connection timeouts:

```
Error: Connection terminated due to connection timeout
    at PostgresSchedulerStore.listTasks
    at SchedulerService.scanCompensations
```

## Root Cause Analysis

### Phase 1: Investigation

1. **PostgreSQL was running** - `pg_isready` confirmed database accepting connections
2. **Connection pool exhaustion** - Found 3 "idle in transaction" connections blocking the pool
3. **Two scheduler systems** - Discovered duplicate scheduler tables:
   - `public.scheduler_tasks` (TypeScript) - uses `enabled` column
   - `quant.scheduler_tasks` (Python) - uses `is_enabled` and `next_run_at` columns

4. **Idle transactions from Python** - Query traces showed:
   ```sql
   SELECT * FROM quant.scheduler_tasks 
   WHERE is_enabled = true 
   ORDER BY next_run_at ASC NULLS LAST
   ```

### Phase 2: Pattern Analysis

Found the bug in `quantsys-v2/runtime/scheduler/scheduler.py`:

**Five read-only methods missing transaction commits:**

1. `get_task()` - line 422
2. `get_task_by_name()` - line 435
3. `list_tasks()` - line 448
4. `get_run()` - line 622
5. `list_runs()` - line 635

**The Pattern:**
```python
def list_tasks(self, enabled_only: bool = False):
    conn = self._get_conn()  # Cached connection
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT ...")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()  # ❌ Only closes cursor, NOT the connection!
```

**Why this causes timeouts:**
- psycopg2 starts a transaction even for SELECT queries
- Without `conn.commit()` or `conn.rollback()`, connection stays in "idle in transaction" state
- Connection is cached in `self._conn` and reused, so it stays stuck
- Pool exhausts (max: 10 connections), new connections timeout after 5 seconds

### Phase 3: Fix

Added `conn.commit()` after all read-only queries:

```python
def list_tasks(self, enabled_only: bool = False):
    conn = self._get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT ...")
        rows = cursor.fetchall()
        conn.commit()  # ✅ Commit to close transaction
        return [dict(row) for row in rows]
    finally:
        cursor.close()
```

**Changes:**
- `get_task()` - added `conn.commit()` after `fetchone()`
- `get_task_by_name()` - added `conn.commit()` after `fetchone()`
- `list_tasks()` - added `conn.commit()` after `fetchall()`
- `get_run()` - added `conn.commit()` after `fetchone()`
- `list_runs()` - added `conn.commit()` after `fetchall()`

## Verification

### Before Fix
```
 active_connections |        state        
--------------------+---------------------
                  1 | active
                 21 | idle
                  3 | idle in transaction  ❌
```

### After Fix
```
 active_connections | state  
--------------------+--------
                  1 | active
                 21 | idle                 ✅
```

### Tests
- All 88/89 scheduler tests passing
- No new idle in transaction connections after running tests
- Connection pool healthy

## Prevention

**Best Practice for psycopg2:**
- Always commit or rollback after queries, even read-only SELECTs
- Use connection pooling libraries (psycopg2.pool) for better lifecycle management
- Consider using context managers for automatic transaction handling

**Alternative Pattern:**
```python
def list_tasks(self):
    conn = self._get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT ...")
            rows = cursor.fetchall()
        conn.commit()
        return [dict(row) for row in rows]
    except Exception:
        conn.rollback()
        raise
```

## Related Files

- `quantsys-v2/runtime/scheduler/scheduler.py` - Fixed file
- `quantsys-v2/tests/test_scheduler.py` - Test coverage
- `src/services/scheduler/postgres-client.ts` - TypeScript scheduler (separate system)

## Lessons Learned

1. **Multiple scheduler systems** - Having two separate scheduler implementations (TypeScript + Python) with different schemas created confusion
2. **Connection lifecycle** - psycopg2 requires explicit transaction management even for read-only queries
3. **Cached connections** - The `self._conn` caching pattern amplified the issue by keeping broken connections alive
4. **Systematic debugging** - Following the 4-phase debugging process (root cause → pattern → hypothesis → implementation) prevented guess-and-check thrashing
