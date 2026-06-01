# Stock Pool Screening & Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the "screening → stock pool → strategy validation" pipeline, adding custom pool CRUD, dynamic pool refresh, and multi-strategy batch comparison with auto-recommendation.

**Architecture:** Extend existing quantsys-v2 with a `stock_pools` table, `StockPoolRepository` for CRUD, extended `StockPoolService` for pool lifecycle, new `PoolValidationService` for strategy comparison, Flask API routes, and two TypeScript Agent tools (`pool_manage`, `pool_validate`) calling via `QuantV2Client`.

**Tech Stack:** Python 3.13 / Flask / PostgreSQL / psycopg2, TypeScript / @sinclair/typebox

**Spec:** `docs/superpowers/specs/2026-06-01-stock-pool-screening-validation-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `quantsys-v2/migrations/add_stock_pools_table.sql` | DDL for `quant.stock_pools` table |
| `quantsys-v2/repositories/stock_pool_repository.py` | CRUD data access for stock_pools |
| `quantsys-v2/services/pool_validation_service.py` | Strategy×pool batch backtest orchestration |
| `quantsys-v2/api/routes/pools.py` | Flask Blueprint for `/api/pools/*` endpoints |
| `quantsys-v2/tests/repositories/test_stock_pool_repository.py` | Repository unit tests |
| `quantsys-v2/tests/services/test_pool_validation_service.py` | Validation service unit tests |
| `quantsys-v2/tests/api/test_pools_routes.py` | API route integration tests |
| `src/infrastructure/tools/pool/pool-manage-tool.ts` | Agent tool for pool CRUD |
| `src/infrastructure/tools/pool/pool-validate-tool.ts` | Agent tool for strategy validation |

### Modified Files

| File | Change |
|------|--------|
| `quantsys-v2/services/stock_pool_service.py` | Add CRUD, refresh, create_from_scan methods |
| `quantsys-v2/api/shared.py` | Wire `StockPoolRepository`, `PoolValidationService` |
| `quantsys-v2/api/server.py` | Register `pools_bp` blueprint |
| `src/infrastructure/quant/quant-v2-client.ts` | Add pool API methods |
| `src/infrastructure/tools/index.ts` | Register pool tools |

---

### Task 1: Database Migration

**Files:**
- Create: `quantsys-v2/migrations/add_stock_pools_table.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- Stock Pools table for screening → pool → validation pipeline
-- Supports static (manually curated) and dynamic (auto-refreshed) pools

CREATE TABLE IF NOT EXISTS quant.stock_pools (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    pool_type VARCHAR(10) NOT NULL CHECK (pool_type IN ('static', 'dynamic')),
    description TEXT,
    symbols TEXT[] NOT NULL DEFAULT '{}',
    filter_template JSONB,
    refresh_interval VARCHAR(20) CHECK (refresh_interval IN ('daily', 'weekly', NULL)),
    last_refreshed_at TIMESTAMP,
    last_validation JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_pools_pool_type ON quant.stock_pools(pool_type);
CREATE INDEX IF NOT EXISTS idx_stock_pools_name ON quant.stock_pools(name);

COMMENT ON TABLE quant.stock_pools IS '股票池管理表：支持静态池和动态池（定时刷新）';
COMMENT ON COLUMN quant.stock_pools.pool_type IS 'static=手动锁定, dynamic=按filter_template定时刷新';
COMMENT ON COLUMN quant.stock_pools.filter_template IS '动态池筛选条件模板（JSON），复用 /api/signals/scan 参数格式';
COMMENT ON COLUMN quant.stock_pools.last_validation IS '最近一次策略验证结果快照（JSON）';
```

- [ ] **Step 2: Apply the migration**

Run:
```bash
cd quantsys-v2 && psql -d quant_investment -f migrations/add_stock_pools_table.sql
```
Expected: `CREATE TABLE`, `CREATE INDEX` (no errors)

Also apply to test database:
```bash
cd quantsys-v2 && psql -d quant_test -f migrations/add_stock_pools_table.sql
```

- [ ] **Step 3: Verify table exists**

Run:
```bash
psql -d quant_investment -c "\d quant.stock_pools"
```
Expected: Table with 11 columns (id, name, pool_type, description, symbols, filter_template, refresh_interval, last_refreshed_at, last_validation, created_at, updated_at)

- [ ] **Step 4: Commit**

```bash
git add quantsys-v2/migrations/add_stock_pools_table.sql
git commit -m "feat(pool): add stock_pools table migration"
```

---

### Task 2: StockPoolRepository

**Files:**
- Create: `quantsys-v2/tests/repositories/test_stock_pool_repository.py`
- Create: `quantsys-v2/repositories/stock_pool_repository.py`

- [ ] **Step 1: Write failing tests for repository CRUD**

```python
# quantsys-v2/tests/repositories/test_stock_pool_repository.py
import json
import pytest
from repositories.stock_pool_repository import StockPoolRepository


@pytest.fixture
def repo():
    r = StockPoolRepository()
    # Clean up before each test
    cursor = r.db.cursor()
    cursor.execute("DELETE FROM quant.stock_pools")
    cursor.close()
    r.db.commit()
    return r


class TestStockPoolRepository:
    def test_create_static_pool(self, repo):
        pool = repo.create({
            'name': '测试静态池',
            'pool_type': 'static',
            'description': '单元测试用',
            'symbols': ['600519.SH', '000858.SZ'],
        })
        assert pool['id'] > 0
        assert pool['name'] == '测试静态池'
        assert pool['pool_type'] == 'static'
        assert pool['symbols'] == ['600519.SH', '000858.SZ']
        assert pool['filter_template'] is None

    def test_create_dynamic_pool(self, repo):
        template = {'min_score': 60, 'fundamental': ['pe_low'], 'top_n': 20}
        pool = repo.create({
            'name': '测试动态池',
            'pool_type': 'dynamic',
            'symbols': ['600519.SH'],
            'filter_template': template,
            'refresh_interval': 'weekly',
        })
        assert pool['pool_type'] == 'dynamic'
        assert pool['filter_template'] == template
        assert pool['refresh_interval'] == 'weekly'

    def test_get_by_id(self, repo):
        created = repo.create({
            'name': 'get测试',
            'pool_type': 'static',
            'symbols': ['600519.SH'],
        })
        fetched = repo.get_by_id(created['id'])
        assert fetched is not None
        assert fetched['name'] == 'get测试'

    def test_get_by_id_not_found(self, repo):
        result = repo.get_by_id(99999)
        assert result is None

    def test_get_all(self, repo):
        repo.create({'name': '池1', 'pool_type': 'static', 'symbols': ['600519.SH']})
        repo.create({'name': '池2', 'pool_type': 'dynamic', 'symbols': ['000858.SZ'],
                      'filter_template': {'min_score': 50}, 'refresh_interval': 'daily'})
        pools = repo.get_all()
        assert len(pools) == 2

    def test_update(self, repo):
        created = repo.create({
            'name': '更新前',
            'pool_type': 'static',
            'symbols': ['600519.SH'],
        })
        updated = repo.update(created['id'], {
            'name': '更新后',
            'symbols': ['600519.SH', '000001.SZ'],
            'description': '已更新',
        })
        assert updated['name'] == '更新后'
        assert len(updated['symbols']) == 2
        assert updated['description'] == '已更新'

    def test_update_not_found(self, repo):
        result = repo.update(99999, {'name': '不存在'})
        assert result is None

    def test_delete(self, repo):
        created = repo.create({
            'name': '待删除',
            'pool_type': 'static',
            'symbols': ['600519.SH'],
        })
        assert repo.delete(created['id']) is True
        assert repo.get_by_id(created['id']) is None

    def test_delete_not_found(self, repo):
        assert repo.delete(99999) is False

    def test_update_symbols(self, repo):
        created = repo.create({
            'name': '符号更新',
            'pool_type': 'dynamic',
            'symbols': ['600519.SH'],
            'filter_template': {'min_score': 60},
            'refresh_interval': 'daily',
        })
        updated = repo.update_symbols(created['id'], ['000001.SZ', '000002.SZ'])
        assert updated['symbols'] == ['000001.SZ', '000002.SZ']
        assert updated['last_refreshed_at'] is not None

    def test_update_validation(self, repo):
        created = repo.create({
            'name': '验证更新',
            'pool_type': 'static',
            'symbols': ['600519.SH'],
        })
        validation = {
            'validated_at': '2026-06-01T10:00:00',
            'best_strategy': {'id': 53, 'score': 82.5},
        }
        updated = repo.update_validation(created['id'], validation)
        assert updated['last_validation']['best_strategy']['id'] == 53

    def test_get_dynamic_pools(self, repo):
        repo.create({'name': '静态', 'pool_type': 'static', 'symbols': ['600519.SH']})
        repo.create({'name': '动态', 'pool_type': 'dynamic', 'symbols': ['000858.SZ'],
                      'filter_template': {'min_score': 50}, 'refresh_interval': 'daily'})
        dynamic = repo.get_dynamic_pools()
        assert len(dynamic) == 1
        assert dynamic[0]['pool_type'] == 'dynamic'
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd quantsys-v2 && python -m pytest tests/repositories/test_stock_pool_repository.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'repositories.stock_pool_repository'`

- [ ] **Step 3: Implement StockPoolRepository**

```python
# quantsys-v2/repositories/stock_pool_repository.py
"""Stock pool repository - CRUD for quant.stock_pools table."""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from infrastructure.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class StockPoolRepository(BaseRepository):
    """Data access for stock_pools table."""

    def create(self, data: Dict) -> Dict:
        """Create a new stock pool. Returns the created pool dict."""
        cursor = self.db.cursor()
        try:
            cursor.execute("""
                INSERT INTO quant.stock_pools
                    (name, pool_type, description, symbols,
                     filter_template, refresh_interval)
                VALUES
                    (%(name)s, %(pool_type)s, %(description)s, %(symbols)s,
                     %(filter_template)s, %(refresh_interval)s)
                RETURNING id
            """, {
                'name': data['name'],
                'pool_type': data['pool_type'],
                'description': data.get('description'),
                'symbols': data.get('symbols', []),
                'filter_template': json.dumps(data['filter_template']) if data.get('filter_template') else None,
                'refresh_interval': data.get('refresh_interval'),
            })
            result = dict(cursor.fetchone())
            self.db.commit()
            return self.get_by_id(result['id'])
        except Exception:
            self.db.rollback()
            raise
        finally:
            cursor.close()

    def get_by_id(self, pool_id: int) -> Optional[Dict]:
        """Get a pool by ID. Returns None if not found."""
        cursor = self.db.cursor()
        try:
            cursor.execute(
                "SELECT * FROM quant.stock_pools WHERE id = %(id)s",
                {'id': pool_id}
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._parse_row(row)
        finally:
            cursor.close()

    def get_all(self) -> List[Dict]:
        """Get all stock pools."""
        cursor = self.db.cursor()
        try:
            cursor.execute("SELECT * FROM quant.stock_pools ORDER BY created_at DESC")
            return [self._parse_row(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_dynamic_pools(self) -> List[Dict]:
        """Get all dynamic pools (for scheduler recovery)."""
        cursor = self.db.cursor()
        try:
            cursor.execute(
                "SELECT * FROM quant.stock_pools WHERE pool_type = 'dynamic' ORDER BY id"
            )
            return [self._parse_row(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def update(self, pool_id: int, data: Dict) -> Optional[Dict]:
        """Update pool fields. Returns updated pool or None if not found."""
        allowed = {'name', 'description', 'symbols', 'filter_template', 'refresh_interval'}
        fields = {k: v for k, v in data.items() if k in allowed and v is not None}
        if not fields:
            return self.get_by_id(pool_id)

        set_clauses = []
        params = {'id': pool_id}
        for key, value in fields.items():
            if key == 'filter_template':
                params[key] = json.dumps(value)
            else:
                params[key] = value
            set_clauses.append(f"{key} = %({key})s")
        set_clauses.append("updated_at = NOW()")

        cursor = self.db.cursor()
        try:
            cursor.execute(f"""
                UPDATE quant.stock_pools
                SET {', '.join(set_clauses)}
                WHERE id = %(id)s
                RETURNING id
            """, params)
            result = cursor.fetchone()
            self.db.commit()
            if not result:
                return None
            return self.get_by_id(pool_id)
        except Exception:
            self.db.rollback()
            raise
        finally:
            cursor.close()

    def update_symbols(self, pool_id: int, symbols: List[str]) -> Optional[Dict]:
        """Update pool symbols and set last_refreshed_at. Used by dynamic pool refresh."""
        cursor = self.db.cursor()
        try:
            cursor.execute("""
                UPDATE quant.stock_pools
                SET symbols = %(symbols)s,
                    last_refreshed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %(id)s
                RETURNING id
            """, {'id': pool_id, 'symbols': symbols})
            result = cursor.fetchone()
            self.db.commit()
            if not result:
                return None
            return self.get_by_id(pool_id)
        except Exception:
            self.db.rollback()
            raise
        finally:
            cursor.close()

    def update_validation(self, pool_id: int, validation: Dict) -> Optional[Dict]:
        """Update last_validation JSON snapshot."""
        cursor = self.db.cursor()
        try:
            cursor.execute("""
                UPDATE quant.stock_pools
                SET last_validation = %(validation)s,
                    updated_at = NOW()
                WHERE id = %(id)s
                RETURNING id
            """, {'id': pool_id, 'validation': json.dumps(validation)})
            result = cursor.fetchone()
            self.db.commit()
            if not result:
                return None
            return self.get_by_id(pool_id)
        except Exception:
            self.db.rollback()
            raise
        finally:
            cursor.close()

    def delete(self, pool_id: int) -> bool:
        """Delete a pool. Returns True if deleted, False if not found."""
        cursor = self.db.cursor()
        try:
            cursor.execute(
                "DELETE FROM quant.stock_pools WHERE id = %(id)s RETURNING id",
                {'id': pool_id}
            )
            result = cursor.fetchone()
            self.db.commit()
            return result is not None
        except Exception:
            self.db.rollback()
            raise
        finally:
            cursor.close()

    def _parse_row(self, row) -> Dict:
        """Convert a database row to a dict, parsing JSONB fields."""
        d = dict(row)
        # psycopg2 auto-parses JSONB, but if stored as string, parse it
        for jsonb_field in ('filter_template', 'last_validation'):
            if isinstance(d.get(jsonb_field), str):
                d[jsonb_field] = json.loads(d[jsonb_field])
        return d
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd quantsys-v2 && python -m pytest tests/repositories/test_stock_pool_repository.py -v
```
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/repositories/stock_pool_repository.py quantsys-v2/tests/repositories/test_stock_pool_repository.py
git commit -m "feat(pool): add StockPoolRepository with CRUD operations"
```

---

### Task 3: Extend StockPoolService

**Files:**
- Modify: `quantsys-v2/services/stock_pool_service.py`

- [ ] **Step 1: Read current file**

Read `quantsys-v2/services/stock_pool_service.py` to see the existing class structure.

- [ ] **Step 2: Add CRUD and refresh methods**

Add the following methods to the existing `StockPoolService` class. Keep `get_hot_stocks()` and `get_scan_universe()` unchanged. The service needs an additional constructor parameter for `StockPoolRepository` and `OpportunityScoringService`.

Add constructor parameters and new methods:

```python
# At the top of the file, add imports:
from repositories.stock_pool_repository import StockPoolRepository

# Modify __init__ to accept new dependencies:
def __init__(self, stock_repo, pool_repo=None, scoring_service=None):
    # ... existing init code stays ...
    self._pool_repo = pool_repo  # Optional: for custom pool CRUD
    self._scoring_service = scoring_service  # Optional: for scan-and-create

# Add these methods after the existing methods:

def create_pool(self, name: str, pool_type: str, symbols: list = None,
                filter_template: dict = None, refresh_interval: str = None,
                description: str = None) -> dict:
    """Create a stock pool (static or dynamic)."""
    if not self._pool_repo:
        raise RuntimeError("StockPoolRepository not configured")
    if pool_type == 'static' and not symbols:
        raise ValueError("Static pool requires symbols list")
    if pool_type == 'dynamic' and not filter_template:
        raise ValueError("Dynamic pool requires filter_template")

    return self._pool_repo.create({
        'name': name,
        'pool_type': pool_type,
        'symbols': symbols or [],
        'description': description,
        'filter_template': filter_template,
        'refresh_interval': refresh_interval,
    })

def get_pool(self, pool_id: int) -> dict:
    """Get a pool by ID. Raises ValueError if not found."""
    if not self._pool_repo:
        raise RuntimeError("StockPoolRepository not configured")
    pool = self._pool_repo.get_by_id(pool_id)
    if not pool:
        raise ValueError(f"Pool {pool_id} not found")
    return pool

def list_pools(self) -> list:
    """List all pools with summary info."""
    if not self._pool_repo:
        raise RuntimeError("StockPoolRepository not configured")
    pools = self._pool_repo.get_all()
    # Return summary: exclude full symbols list, include count
    result = []
    for p in pools:
        summary = {
            'id': p['id'],
            'name': p['name'],
            'pool_type': p['pool_type'],
            'description': p['description'],
            'symbol_count': len(p.get('symbols', [])),
            'refresh_interval': p.get('refresh_interval'),
            'last_refreshed_at': str(p['last_refreshed_at']) if p.get('last_refreshed_at') else None,
            'has_validation': p.get('last_validation') is not None,
            'created_at': str(p['created_at']),
        }
        result.append(summary)
    return result

def update_pool(self, pool_id: int, **kwargs) -> dict:
    """Update pool fields. Returns updated pool."""
    if not self._pool_repo:
        raise RuntimeError("StockPoolRepository not configured")
    updated = self._pool_repo.update(pool_id, kwargs)
    if not updated:
        raise ValueError(f"Pool {pool_id} not found")
    return updated

def delete_pool(self, pool_id: int) -> bool:
    """Delete a pool. Returns True if deleted."""
    if not self._pool_repo:
        raise RuntimeError("StockPoolRepository not configured")
    if not self._pool_repo.delete(pool_id):
        raise ValueError(f"Pool {pool_id} not found")
    return True

def refresh_pool(self, pool_id: int) -> dict:
    """Refresh a dynamic pool by re-running its filter_template."""
    if not self._pool_repo:
        raise RuntimeError("StockPoolRepository not configured")
    if not self._scoring_service:
        raise RuntimeError("OpportunityScoringService not configured")

    pool = self._pool_repo.get_by_id(pool_id)
    if not pool:
        raise ValueError(f"Pool {pool_id} not found")
    if pool['pool_type'] != 'dynamic':
        raise ValueError(f"Pool {pool_id} is static, cannot refresh")
    if not pool.get('filter_template'):
        raise ValueError(f"Pool {pool_id} has no filter_template")

    template = pool['filter_template']
    universe = self.get_hot_stocks()

    filters = {
        'technical': template.get('technical', []),
        'fundamental': template.get('fundamental', []),
    }
    scored = self._scoring_service.score_stocks(universe, filters)

    # Apply min_score filter
    min_score = template.get('min_score', 0)
    filtered = [s for s in scored if s.get('score', 0) >= min_score]

    # Apply max_risk_level filter
    max_risk = template.get('max_risk_level')
    if max_risk:
        risk_order = {'low': 0, 'medium': 1, 'high': 2}
        max_level = risk_order.get(max_risk, 2)
        filtered = [s for s in filtered if risk_order.get(s.get('risk_level', 'high'), 2) <= max_level]

    # Sort by score descending, take top_n
    filtered.sort(key=lambda s: s.get('score', 0), reverse=True)
    top_n = template.get('top_n', 50)
    symbols = [s['symbol'] for s in filtered[:top_n]]

    updated = self._pool_repo.update_symbols(pool_id, symbols)
    logger.info(f"Refreshed pool {pool_id}: {len(symbols)} symbols")
    return updated

def create_from_scan(self, name: str, pool_type: str, scan_params: dict,
                     refresh_interval: str = None, description: str = None) -> dict:
    """Screen stocks using OpportunityScoringService, then create a pool from the results."""
    if not self._scoring_service:
        raise RuntimeError("OpportunityScoringService not configured")

    universe = self.get_hot_stocks()
    filters = {
        'technical': scan_params.get('technical', []),
        'fundamental': scan_params.get('fundamental', []),
    }
    scored = self._scoring_service.score_stocks(universe, filters)

    min_score = scan_params.get('min_score', 0)
    filtered = [s for s in scored if s.get('score', 0) >= min_score]

    max_risk = scan_params.get('max_risk_level')
    if max_risk:
        risk_order = {'low': 0, 'medium': 1, 'high': 2}
        max_level = risk_order.get(max_risk, 2)
        filtered = [s for s in filtered if risk_order.get(s.get('risk_level', 'high'), 2) <= max_level]

    filtered.sort(key=lambda s: s.get('score', 0), reverse=True)
    top_n = scan_params.get('top_n', 50)
    symbols = [s['symbol'] for s in filtered[:top_n]]

    filter_template = scan_params if pool_type == 'dynamic' else None

    return self.create_pool(
        name=name,
        pool_type=pool_type,
        symbols=symbols,
        filter_template=filter_template,
        refresh_interval=refresh_interval if pool_type == 'dynamic' else None,
        description=description,
    )
```

- [ ] **Step 3: Verify existing tests still pass**

Run:
```bash
cd quantsys-v2 && python -m pytest tests/ -k "stock_pool" -v --timeout=30
```
Expected: All existing and new tests PASS. The constructor change is backward-compatible because `pool_repo` and `scoring_service` default to `None`.

- [ ] **Step 4: Commit**

```bash
git add quantsys-v2/services/stock_pool_service.py
git commit -m "feat(pool): extend StockPoolService with CRUD, refresh, scan-and-create"
```

---

### Task 4: PoolValidationService

**Files:**
- Create: `quantsys-v2/tests/services/test_pool_validation_service.py`
- Create: `quantsys-v2/services/pool_validation_service.py`

- [ ] **Step 1: Write failing tests**

```python
# quantsys-v2/tests/services/test_pool_validation_service.py
"""Tests for PoolValidationService."""
import json
import pytest
from unittest.mock import MagicMock, patch
from services.pool_validation_service import PoolValidationService


@pytest.fixture
def mock_pool_repo():
    repo = MagicMock()
    repo.get_by_id.return_value = {
        'id': 1,
        'name': '测试池',
        'pool_type': 'static',
        'symbols': ['600519.SH', '000858.SZ', '000001.SZ'],
    }
    return repo


@pytest.fixture
def mock_strategy_repo():
    repo = MagicMock()
    repo.get_all.return_value = [
        {'id': 53, 'name': '多因子波段策略v9', 'is_active': True},
        {'id': 54, 'name': 'RSI策略', 'is_active': True},
    ]
    return repo


@pytest.fixture
def service(mock_pool_repo, mock_strategy_repo):
    return PoolValidationService(
        pool_repo=mock_pool_repo,
        strategy_repo=mock_strategy_repo,
    )


class TestPoolValidationService:
    def test_validate_pool_not_found(self, service, mock_pool_repo):
        mock_pool_repo.get_by_id.return_value = None
        with pytest.raises(ValueError, match="Pool 999 not found"):
            service.validate_pool(999)

    def test_validate_pool_empty_symbols(self, service, mock_pool_repo):
        mock_pool_repo.get_by_id.return_value = {
            'id': 1, 'name': '空池', 'symbols': [],
        }
        with pytest.raises(ValueError, match="empty"):
            service.validate_pool(1)

    @patch('services.pool_validation_service.requests.post')
    def test_validate_pool_builds_correct_jobs(self, mock_post, service):
        """Verify jobs = strategy × symbol cartesian product."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'success': True,
            'data': {'results': [], 'errors': []},
        }
        service.validate_pool(1, strategy_ids=[53])

        call_args = mock_post.call_args
        body = call_args[1]['json'] if 'json' in call_args[1] else json.loads(call_args[1].get('data', '{}'))
        jobs = body['jobs']
        # 1 strategy × 3 symbols = 3 jobs
        assert len(jobs) == 3
        assert all(j['strategy_id'] == 53 for j in jobs)
        symbols_in_jobs = {j['symbol'] for j in jobs}
        assert symbols_in_jobs == {'600519.SH', '000858.SZ', '000001.SZ'}

    @patch('services.pool_validation_service.requests.post')
    def test_validate_pool_aggregates_by_strategy(self, mock_post, service, mock_pool_repo):
        """Test that results are aggregated per strategy and ranked."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'success': True,
            'data': {
                'results': [
                    {'strategy_id': 53, 'symbol': '600519.SH',
                     'annual_return': 0.15, 'sharpe_ratio': 2.0,
                     'max_drawdown': -0.05, 'win_rate': 0.7, 'profit_factor': 2.0},
                    {'strategy_id': 53, 'symbol': '000858.SZ',
                     'annual_return': 0.10, 'sharpe_ratio': 1.5,
                     'max_drawdown': -0.08, 'win_rate': 0.6, 'profit_factor': 1.5},
                    {'strategy_id': 53, 'symbol': '000001.SZ',
                     'annual_return': 0.12, 'sharpe_ratio': 1.8,
                     'max_drawdown': -0.06, 'win_rate': 0.65, 'profit_factor': 1.8},
                    {'strategy_id': 54, 'symbol': '600519.SH',
                     'annual_return': 0.05, 'sharpe_ratio': 0.8,
                     'max_drawdown': -0.12, 'win_rate': 0.45, 'profit_factor': 0.9},
                    {'strategy_id': 54, 'symbol': '000858.SZ',
                     'annual_return': 0.03, 'sharpe_ratio': 0.5,
                     'max_drawdown': -0.15, 'win_rate': 0.40, 'profit_factor': 0.7},
                    {'strategy_id': 54, 'symbol': '000001.SZ',
                     'annual_return': 0.04, 'sharpe_ratio': 0.6,
                     'max_drawdown': -0.13, 'win_rate': 0.42, 'profit_factor': 0.8},
                ],
                'errors': [],
            },
        }

        result = service.validate_pool(1)

        assert result['pool_id'] == 1
        assert result['strategies_tested'] == 2
        assert result['stocks_in_pool'] == 3
        # Strategy 53 should be ranked first (better metrics)
        assert result['best_strategy']['id'] == 53
        assert len(result['rankings']) == 2
        assert result['rankings'][0]['strategy_id'] == 53
        assert result['rankings'][1]['strategy_id'] == 54
        # recommended_pairs should exist (top 5 from best strategy)
        assert len(result['recommended_pairs']) <= 5

    @patch('services.pool_validation_service.requests.post')
    def test_validate_pool_uses_all_strategies_when_none_specified(self, mock_post, service):
        """When strategy_ids is None, all active strategies are used."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'success': True,
            'data': {'results': [], 'errors': []},
        }
        service.validate_pool(1, strategy_ids=None)

        call_args = mock_post.call_args
        body = call_args[1]['json']
        jobs = body['jobs']
        strategy_ids_used = {j['strategy_id'] for j in jobs}
        # Should use both strategies from mock_strategy_repo
        assert strategy_ids_used == {53, 54}
        # 2 strategies × 3 symbols = 6 jobs
        assert len(jobs) == 6

    @patch('services.pool_validation_service.requests.post')
    def test_validate_pool_saves_validation_result(self, mock_post, service, mock_pool_repo):
        """Verify last_validation is saved to the pool."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'success': True,
            'data': {
                'results': [
                    {'strategy_id': 53, 'symbol': '600519.SH',
                     'annual_return': 0.15, 'sharpe_ratio': 2.0,
                     'max_drawdown': -0.05, 'win_rate': 0.7, 'profit_factor': 2.0},
                ],
                'errors': [],
            },
        }
        service.validate_pool(1, strategy_ids=[53])
        mock_pool_repo.update_validation.assert_called_once()
        saved_validation = mock_pool_repo.update_validation.call_args[0][1]
        assert 'validated_at' in saved_validation
        assert 'best_strategy' in saved_validation
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd quantsys-v2 && python -m pytest tests/services/test_pool_validation_service.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'services.pool_validation_service'`

- [ ] **Step 3: Implement PoolValidationService**

```python
# quantsys-v2/services/pool_validation_service.py
"""Pool validation service - batch backtest strategies against a stock pool."""
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BACKTEST_API_URL = "http://127.0.0.1:5001/api/backtest/batch"
BACKTEST_TIMEOUT = 300  # 5 minutes


class PoolValidationService:
    """Orchestrates multi-strategy validation against a stock pool."""

    def __init__(self, pool_repo, strategy_repo):
        self._pool_repo = pool_repo
        self._strategy_repo = strategy_repo

    def validate_pool(self, pool_id: int, strategy_ids: List[int] = None,
                      start_date: str = None, end_date: str = None) -> Dict:
        """
        Run batch backtest: strategies × pool symbols, aggregate, rank, recommend.

        Args:
            pool_id: Target pool ID
            strategy_ids: Specific strategies to test (None = all active)
            start_date: Backtest start (default: 6 months ago)
            end_date: Backtest end (default: today)

        Returns:
            Dict with rankings, best_strategy, recommended_pairs
        """
        # 1. Load pool
        pool = self._pool_repo.get_by_id(pool_id)
        if not pool:
            raise ValueError(f"Pool {pool_id} not found")

        symbols = pool.get('symbols', [])
        if not symbols:
            raise ValueError(f"Pool {pool_id} is empty (no symbols)")

        # 2. Resolve strategies
        if strategy_ids:
            strategies = [
                s for s in self._strategy_repo.get_all()
                if s['id'] in strategy_ids
            ]
        else:
            strategies = self._strategy_repo.get_all(active_only=True)

        if not strategies:
            raise ValueError("No strategies available for validation")

        # 3. Resolve date range
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

        # 4. Build jobs: strategy × symbol cartesian product
        jobs = []
        for strategy in strategies:
            for symbol in symbols:
                jobs.append({
                    'strategy_id': strategy['id'],
                    'symbol': symbol,
                    'start_date': start_date,
                    'end_date': end_date,
                })

        logger.info(f"Pool validation: {len(strategies)} strategies × "
                     f"{len(symbols)} symbols = {len(jobs)} jobs")

        # 5. Call batch backtest API
        backtest_results = self._call_batch_backtest(jobs)

        # 6. Aggregate by strategy
        strategy_map = {s['id']: s['name'] for s in strategies}
        rankings = self._aggregate_by_strategy(backtest_results, strategy_map)

        # 7. Build result
        rankings.sort(key=lambda r: r['score'], reverse=True)
        best = rankings[0] if rankings else None

        # 8. Build recommended_pairs from best strategy's individual results
        recommended_pairs = []
        if best:
            best_results = [
                r for r in backtest_results
                if r.get('strategy_id') == best['strategy_id']
            ]
            best_results.sort(
                key=lambda r: self._calculate_score(r), reverse=True
            )
            for r in best_results[:5]:
                recommended_pairs.append({
                    'strategy_id': best['strategy_id'],
                    'strategy_name': best['name'],
                    'symbol': r['symbol'],
                    'expected_return': round(r.get('annual_return', 0) * 100, 2),
                    'win_rate': round(r.get('win_rate', 0) * 100, 2),
                    'sharpe': round(r.get('sharpe_ratio', 0), 2),
                })

        validation_result = {
            'pool_id': pool_id,
            'pool_name': pool['name'],
            'period': {'start': start_date, 'end': end_date},
            'strategies_tested': len(strategies),
            'stocks_in_pool': len(symbols),
            'best_strategy': best,
            'rankings': rankings,
            'recommended_pairs': recommended_pairs,
            'validated_at': datetime.now().isoformat(),
        }

        # 9. Save to pool
        self._pool_repo.update_validation(pool_id, validation_result)

        return validation_result

    def _call_batch_backtest(self, jobs: List[Dict]) -> List[Dict]:
        """Call POST /api/backtest/batch and return results list."""
        try:
            resp = requests.post(
                BACKTEST_API_URL,
                json={'jobs': jobs, 'initial_capital': 100000.0},
                timeout=BACKTEST_TIMEOUT,
            )
            if resp.status_code != 200:
                logger.error(f"Batch backtest failed: HTTP {resp.status_code}")
                return []

            data = resp.json()
            if not data.get('success'):
                logger.error(f"Batch backtest error: {data.get('error')}")
                return []

            results = data.get('data', {}).get('results', [])
            errors = data.get('data', {}).get('errors', [])
            if errors:
                logger.warning(f"Batch backtest had {len(errors)} errors")

            return results
        except requests.RequestException as e:
            logger.error(f"Batch backtest request failed: {e}")
            return []

    def _aggregate_by_strategy(self, results: List[Dict],
                                strategy_map: Dict[int, str]) -> List[Dict]:
        """Group results by strategy_id, compute averages and score."""
        grouped = defaultdict(list)
        for r in results:
            grouped[r.get('strategy_id')].append(r)

        rankings = []
        for strategy_id, items in grouped.items():
            n = len(items)
            avg_return = sum(i.get('annual_return', 0) for i in items) / n
            avg_sharpe = sum(i.get('sharpe_ratio', 0) for i in items) / n
            avg_drawdown = sum(i.get('max_drawdown', 0) for i in items) / n
            avg_win_rate = sum(i.get('win_rate', 0) for i in items) / n
            avg_profit_factor = sum(i.get('profit_factor', 0) for i in items) / n

            score = self._calculate_score({
                'annual_return': avg_return,
                'sharpe_ratio': avg_sharpe,
                'max_drawdown': avg_drawdown,
                'win_rate': avg_win_rate,
                'profit_factor': avg_profit_factor,
            })

            rankings.append({
                'strategy_id': strategy_id,
                'name': strategy_map.get(strategy_id, f'Strategy {strategy_id}'),
                'score': round(score, 2),
                'avg_return': round(avg_return * 100, 2),
                'avg_sharpe': round(avg_sharpe, 2),
                'avg_drawdown': round(avg_drawdown * 100, 2),
                'avg_win_rate': round(avg_win_rate * 100, 2),
                'avg_profit_factor': round(avg_profit_factor, 2),
                'stocks_tested': n,
            })

        return rankings

    def _calculate_score(self, metrics: Dict) -> float:
        """
        Comprehensive score (0-100). Same formula as StrategyValidationService.

        Weights: return 40%, sharpe 20%, drawdown 15%, win_rate 15%, profit_factor 10%
        """
        def normalize(value, low, high, reverse=False):
            clamped = max(low, min(high, value))
            ratio = (clamped - low) / (high - low) if high != low else 0.5
            return (1 - ratio) if reverse else ratio

        annual_return = metrics.get('annual_return', 0)
        sharpe = metrics.get('sharpe_ratio', 0)
        drawdown = metrics.get('max_drawdown', 0)
        win_rate = metrics.get('win_rate', 0)
        profit_factor = metrics.get('profit_factor', 0)

        score = (
            normalize(annual_return, -0.5, 0.5) * 0.40
            + normalize(sharpe, -2, 3) * 0.20
            + normalize(drawdown, -0.5, 0.0, reverse=True) * 0.15
            + normalize(win_rate, 0, 1) * 0.15
            + normalize(profit_factor, 0, 3) * 0.10
        ) * 100

        return max(0, min(100, score))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd quantsys-v2 && python -m pytest tests/services/test_pool_validation_service.py -v
```
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/services/pool_validation_service.py quantsys-v2/tests/services/test_pool_validation_service.py
git commit -m "feat(pool): add PoolValidationService for multi-strategy batch comparison"
```

---

### Task 5: API Routes

**Files:**
- Create: `quantsys-v2/tests/api/test_pools_routes.py`
- Create: `quantsys-v2/api/routes/pools.py`

- [ ] **Step 1: Write failing route tests**

```python
# quantsys-v2/tests/api/test_pools_routes.py
"""Tests for /api/pools/* routes."""
import json
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def client():
    """Create a test Flask client with pools blueprint."""
    from flask import Flask
    from api.routes.pools import pools_bp

    app = Flask(__name__)
    app.register_blueprint(pools_bp)

    # Mock the shared services
    with patch('api.routes.pools.stock_pool_service') as mock_svc, \
         patch('api.routes.pools.pool_validation_service') as mock_val:

        mock_svc.create_pool.return_value = {
            'id': 1, 'name': '测试池', 'pool_type': 'static',
            'symbols': ['600519.SH'], 'description': None,
            'filter_template': None, 'refresh_interval': None,
            'last_refreshed_at': None, 'last_validation': None,
            'created_at': '2026-06-01', 'updated_at': '2026-06-01',
        }
        mock_svc.list_pools.return_value = [
            {'id': 1, 'name': '测试池', 'pool_type': 'static', 'symbol_count': 1},
        ]
        mock_svc.get_pool.return_value = {
            'id': 1, 'name': '测试池', 'pool_type': 'static',
            'symbols': ['600519.SH'],
        }
        mock_svc.update_pool.return_value = {
            'id': 1, 'name': '更新后', 'pool_type': 'static',
            'symbols': ['600519.SH'],
        }
        mock_svc.delete_pool.return_value = True
        mock_svc.refresh_pool.return_value = {
            'id': 1, 'name': '动态池', 'pool_type': 'dynamic',
            'symbols': ['600519.SH', '000858.SZ'],
        }
        mock_svc.create_from_scan.return_value = {
            'id': 2, 'name': '扫描池', 'pool_type': 'dynamic',
            'symbols': ['600519.SH', '000858.SZ'],
            'filter_template': {'min_score': 60},
        }

        mock_val.validate_pool.return_value = {
            'pool_id': 1, 'pool_name': '测试池',
            'best_strategy': {'id': 53, 'score': 82.5},
            'rankings': [], 'recommended_pairs': [],
        }

        with app.test_client() as c:
            # Store mocks on client for assertions
            c._mock_svc = mock_svc
            c._mock_val = mock_val
            yield c


class TestPoolsRoutes:
    def test_create_pool(self, client):
        resp = client.post('/api/pools', json={
            'name': '测试池',
            'poolType': 'static',
            'symbols': ['600519.SH'],
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['id'] == 1

    def test_create_pool_missing_name(self, client):
        resp = client.post('/api/pools', json={
            'poolType': 'static',
            'symbols': ['600519.SH'],
        })
        assert resp.status_code == 400

    def test_list_pools(self, client):
        resp = client.get('/api/pools')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert len(data['data']) == 1

    def test_get_pool(self, client):
        resp = client.get('/api/pools/1')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['id'] == 1

    def test_update_pool(self, client):
        resp = client.put('/api/pools/1', json={'name': '更新后'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_delete_pool(self, client):
        resp = client.delete('/api/pools/1')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_refresh_pool(self, client):
        resp = client.post('/api/pools/1/refresh')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_validate_pool(self, client):
        resp = client.post('/api/pools/1/validate', json={
            'strategyIds': [53, 54],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['best_strategy']['id'] == 53

    def test_scan_and_create(self, client):
        resp = client.post('/api/pools/scan-and-create', json={
            'name': '扫描池',
            'poolType': 'dynamic',
            'filter': {'minScore': 60, 'fundamental': ['pe_low']},
            'refreshInterval': 'weekly',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True
        assert data['data']['id'] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd quantsys-v2 && python -m pytest tests/api/test_pools_routes.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'api.routes.pools'`

- [ ] **Step 3: Implement pools.py routes**

```python
# quantsys-v2/api/routes/pools.py
"""Stock pool management API routes."""
import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

pools_bp = Blueprint('pools', __name__)

# Lazy imports to avoid circular dependencies at module level.
# These are resolved at request time from api.shared.
_stock_pool_service = None
_pool_validation_service = None


def _get_services():
    global _stock_pool_service, _pool_validation_service
    if _stock_pool_service is None:
        from api.shared import stock_pool_service, pool_validation_service
        _stock_pool_service = stock_pool_service
        _pool_validation_service = pool_validation_service
    return _stock_pool_service, _pool_validation_service


# Expose for test patching
def __getattr__(name):
    if name == 'stock_pool_service':
        svc, _ = _get_services()
        return svc
    if name == 'pool_validation_service':
        _, val = _get_services()
        return val
    raise AttributeError(name)


def _convert_filter_keys(filter_dict):
    """Convert camelCase filter keys to snake_case."""
    if not filter_dict:
        return filter_dict
    mapping = {
        'minScore': 'min_score',
        'maxRiskLevel': 'max_risk_level',
        'topN': 'top_n',
    }
    result = {}
    for k, v in filter_dict.items():
        result[mapping.get(k, k)] = v
    return result


@pools_bp.route('/api/pools', methods=['POST'])
def create_pool():
    svc, _ = _get_services()
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body required'}), 400

    name = data.get('name')
    pool_type = data.get('poolType') or data.get('pool_type')
    if not name or not pool_type:
        return jsonify({'success': False, 'error': 'name and poolType are required'}), 400

    try:
        pool = svc.create_pool(
            name=name,
            pool_type=pool_type,
            symbols=data.get('symbols'),
            filter_template=_convert_filter_keys(data.get('filterTemplate') or data.get('filter_template')),
            refresh_interval=data.get('refreshInterval') or data.get('refresh_interval'),
            description=data.get('description'),
        )
        return jsonify({'success': True, 'data': pool}), 201
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Create pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools', methods=['GET'])
def list_pools():
    svc, _ = _get_services()
    try:
        pools = svc.list_pools()
        return jsonify({'success': True, 'data': pools})
    except Exception as e:
        logger.error(f"List pools failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>', methods=['GET'])
def get_pool(pool_id):
    svc, _ = _get_services()
    try:
        pool = svc.get_pool(pool_id)
        return jsonify({'success': True, 'data': pool})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Get pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>', methods=['PUT'])
def update_pool(pool_id):
    svc, _ = _get_services()
    data = request.get_json() or {}
    try:
        pool = svc.update_pool(
            pool_id,
            name=data.get('name'),
            symbols=data.get('symbols'),
            description=data.get('description'),
        )
        return jsonify({'success': True, 'data': pool})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Update pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>', methods=['DELETE'])
def delete_pool(pool_id):
    svc, _ = _get_services()
    try:
        svc.delete_pool(pool_id)
        return jsonify({'success': True, 'message': f'Pool {pool_id} deleted'})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Delete pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>/refresh', methods=['POST'])
def refresh_pool(pool_id):
    svc, _ = _get_services()
    try:
        pool = svc.refresh_pool(pool_id)
        return jsonify({'success': True, 'data': pool})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Refresh pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/<int:pool_id>/validate', methods=['POST'])
def validate_pool(pool_id):
    _, val_svc = _get_services()
    data = request.get_json() or {}
    try:
        result = val_svc.validate_pool(
            pool_id=pool_id,
            strategy_ids=data.get('strategyIds') or data.get('strategy_ids'),
            start_date=data.get('startDate') or data.get('start_date'),
            end_date=data.get('endDate') or data.get('end_date'),
        )
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Validate pool failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@pools_bp.route('/api/pools/scan-and-create', methods=['POST'])
def scan_and_create():
    svc, _ = _get_services()
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Request body required'}), 400

    name = data.get('name')
    pool_type = data.get('poolType') or data.get('pool_type')
    filter_params = data.get('filter') or data.get('filterTemplate') or data.get('filter_template')

    if not name or not pool_type or not filter_params:
        return jsonify({'success': False, 'error': 'name, poolType, and filter are required'}), 400

    try:
        pool = svc.create_from_scan(
            name=name,
            pool_type=pool_type,
            scan_params=_convert_filter_keys(filter_params),
            refresh_interval=data.get('refreshInterval') or data.get('refresh_interval'),
            description=data.get('description'),
        )
        return jsonify({'success': True, 'data': pool}), 201
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Scan and create failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd quantsys-v2 && python -m pytest tests/api/test_pools_routes.py -v
```
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/api/routes/pools.py quantsys-v2/tests/api/test_pools_routes.py
git commit -m "feat(pool): add /api/pools/* routes for pool CRUD and validation"
```

---

### Task 6: Wire Services and Register Blueprint

**Files:**
- Modify: `quantsys-v2/api/shared.py`
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: Read current shared.py**

Read `quantsys-v2/api/shared.py` to see the current service wiring and `__all__` list.

- [ ] **Step 2: Add StockPoolRepository and PoolValidationService to shared.py**

Add these imports and instances near the existing service wiring (after the `scoring_service` line):

```python
# Add to imports section:
from repositories.stock_pool_repository import StockPoolRepository
from services.pool_validation_service import PoolValidationService
from repositories.strategy_repository import StrategyRepository

# Add after scoring_service line in the service wiring section:
pool_repo = StockPoolRepository()
pool_validation_service = PoolValidationService(
    pool_repo=pool_repo,
    strategy_repo=StrategyRepository(),
)

# Update the existing stock_pool_service line to pass new dependencies:
# Change: stock_pool_service = StockPoolService(ds.stock)
# To:
stock_pool_service = StockPoolService(ds.stock, pool_repo=pool_repo, scoring_service=scoring_service)
```

Add the new exports to `__all__`:
```python
__all__ = [
    'ds',
    'strategy_service',
    'stock_pool_service',
    'pool_repo',
    'pool_validation_service',
    'factor_adapter',
    'scoring_service',
    'sector_rotation_service',
]
```

- [ ] **Step 3: Read current server.py**

Read `quantsys-v2/api/server.py` to see the blueprint registration pattern.

- [ ] **Step 4: Register pools blueprint in server.py**

Add in the `create_app()` function, following the alphabetical pattern of existing registrations. Find an appropriate location (after `pipeline_bp` and before `portfolio_bp`):

```python
    from api.routes.pools import pools_bp
    app.register_blueprint(pools_bp)
```

- [ ] **Step 5: Verify server starts without errors**

Run:
```bash
cd quantsys-v2 && timeout 5 python -c "from api.server import create_app; app = create_app(); print('OK')" 2>&1 || true
```
Expected: `OK` (no import errors)

- [ ] **Step 6: Commit**

```bash
git add quantsys-v2/api/shared.py quantsys-v2/api/server.py
git commit -m "feat(pool): wire StockPoolRepository and PoolValidationService into API server"
```

---

### Task 7: QuantV2Client Extension (TypeScript)

**Files:**
- Modify: `src/infrastructure/quant/quant-v2-client.ts`

- [ ] **Step 1: Read current quant-v2-client.ts**

Read `src/infrastructure/quant/quant-v2-client.ts` to find `fetchV2`, `V2_API_BASE`, and existing function patterns.

- [ ] **Step 2: Add pool API functions**

Add the following named export functions at the bottom of the file, following the existing pattern (e.g., `batchValidateStrategies`, `scanOpportunities`):

```typescript
// ── Stock Pool Management ──

export interface PoolCreateParams {
  name: string;
  pool_type: 'static' | 'dynamic';
  symbols?: string[];
  filter_template?: Record<string, unknown>;
  refresh_interval?: 'daily' | 'weekly';
  description?: string;
}

export interface PoolValidateParams {
  strategy_ids?: number[];
  start_date?: string;
  end_date?: string;
}

export interface PoolScanCreateParams {
  name: string;
  pool_type: 'static' | 'dynamic';
  filter: Record<string, unknown>;
  refresh_interval?: 'daily' | 'weekly';
  description?: string;
}

export async function createPool(params: PoolCreateParams): Promise<any> {
  const url = `${V2_API_BASE}/api/pools`;
  return fetchV2(url, { method: 'POST', body: params });
}

export async function listPools(): Promise<any> {
  const url = `${V2_API_BASE}/api/pools`;
  return fetchV2(url, { method: 'GET' });
}

export async function getPool(poolId: number): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}`;
  return fetchV2(url, { method: 'GET' });
}

export async function updatePool(poolId: number, data: Partial<PoolCreateParams>): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}`;
  return fetchV2(url, { method: 'PUT', body: data });
}

export async function deletePool(poolId: number): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}`;
  return fetchV2(url, { method: 'DELETE' });
}

export async function refreshPool(poolId: number): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}/refresh`;
  return fetchV2(url, { method: 'POST' });
}

export async function validatePool(poolId: number, params?: PoolValidateParams): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/${poolId}/validate`;
  return fetchV2(url, { method: 'POST', body: params ?? {} });
}

export async function scanAndCreatePool(params: PoolScanCreateParams): Promise<any> {
  const url = `${V2_API_BASE}/api/pools/scan-and-create`;
  return fetchV2(url, { method: 'POST', body: params });
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run:
```bash
npx tsc --noEmit src/infrastructure/quant/quant-v2-client.ts 2>&1 | head -20
```
Expected: No errors (or only pre-existing errors unrelated to pool functions)

- [ ] **Step 4: Commit**

```bash
git add src/infrastructure/quant/quant-v2-client.ts
git commit -m "feat(pool): add pool management API methods to QuantV2Client"
```

---

### Task 8: pool_manage Agent Tool

**Files:**
- Create: `src/infrastructure/tools/pool/pool-manage-tool.ts`

- [ ] **Step 1: Create the tool file**

```typescript
// src/infrastructure/tools/pool/pool-manage-tool.ts
/**
 * Pool management tool — CRUD, refresh, scan-and-create for stock pools.
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import {
  createPool,
  listPools,
  getPool,
  updatePool,
  deletePool,
  refreshPool,
  scanAndCreatePool,
} from "../../quant/quant-v2-client.js";

export const poolManageTool: ToolDefinition = {
  name: "pool_manage",
  label: "股票池管理",
  description:
    "管理股票池：创建静态/动态池、列出所有池、查看详情、更新、删除、刷新动态池、筛选建池。" +
    "动态池保存筛选条件(filter_template)，可定时自动刷新。" +
    "筛选建池(scan_create)：执行多因子扫描后自动创建池子。",
  parameters: Type.Object({
    action: Type.Union(
      [
        Type.Literal("create"),
        Type.Literal("list"),
        Type.Literal("get"),
        Type.Literal("update"),
        Type.Literal("delete"),
        Type.Literal("refresh"),
        Type.Literal("scan_create"),
      ],
      { description: "操作类型" },
    ),
    pool_id: Type.Optional(
      Type.Number({ description: "池子ID (get/update/delete/refresh 需要)" }),
    ),
    name: Type.Optional(
      Type.String({ description: "池子名称 (create/scan_create 需要)" }),
    ),
    pool_type: Type.Optional(
      Type.Union([Type.Literal("static"), Type.Literal("dynamic")], {
        description: "池子类型 (create/scan_create 需要)",
      }),
    ),
    symbols: Type.Optional(
      Type.Array(Type.String(), {
        description: "股票代码列表 (create static 时手动指定)",
      }),
    ),
    filter: Type.Optional(
      Type.Object(
        {
          min_score: Type.Optional(
            Type.Number({ description: "最低综合评分 (0-100)" }),
          ),
          max_risk_level: Type.Optional(
            Type.String({ description: "最大风险等级: low/medium/high" }),
          ),
          technical: Type.Optional(
            Type.Array(Type.String(), {
              description:
                "技术面条件: rsi_oversold, macd_golden_cross, bollinger_breakout, volume_surge",
            }),
          ),
          fundamental: Type.Optional(
            Type.Array(Type.String(), {
              description:
                "基本面条件: pe_low, roe_high, gross_margin_high, debt_ratio_low",
            }),
          ),
          top_n: Type.Optional(
            Type.Number({ description: "取排名前N只 (默认50)" }),
          ),
        },
        { description: "筛选条件 (scan_create/create dynamic 需要)" },
      ),
    ),
    refresh_interval: Type.Optional(
      Type.Union([Type.Literal("daily"), Type.Literal("weekly")], {
        description: "动态池刷新周期",
      }),
    ),
    description: Type.Optional(
      Type.String({ description: "池子描述" }),
    ),
  }),
  execute: async (_toolCallId: string, rawParams: any) => {
    const { action, pool_id, name, pool_type, symbols, filter,
            refresh_interval, description } = rawParams;

    try {
      let result: any;

      switch (action) {
        case "create":
          if (!name || !pool_type) {
            return _err("create 需要 name 和 pool_type 参数");
          }
          result = await createPool({
            name,
            pool_type,
            symbols,
            filter_template: filter,
            refresh_interval,
            description,
          });
          break;

        case "list":
          result = await listPools();
          break;

        case "get":
          if (!pool_id) return _err("get 需要 pool_id 参数");
          result = await getPool(pool_id);
          break;

        case "update":
          if (!pool_id) return _err("update 需要 pool_id 参数");
          result = await updatePool(pool_id, { name, symbols, description } as any);
          break;

        case "delete":
          if (!pool_id) return _err("delete 需要 pool_id 参数");
          result = await deletePool(pool_id);
          break;

        case "refresh":
          if (!pool_id) return _err("refresh 需要 pool_id 参数");
          result = await refreshPool(pool_id);
          break;

        case "scan_create":
          if (!name || !pool_type || !filter) {
            return _err("scan_create 需要 name, pool_type, filter 参数");
          }
          result = await scanAndCreatePool({
            name,
            pool_type,
            filter,
            refresh_interval,
            description,
          });
          break;

        default:
          return _err(`未知操作: ${action}`);
      }

      const data = result?.data ?? result;
      const text = _formatResult(action, data);
      return { content: [{ type: "text" as const, text }], details: undefined };
    } catch (error) {
      return _err(
        `操作失败: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  },
};

function _err(msg: string) {
  return { content: [{ type: "text" as const, text: `❌ ${msg}` }], details: undefined };
}

function _formatResult(action: string, data: any): string {
  if (!data) return "操作完成（无返回数据）";

  switch (action) {
    case "list": {
      const pools = Array.isArray(data) ? data : [];
      if (pools.length === 0) return "📋 暂无股票池";
      const lines = pools.map(
        (p: any) =>
          `  [${p.id}] ${p.name} (${p.pool_type}) — ${p.symbol_count}只股票` +
          (p.refresh_interval ? ` — 刷新: ${p.refresh_interval}` : ""),
      );
      return `📋 股票池列表 (${pools.length}个):\n${lines.join("\n")}`;
    }

    case "get": {
      const syms = data.symbols || [];
      let text = `📊 池子详情: ${data.name} (${data.pool_type})\n`;
      text += `  成员 (${syms.length}只): ${syms.slice(0, 10).join(", ")}`;
      if (syms.length > 10) text += ` ... 等${syms.length}只`;
      if (data.filter_template) {
        text += `\n  筛选条件: ${JSON.stringify(data.filter_template)}`;
      }
      if (data.last_validation?.best_strategy) {
        const best = data.last_validation.best_strategy;
        text += `\n  最优策略: ${best.name || best.id} (评分: ${best.score})`;
      }
      return text;
    }

    case "create":
    case "scan_create": {
      const syms = data.symbols || [];
      return (
        `✅ 池子已创建: [${data.id}] ${data.name} (${data.pool_type})\n` +
        `  入池 ${syms.length} 只股票: ${syms.slice(0, 10).join(", ")}` +
        (syms.length > 10 ? ` ... 等${syms.length}只` : "")
      );
    }

    case "refresh": {
      const syms = data.symbols || [];
      return `🔄 池子已刷新: ${data.name}\n  当前 ${syms.length} 只股票`;
    }

    case "delete":
      return `🗑️ 池子已删除`;

    case "update":
      return `✏️ 池子已更新: ${data.name}`;

    default:
      return JSON.stringify(data, null, 2);
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
npx tsc --noEmit src/infrastructure/tools/pool/pool-manage-tool.ts 2>&1 | head -20
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/infrastructure/tools/pool/pool-manage-tool.ts
git commit -m "feat(pool): add pool_manage agent tool"
```

---

### Task 9: pool_validate Agent Tool

**Files:**
- Create: `src/infrastructure/tools/pool/pool-validate-tool.ts`

- [ ] **Step 1: Create the tool file**

```typescript
// src/infrastructure/tools/pool/pool-validate-tool.ts
/**
 * Pool validation tool — run multi-strategy batch backtest against a stock pool.
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { validatePool } from "../../quant/quant-v2-client.js";

export const poolValidateTool: ToolDefinition = {
  name: "pool_validate",
  label: "股票池策略验证",
  description:
    "对股票池执行多策略批量回测对比：每个策略在池内所有股票上跑回测，" +
    "按综合评分(收益率40%+夏普20%+回撤15%+胜率15%+盈亏比10%)排名，" +
    "自动推荐最优策略+股票组合(top 5)。" +
    "strategy_ids为空时使用所有活跃策略，时间范围默认近6个月。",
  parameters: Type.Object({
    pool_id: Type.Number({ description: "股票池ID (必需)" }),
    strategy_ids: Type.Optional(
      Type.Array(Type.Number(), {
        description: "策略ID列表，为空则使用所有活跃策略",
      }),
    ),
    start_date: Type.Optional(
      Type.String({ description: "回测起始日期 YYYY-MM-DD (默认近6个月)" }),
    ),
    end_date: Type.Optional(
      Type.String({ description: "回测结束日期 YYYY-MM-DD (默认今天)" }),
    ),
  }),
  execute: async (_toolCallId: string, rawParams: any) => {
    const { pool_id, strategy_ids, start_date, end_date } = rawParams;

    if (!pool_id) {
      return {
        content: [{ type: "text" as const, text: "❌ 需要 pool_id 参数" }],
        details: undefined,
      };
    }

    try {
      const resp = await validatePool(pool_id, {
        strategy_ids,
        start_date,
        end_date,
      });
      const data = resp?.data ?? resp;
      const text = _formatValidation(data);
      return { content: [{ type: "text" as const, text }], details: undefined };
    } catch (error) {
      return {
        content: [
          {
            type: "text" as const,
            text: `❌ 验证失败: ${error instanceof Error ? error.message : String(error)}`,
          },
        ],
        details: undefined,
      };
    }
  },
};

function _formatValidation(data: any): string {
  if (!data) return "验证完成（无数据）";

  const lines: string[] = [];
  lines.push(`📊 策略验证结果: ${data.pool_name || `Pool #${data.pool_id}`}`);
  lines.push(
    `  验证期间: ${data.period?.start} ~ ${data.period?.end}`,
  );
  lines.push(
    `  测试: ${data.strategies_tested} 个策略 × ${data.stocks_in_pool} 只股票`,
  );
  lines.push("");

  // Best strategy
  const best = data.best_strategy;
  if (best) {
    lines.push(`🏆 最优策略: ${best.name || `#${best.strategy_id}`}`);
    lines.push(
      `  综合评分: ${best.score} | 平均收益: ${best.avg_return}% | 胜率: ${best.avg_win_rate}% | 夏普: ${best.avg_sharpe}`,
    );
    lines.push("");
  }

  // Rankings table
  const rankings = data.rankings || [];
  if (rankings.length > 0) {
    lines.push("📈 策略排名:");
    lines.push("  排名 | 策略名称 | 评分 | 收益% | 胜率% | 夏普");
    lines.push("  " + "-".repeat(60));
    rankings.forEach((r: any, i: number) => {
      lines.push(
        `  ${String(i + 1).padStart(2)}   | ${(r.name || `#${r.strategy_id}`).padEnd(16)} | ${String(r.score).padStart(5)} | ${String(r.avg_return).padStart(6)} | ${String(r.avg_win_rate).padStart(5)} | ${String(r.avg_sharpe).padStart(5)}`,
      );
    });
    lines.push("");
  }

  // Recommended pairs
  const pairs = data.recommended_pairs || [];
  if (pairs.length > 0) {
    lines.push("💡 推荐组合 (最优策略 + 最佳股票):");
    pairs.forEach((p: any, i: number) => {
      lines.push(
        `  ${i + 1}. ${p.symbol} — 预期收益: ${p.expected_return}% | 胜率: ${p.win_rate}% | 夏普: ${p.sharpe}`,
      );
    });
  }

  return lines.join("\n");
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
npx tsc --noEmit src/infrastructure/tools/pool/pool-validate-tool.ts 2>&1 | head -20
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/infrastructure/tools/pool/pool-validate-tool.ts
git commit -m "feat(pool): add pool_validate agent tool"
```

---

### Task 10: Register Tools in index.ts

**Files:**
- Modify: `src/infrastructure/tools/index.ts`

- [ ] **Step 1: Read current index.ts**

Read `src/infrastructure/tools/index.ts` to find the imports section and `allCustomTools` array.

- [ ] **Step 2: Add import statements**

Add after the `L2.6 ZigZag` import block (around line 38):

```typescript
// L2.7 股票池管理
import { poolManageTool } from "./pool/pool-manage-tool.js";
import { poolValidateTool } from "./pool/pool-validate-tool.js";
```

- [ ] **Step 3: Add tools to allCustomTools array**

Add after the `swingPointsTool` entry in the `allCustomTools` array (around line 128):

```typescript
  // L2.7 股票池管理
  poolManageTool,                   // pool_manage - 股票池 CRUD + 筛选建池
  poolValidateTool,                 // pool_validate - 多策略批量回测验证
```

- [ ] **Step 4: Verify TypeScript compiles**

Run:
```bash
npx tsc --noEmit 2>&1 | head -20
```
Expected: No errors (or only pre-existing errors)

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/tools/index.ts
git commit -m "feat(pool): register pool_manage and pool_validate tools in tool registry"
```

---

### Task 11: End-to-End Smoke Test

- [ ] **Step 1: Start quantsys-v2 backend**

Run:
```bash
cd quantsys-v2 && python start_all.py &
sleep 5
```
Expected: REST API on port 5001 healthy

- [ ] **Step 2: Test create static pool**

Run:
```bash
curl -s -X POST http://127.0.0.1:5001/api/pools \
  -H "Content-Type: application/json" \
  -d '{"name": "E2E测试静态池", "poolType": "static", "symbols": ["600519.SH", "000858.SZ"]}' \
  | python -m json.tool
```
Expected: `{ "success": true, "data": { "id": ..., "name": "E2E测试静态池", "symbols": [...] } }`

- [ ] **Step 3: Test list pools**

Run:
```bash
curl -s http://127.0.0.1:5001/api/pools | python -m json.tool
```
Expected: Array with at least the pool just created

- [ ] **Step 4: Test get pool detail**

Run (replace `1` with actual pool_id from step 2):
```bash
curl -s http://127.0.0.1:5001/api/pools/1 | python -m json.tool
```
Expected: Full pool details with symbols

- [ ] **Step 5: Test delete pool**

Run:
```bash
curl -s -X DELETE http://127.0.0.1:5001/api/pools/1 | python -m json.tool
```
Expected: `{ "success": true, "message": "Pool 1 deleted" }`

- [ ] **Step 6: Run all Python tests**

Run:
```bash
cd quantsys-v2 && python -m pytest tests/repositories/test_stock_pool_repository.py tests/services/test_pool_validation_service.py tests/api/test_pools_routes.py -v
```
Expected: All tests PASS

- [ ] **Step 7: Run TypeScript build**

Run:
```bash
npm run build 2>&1 | tail -5
```
Expected: Build succeeds with no errors

- [ ] **Step 8: Commit and tag**

```bash
git add -A
git commit -m "test(pool): verify end-to-end stock pool pipeline"
```
