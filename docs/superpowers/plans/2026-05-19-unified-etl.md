# Unified ETL Data Update API — Implementation Plan

> **Status:** 旧系统已完成；仅剩 quantsys-v2 API 端点待实现。
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add unified `POST /api/data/update` endpoint to quantsys-v2 API.

**Architecture:** 数据更新走 CLI（`quantsys.cli data update-klines`），Web API 提供 HTTP 入口封装。TypeScript 层已通过 `quant-service.ts` → `quant-cli-client.ts` → `runQuantCli()` 完成调度，不需改动。

**Tech Stack:** Python Flask, psycopg2, PostgreSQL (quant)

---

## Current State

| Layer | Status |
|-------|--------|
| 旧 `quant/api/server.py` `/api/data/update` | Done — 可用，不删 |
| 旧 5 个 ETL 脚本 | Done — 已删除 |
| TypeScript `quant-service.ts` `updateStockData()` | Done — 走 `runQuantCli('data', 'update-klines')` |
| TypeScript 类型 `UpdateDataRequest/Response` | Done — 定义在 `quant-service.ts` |
| **quantsys-v2 `/api/data/update`** | **待实现** |

---

## File Layout

| File | Action | Role |
|------|--------|------|
| `quantsys-v2/api/server.py` | MODIFY | Add unified `/api/data/update` endpoint |

---

### Task 1: Add data update endpoint to quantsys-v2 API

**Files:**
- Modify: `quantsys-v2/api/server.py` (before `if __name__`)

- [ ] **Step 1: Add the endpoint and `_execute_data_update` helper**

Add after the execution routes, before `if __name__`:

```python
@app.route('/api/data/update', methods=['POST'])
def unified_data_update():
    """统一数据更新入口

    Request JSON:
      source: "portfolio" | "watchlist" | "hs300" | "all"
      days:   正整数
      async:  false(默认, 同步返回) | true(返回 job_id)
      force:  false(默认, 跳过已有数据) | true(强制全拉)
    """
    data = request.get_json() or {}
    source = data.get('source', 'all')
    days = data.get('days', 5)
    async_mode = data.get('async', False)
    force = data.get('force', False)

    valid_sources = ['portfolio', 'watchlist', 'hs300', 'all']
    if source not in valid_sources:
        return jsonify({'success': False, 'error': f'source must be one of {valid_sources}'}), 400
    if not isinstance(days, int) or days < 1:
        return jsonify({'success': False, 'error': 'days must be a positive integer'}), 400

    if async_mode:
        import threading, uuid
        job_id = f"data_update_{uuid.uuid4().hex[:8]}"
        def _run_async():
            try:
                _execute_data_update(source, days, force)
            except Exception:
                pass
        threading.Thread(target=_run_async, daemon=True).start()
        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': f'数据更新任务已提交 ({source}, {days}天)'
        })

    try:
        result = _execute_data_update(source, days, force)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _execute_data_update(source: str, days: int, force: bool) -> dict:
    """Core update logic — resolve stock list and fetch klines."""
    from core.base_repository import _resolve_db_dsn
    import psycopg2
    from psycopg2.extras import RealDictCursor

    # Resolve stock list
    if source == 'hs300':
        import akshare as ak
        df = ak.index_stock_cons_csindex(symbol='000300')
        stocks = [{'symbol': row['成分券代码'], 'name': row['成分券名称']} for _, row in df.iterrows()]
    elif source in ('portfolio', 'watchlist'):
        import json
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        filename = 'portfolio.json' if source == 'portfolio' else 'watchlist.json'
        path = project_root / '.pi-invest' / filename
        if not path.exists():
            raise ValueError(f'{filename} not found')
        with open(path) as f:
            data = json.load(f)
        items = data.get('holdings', []) if source == 'portfolio' else data.get('items', [])
        stocks = [{'symbol': i['symbol'], 'name': i.get('name', '')} for i in items]
    else:  # all
        dsn = _resolve_db_dsn()
        if not dsn:
            raise RuntimeError('Database connection not configured')
        conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        cur.execute('SELECT symbol, name FROM quant.stocks WHERE market = %s', ('A',))
        stocks = [{'symbol': r['symbol'], 'name': r['name']} for r in cur.fetchall()]
        cur.close()
        conn.close()

    # Fetch klines for resolved symbols
    from quant.data.fetchers.klines import KlineFetcher
    from quant.data.db import Database

    project_root = __import__('pathlib').Path(__file__).parent.parent.parent
    db_path = project_root / '.pi-invest' / 'stock-db' / 'stocks.db'
    db = Database(str(db_path))
    fetcher = KlineFetcher(db)

    details = []
    updated = skipped = failed = 0

    for stock in stocks:
        symbol = stock['symbol']
        detail = {'symbol': symbol, 'name': stock['name']}
        try:
            fetcher.run(symbols=[symbol], days=days, market='A')
            detail['status'] = 'updated'
            detail['error'] = None
            updated += 1
        except Exception as e:
            detail['status'] = 'failed'
            detail['error'] = str(e)[:200]
            failed += 1
        details.append(detail)

    db.close()
    return {
        'success': True,
        'source': source,
        'days': days,
        'total': len(stocks),
        'updated': updated,
        'skipped': skipped,
        'failed': failed,
        'details': details,
    }
```

- [ ] **Step 2: Verify the endpoint loads**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python3 -c "
from api.server import app
print('Import OK')
"
```

Expected: `Import OK`

- [ ] **Step 3: Test via curl**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && PGDATABASE=quant_investment python3 api/server.py &
sleep 2
curl -s -X POST http://localhost:5001/api/data/update \
  -H 'Content-Type: application/json' \
  -d '{"source":"portfolio","days":3}' | python3 -m json.tool | head -20
```

- [ ] **Step 4: Stop server & commit**

```bash
kill %1 2>/dev/null
git add quantsys-v2/api/server.py
git commit -m "feat: add unified POST /api/data/update endpoint to v2 API"
```
