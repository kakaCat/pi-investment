# Unified ETL Data Update API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge 5 overlapping ETL scripts into one `POST /api/data/update` endpoint with source/days/async/force parameters.

**Architecture:** New endpoint lives in `server.py`, imports Database and KlineFetcher directly. Stock list is resolved from source parameter. Incremental check queries existing kline coverage per symbol. Async mode reuses existing `_create_job` + daemon thread pattern.

**Tech Stack:** Python Flask, sqlite3, akshare, quantsys.data.db / quantsys.data.fetchers.klines

---

## File Layout

| File | Action | Role |
|------|--------|------|
| `quant/api/server.py` | MODIFY | Add unified endpoint, remove 5 old ones |
| `quant/scripts/daily_update.py` | DELETE | Merged |
| `quant/scripts/download_5year_data.py` | DELETE | Merged |
| `quant/scripts/fetch_hs300_data.py` | DELETE | Merged |
| `quant/scripts/sync_portfolio_stocks.py` | DELETE | Merged |
| `quant/scripts/sync_watchlist_stocks.py` | DELETE | Merged |
| `src/infrastructure/quant/quant-api-client.ts` | MODIFY | Add `updateData()` method |
| `src/services/quant/quant-service.ts` | MODIFY | Add `updateStockData()` method |

---

### Task 1: Add unified endpoint to server.py

**Files:**
- Modify: `quant/api/server.py` (after line 1227, replace 5 old endpoints)

- [ ] **Step 1: Write the `_resolve_stock_list` helper**

Add after `_run_etl_script`:

```python
def _resolve_stock_list(source: str, db: Database) -> list[dict]:
    """Resolve stock list from the requested source."""
    project_root = Path(__file__).parent.parent.parent  # pi-investment root

    if source == 'portfolio':
        portfolio_path = project_root / '.pi-invest' / 'portfolio.json'
        if not portfolio_path.exists():
            raise ValueError('portfolio.json not found')
        with open(portfolio_path) as f:
            holdings = json.load(f).get('holdings', [])
        return [
            {'symbol': h['symbol'], 'name': h.get('name', '')}
            for h in holdings
            if h.get('market', 'A') == 'A' and not h['symbol'].startswith('5')
        ]

    elif source == 'watchlist':
        watchlist_path = project_root / '.pi-invest' / 'watchlist.json'
        if not watchlist_path.exists():
            raise ValueError('watchlist.json not found')
        with open(watchlist_path) as f:
            items = json.load(f).get('items', [])
        return [
            {'symbol': i['symbol'], 'name': i.get('name', '')}
            for i in items
            if not i['symbol'].startswith('5')  # skip ETFs
        ]

    elif source == 'hs300':
        import akshare as ak
        df = ak.index_stock_cons_csindex(symbol='000300')
        stocks = []
        for _, row in df.iterrows():
            symbol = row['成分券代码']
            name = row['成分券名称']
            db._get_connection().execute(
                'INSERT OR REPLACE INTO stocks (symbol, name, market) VALUES (?, ?, ?)',
                (symbol, name, 'A')
            )
            stocks.append({'symbol': symbol, 'name': name})
        db._get_connection().commit()
        return stocks

    elif source == 'all':
        conn = db._get_connection()
        rows = conn.execute('SELECT symbol, name FROM stocks WHERE market = ?', ('A',)).fetchall()
        return [{'symbol': r[0], 'name': r[1]} for r in rows]

    else:
        raise ValueError(f'Unknown source: {source}')
```

- [ ] **Step 2: Write the `_check_kline_coverage` helper**

```python
def _check_kline_coverage(db: Database, symbol: str) -> dict:
    """Check existing kline data coverage for a symbol."""
    conn = db._get_connection()
    row = conn.execute(
        'SELECT COUNT(*) as count, MIN(date) as first_date, MAX(date) as last_date '
        'FROM daily_klines WHERE symbol = ?',
        (symbol,)
    ).fetchone()
    if row and row[0]:
        return {
            'existing_days': row[0],
            'first_date': row[1],
            'last_date': row[2],
        }
    return {'existing_days': 0, 'first_date': None, 'last_date': None}
```

- [ ] **Step 3: Write the unified endpoint**

Replace the 5 old endpoints (lines ~1195-1227) with:

```python
@app.route('/api/data/update', methods=['POST'])
def unified_data_update():
    """统一数据更新入口"""
    data = request.get_json() or {}
    source = data.get('source', 'all')
    days = data.get('days', 5)
    async_mode = data.get('async', False)
    force = data.get('force', False)

    # Validate
    valid_sources = ['portfolio', 'watchlist', 'hs300', 'all']
    if source not in valid_sources:
        return jsonify({'success': False, 'error': f'source must be one of {valid_sources}'}), 400
    if not isinstance(days, int) or days < 1:
        return jsonify({'success': False, 'error': 'days must be a positive integer'}), 400

    # Async mode — delegate to job thread
    if async_mode:
        def _run():
            return _execute_data_update(source, days, force)
        job_id = _create_job('data_update', {'source': source, 'days': days, 'force': force})
        threading.Thread(target=lambda: _run_script_async(job_id, None), daemon=True).start()
        # Override — actually run inline logic in thread
        def _run_inline():
            try:
                result = _execute_data_update(source, days, force)
                _update_job(job_id, result)
            except Exception as e:
                _update_job(job_id, {'success': False, 'error': str(e)})
        threading.Thread(target=_run_inline, daemon=True).start()
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': f'数据更新任务已提交 ({source}, {days}天)'
        })

    # Sync mode
    try:
        result = _execute_data_update(source, days, force)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _execute_data_update(source: str, days: int, force: bool) -> dict:
    """Core update logic — called by both sync and async paths."""
    db_path = Path(__file__).parent.parent.parent / '.pi-invest' / 'stock-db' / 'stocks.db'
    db = Database(str(db_path))
    fetcher = KlineFetcher(db)

    stocks = _resolve_stock_list(source, db)

    details = []
    updated_count = 0
    skipped_count = 0
    failed_count = 0

    for stock in stocks:
        symbol = stock['symbol']
        name = stock['name']
        detail = {'symbol': symbol, 'name': name}

        try:
            if not force:
                coverage = _check_kline_coverage(db, symbol)
                detail['existing_days'] = coverage['existing_days']

                # Skip if already has enough data (coverage within 3 days of today)
                if coverage['existing_days'] > 0 and coverage['existing_days'] >= days * 0.9:
                    detail['status'] = 'skipped'
                    detail['new_days'] = 0
                    detail['error'] = None
                    skipped_count += 1
                    details.append(detail)
                    continue

            fetcher.run(symbols=[symbol], days=days, market='A')
            new_coverage = _check_kline_coverage(db, symbol)
            detail['status'] = 'updated'
            detail['new_days'] = new_coverage['existing_days'] - detail.get('existing_days', 0)
            detail['existing_days'] = new_coverage['existing_days']
            detail['error'] = None
            updated_count += 1

        except Exception as e:
            detail['status'] = 'failed'
            detail['error'] = str(e)[:200]
            detail['new_days'] = 0
            failed_count += 1

        details.append(detail)

    db.close()
    return {
        'success': True,
        'source': source,
        'days': days,
        'total': len(stocks),
        'updated': updated_count,
        'skipped': skipped_count,
        'failed': failed_count,
        'details': details,
    }
```

- [ ] **Step 4: Verify the endpoint loads without errors**

```bash
cd /Users/mac/Documents/ai/pi-investment && python3 -c "
import sys; sys.path.insert(0, 'quant')
from quant.api.server import app
print('Import OK')
"
```

Expected: `Import OK`

- [ ] **Step 5: Remove 5 old endpoints**

Delete lines from `@app.route('/api/data/update', methods=['POST'])` (old) through `trigger_sync_watchlist` → remove:
- Old `trigger_daily_update` (lines ~1195-1200)
- `trigger_download_history` (lines ~1203-1207)
- `trigger_fetch_hs300` (lines ~1210-1214)
- `trigger_sync_portfolio` (lines ~1217-1221)
- `trigger_sync_watchlist` (lines ~1224-1227)

- [ ] **Step 6: Commit**

```bash
git add quant/api/server.py
git commit -m "feat: add unified POST /api/data/update endpoint, remove 5 old ETL endpoints"
```

---

### Task 2: Delete old ETL scripts

**Files:**
- Delete: `quant/scripts/daily_update.py`
- Delete: `quant/scripts/download_5year_data.py`
- Delete: `quant/scripts/fetch_hs300_data.py`
- Delete: `quant/scripts/sync_portfolio_stocks.py`
- Delete: `quant/scripts/sync_watchlist_stocks.py`

- [ ] **Step 1: Delete the files**

```bash
cd /Users/mac/Documents/ai/pi-investment
rm quant/scripts/daily_update.py
rm quant/scripts/download_5year_data.py
rm quant/scripts/fetch_hs300_data.py
rm quant/scripts/sync_portfolio_stocks.py
rm quant/scripts/sync_watchlist_stocks.py
```

- [ ] **Step 2: Commit**

```bash
git add -u quant/scripts/
git commit -m "refactor: remove 5 old ETL scripts, merged into unified API endpoint"
```

---

### Task 3: Update TypeScript API client

**Files:**
- Modify: `src/infrastructure/quant/quant-api-client.ts`

- [ ] **Step 1: Add types for update data request/response**

Add before the `QuantAPIClient` class:

```typescript
export interface UpdateDataRequest {
  source: 'portfolio' | 'watchlist' | 'hs300' | 'all';
  days: number;
  async?: boolean;
  force?: boolean;
}

export interface UpdateDataDetail {
  symbol: string;
  name: string;
  status: 'updated' | 'skipped' | 'failed';
  existing_days: number;
  new_days: number;
  error: string | null;
}

export interface UpdateDataResponse {
  success: boolean;
  source: string;
  days: number;
  total: number;
  updated: number;
  skipped: number;
  failed: number;
  details: UpdateDataDetail[];
}

export interface AsyncJobResponse {
  success: boolean;
  job_id: string;
  message: string;
}
```

- [ ] **Step 2: Add `updateData` method to QuantAPIClient class**

Add inside the class:

```typescript
async updateData(params: UpdateDataRequest): Promise<UpdateDataResponse | AsyncJobResponse> {
  const res = await fetch(`${this.baseUrl}/data/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}
```

- [ ] **Step 3: Commit**

```bash
git add src/infrastructure/quant/quant-api-client.ts
git commit -m "feat: add updateData() method to quant-api-client for unified ETL"
```

---

### Task 4: Update TypeScript quant-service

**Files:**
- Modify: `src/services/quant/quant-service.ts`

- [ ] **Step 1: Add `updateStockData` method**

Add after existing methods:

```typescript
async updateStockData(params: {
  source: 'portfolio' | 'watchlist' | 'hs300' | 'all';
  days: number;
  async?: boolean;
  force?: boolean;
}): Promise<{ jobId?: string; stats?: { total: number; updated: number; skipped: number; failed: number } }> {
  const quantClient = await this.getClient(); // or import directly
  const result = await quantClient.updateData(params);
  if ('job_id' in result) {
    return { jobId: result.job_id };
  }
  return { stats: { total: result.total, updated: result.updated, skipped: result.skipped, failed: result.failed } };
}
```

- [ ] **Step 2: Commit**

```bash
git add src/services/quant/quant-service.ts
git commit -m "feat: add updateStockData() to quant-service for unified ETL"
```

---

### Task 5: Smoke test the endpoint

- [ ] **Step 1: Start Flask server**

```bash
cd /Users/mac/Documents/ai/pi-investment && python3 quant/api/server.py &
sleep 2
```

- [ ] **Step 2: Test minimal sync update**

```bash
curl -s -X POST http://localhost:5001/api/data/update \
  -H 'Content-Type: application/json' \
  -d '{"source":"portfolio","days":5,"async":false}' | python3 -m json.tool | head -20
```

Expected: `{"success": true, "source": "portfolio", "days": 5, ...}`

- [ ] **Step 3: Test async mode**

```bash
curl -s -X POST http://localhost:5001/api/data/update \
  -H 'Content-Type: application/json' \
  -d '{"source":"hs300","days":30,"async":true}' | python3 -m json.tool
```

Expected: `{"success": true, "job_id": "data_update_...", "message": "..."}`

- [ ] **Step 4: Test invalid source**

```bash
curl -s -X POST http://localhost:5001/api/data/update \
  -H 'Content-Type: application/json' \
  -d '{"source":"unknown","days":5}'
```

Expected: `{"success": false, "error": "source must be one of ..."}`

- [ ] **Step 5: Stop server**

```bash
kill %1 2>/dev/null; pkill -f "quant/api/server.py" 2>/dev/null
```

- [ ] **Step 6: Commit any fixes if needed**
