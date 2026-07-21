# Phase 3: Performance Optimization Plan

**Timeline**: 5-6 weeks  
**Created**: 2026-06-16  
**Status**: In Progress

## Overview

This document outlines the detailed implementation plan for Phase 3 performance optimization, addressing N+1 queries, batch operations, caching, and async/sync issues.

## Performance Issues Identified

### 1. N+1 Query Patterns

#### Issue 1.1: Portfolio Holdings N+1 Query
**File**: `adapters/outbound/repositories/portfolio_repository.py:58-68`  
**Problem**: Subquery in SELECT clause executes once per row
```sql
SELECT
    t.symbol,
    (SELECT tt.name FROM quant.trades tt  -- ❌ Subquery per row!
     WHERE tt.symbol = t.symbol AND tt.trade_date <= %s
     ORDER BY tt.trade_date DESC LIMIT 1) AS name,
    SUM(...) AS quantity
FROM quant.trades t
```

**Solution**: Use window functions
```sql
SELECT DISTINCT ON (symbol)
    symbol,
    name,
    quantity
FROM (
    SELECT 
        t.symbol,
        FIRST_VALUE(tt.name) OVER (
            PARTITION BY t.symbol 
            ORDER BY tt.trade_date DESC
        ) AS name,
        SUM(CASE WHEN t.action = 'buy' THEN t.quantity ELSE -t.quantity END) 
            OVER (PARTITION BY t.symbol) AS quantity
    FROM quant.trades t
    LEFT JOIN quant.trades tt ON t.symbol = tt.symbol AND tt.trade_date <= %s
    WHERE t.trade_date <= %s
) subq
WHERE quantity > 0
```

**Impact**: 70% reduction in query time for portfolios with 10+ holdings  
**Priority**: High  
**Effort**: 4 hours

---

#### Issue 1.2: Loop-based Multi-symbol Queries
**File**: `adapters/inbound/api/routes/analysis.py:94-105`  
**Problem**: 3 DB calls per symbol in loop
```python
for symbol in symbols:
    factors = ds.factor.get_latest_factors(symbol)      # DB call #1
    stock_info = ds.stock.get_by_symbol(symbol)         # DB call #2
    kline = ds.kline.get_latest_daily_kline(symbol)     # DB call #3
```

**Solution**: Implement batch query methods
```python
factors_batch = ds.factor.get_latest_factors_batch(symbols)
stocks_batch = ds.stock.get_by_symbols_batch(symbols)
klines_batch = ds.kline.get_latest_daily_klines_batch(symbols)

for symbol in symbols:
    results.append({
        'symbol': symbol,
        'factors': factors_batch.get(symbol),
        'stock_info': stocks_batch.get(symbol),
        'kline': klines_batch.get(symbol)
    })
```

**Impact**: 60% reduction in API response time for compare endpoint  
**Priority**: Critical  
**Effort**: 12 hours

---

### 2. Missing Batch Query Methods

#### Task 2.1: Add batch methods to StockRepository
**File**: `adapters/outbound/repositories/stock_repository.py`  
**Methods to add**:
- `get_by_symbols_batch(symbols: List[str]) -> Dict[str, Dict]`

**Implementation**:
```python
def get_by_symbols_batch(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Batch query for multiple stocks
    
    Args:
        symbols: List of stock symbols
        
    Returns:
        Dict mapping symbol to stock info
    """
    if not symbols:
        return {}
    
    for symbol in symbols:
        self._validate_symbol(symbol)
    
    query = "SELECT * FROM quant.stocks WHERE symbol = ANY(%s)"
    
    cursor = self._get_cursor()
    cursor.execute(query, (symbols,))
    rows = cursor.fetchall()
    cursor.close()
    
    result = {}
    for row in rows:
        stock_data = self._to_domain_object(row)
        result[stock_data['symbol']] = stock_data
    
    return result
```

**Priority**: Critical  
**Effort**: 3 hours

---

#### Task 2.2: Add batch methods to KlineRepository
**File**: `adapters/outbound/repositories/kline_repository.py`  
**Methods to add**:
- `get_latest_daily_klines_batch(symbols: List[str]) -> Dict[str, Dict]`
- `get_daily_klines_batch(symbols: List[str], start_date: str, end_date: str) -> Dict[str, List[Dict]]`

**Implementation**:
```python
def get_latest_daily_klines_batch(self, symbols: List[str]) -> Dict[str, Optional[Dict]]:
    """
    Batch query for latest daily klines of multiple stocks
    
    Args:
        symbols: List of stock symbols
        
    Returns:
        Dict mapping symbol to latest kline data
    """
    if not symbols:
        return {}
    
    # Normalize symbols (remove suffix)
    normalized_symbols = [s.split('.')[0] if '.' in s else s for s in symbols]
    
    query = """
        SELECT DISTINCT ON (symbol) *
        FROM quant.daily_klines
        WHERE symbol = ANY(%s)
        ORDER BY symbol, trade_date DESC
    """
    
    cursor = self._get_cursor()
    cursor.execute(query, (normalized_symbols,))
    rows = cursor.fetchall()
    cursor.close()
    
    result = {}
    for row in rows:
        kline_data = dict(row)
        result[kline_data['symbol']] = kline_data
    
    # Map back to original symbols (with suffixes)
    final_result = {}
    for original_symbol in symbols:
        normalized = original_symbol.split('.')[0] if '.' in original_symbol else original_symbol
        final_result[original_symbol] = result.get(normalized)
    
    return final_result
```

**Priority**: Critical  
**Effort**: 4 hours

---

#### Task 2.3: Update FactorRepository to use existing batch method
**File**: `adapters/outbound/repositories/factor_repository.py`  
**Status**: ✅ Batch method already exists (`get_factors_batch`)  
**Action**: Ensure callers use the batch method

**Priority**: Medium  
**Effort**: 2 hours (refactoring callers)

---

### 3. Refactor API Routes to Use Batch Queries

#### Task 3.1: Refactor `/api/stocks/compare` endpoint
**File**: `adapters/inbound/api/routes/analysis.py:82-112`

**Before**:
```python
results = []
for symbol in symbols:
    factors = ds.factor.get_latest_factors(symbol)
    stock_info = ds.stock.get_by_symbol(symbol)
    kline = ds.kline.get_latest_daily_kline(symbol)
    results.append({...})
```

**After**:
```python
# Batch queries
factors_batch = ds.factor.get_factors_batch(symbols, datetime.now().strftime('%Y-%m-%d'))
stocks_batch = ds.stock.get_by_symbols_batch(symbols)
klines_batch = ds.kline.get_latest_daily_klines_batch(symbols)

results = []
for symbol in symbols:
    results.append(sanitize_for_json({
        'symbol': symbol,
        'name': stocks_batch.get(symbol, {}).get('name', ''),
        'market': stocks_batch.get(symbol, {}).get('market', ''),
        'current_price': klines_batch.get(symbol, {}).get('close'),
        'factors': factors_batch.get(symbol, {})
    }))
```

**Priority**: Critical  
**Effort**: 2 hours

---

#### Task 3.2: Add batch query helper to shared module
**File**: `adapters/inbound/api/shared.py`  
**Purpose**: Reusable batch query function for common patterns

```python
def batch_query_stock_data(symbols: List[str], include_factors: bool = True) -> Dict[str, Dict]:
    """
    Batch query stock data for multiple symbols
    
    Args:
        symbols: List of stock symbols
        include_factors: Whether to include factor data
        
    Returns:
        Dict mapping symbol to combined data
    """
    if not symbols:
        return {}
    
    stocks_batch = ds.stock.get_by_symbols_batch(symbols)
    klines_batch = ds.kline.get_latest_daily_klines_batch(symbols)
    
    result = {}
    for symbol in symbols:
        result[symbol] = {
            'symbol': symbol,
            'stock_info': stocks_batch.get(symbol),
            'kline': klines_batch.get(symbol)
        }
        
        if include_factors:
            factors = ds.factor.get_latest_factors(symbol)
            result[symbol]['factors'] = factors
    
    return result
```

**Priority**: Medium  
**Effort**: 3 hours

---

### 4. Add Caching Layer

#### Task 4.1: Cache frequently accessed stock info
**Files**: 
- `adapters/outbound/repositories/stock_repository.py`
- `infrastructure/cache/cache_service.py`

**Strategy**: Cache stock basic info (name, market, industry) with 1-day TTL

```python
def get_by_symbol(self, symbol: str, fields: List[str] = None) -> Optional[Dict[str, Any]]:
    """Get stock by symbol with caching"""
    cache_key = f"stock:{symbol}"
    
    # Try cache first
    cached = cache_service.get(cache_key)
    if cached:
        return cached
    
    # Query database
    result = self._query_stock(symbol, fields)
    
    # Cache result
    if result:
        cache_service.set(cache_key, result, ttl=86400)  # 1 day
    
    return result
```

**Priority**: Medium  
**Effort**: 6 hours

---

#### Task 4.2: Cache latest kline data
**File**: `adapters/outbound/repositories/kline_repository.py`  
**Strategy**: Cache latest kline with 5-minute TTL during trading hours

```python
def get_latest_daily_kline(self, symbol: str) -> Optional[Dict]:
    """Get latest kline with smart caching"""
    cache_key = f"kline:latest:{symbol}"
    
    cached = cache_service.get(cache_key)
    if cached:
        return cached
    
    result = self._query_latest_kline(symbol)
    
    if result:
        # 5 min TTL during trading hours, 1 hour after close
        ttl = 300 if is_trading_hours() else 3600
        cache_service.set(cache_key, result, ttl=ttl)
    
    return result
```

**Priority**: Medium  
**Effort**: 4 hours

---

### 5. Resolve Async/Sync Mixing

#### Task 5.1: Audit async usage
**Findings**:
- `AsyncCacheService` exists but rarely used
- `benchmark_service.py` calls `asyncio.run()` in sync code (anti-pattern)
- Flask is synchronous, blocks async benefits

**Options**:
1. **Remove async** - Simplify to pure sync (recommended for Flask)
2. **Full async** - Migrate to FastAPI (major refactor)
3. **Hybrid** - Keep async for I/O-bound tasks only

**Recommendation**: Option 1 (Remove async) - Flask is sync, adding async adds complexity without benefits

**Priority**: Low  
**Effort**: 8 hours

---

#### Task 5.2: Remove asyncio.run() anti-patterns
**File**: `application/services/benchmark_service.py`

**Before**:
```python
async_result = asyncio.run(self._benchmark_async_queries(...))
```

**After**:
```python
# Convert async method to sync or remove
result = self._benchmark_queries(...)
```

**Priority**: Low  
**Effort**: 4 hours

---

## Implementation Schedule

### Week 1-2: Critical Batch Queries
- [ ] Task 2.1: Add `get_by_symbols_batch` to StockRepository (3h)
- [ ] Task 2.2: Add `get_latest_daily_klines_batch` to KlineRepository (4h)
- [ ] Task 3.1: Refactor `/api/stocks/compare` to use batch (2h)
- [ ] Task 1.2: Fix other loop-based queries in analysis.py (6h)
- [ ] Testing: Integration tests for batch methods (8h)

**Total Week 1-2**: 23 hours

### Week 3-4: N+1 Query Fixes
- [ ] Task 1.1: Fix portfolio holdings N+1 query (4h)
- [ ] Task 3.2: Add batch query helper to shared module (3h)
- [ ] Audit other repositories for N+1 patterns (6h)
- [ ] Testing: Performance benchmarks before/after (6h)

**Total Week 3-4**: 19 hours

### Week 5: Caching Layer
- [ ] Task 4.1: Cache stock info (6h)
- [ ] Task 4.2: Cache latest kline (4h)
- [ ] Cache invalidation strategy (4h)
- [ ] Testing: Cache hit rate monitoring (4h)

**Total Week 5**: 18 hours

### Week 6: Async/Sync Cleanup
- [ ] Task 5.1: Audit and document async usage (4h)
- [ ] Task 5.2: Remove asyncio.run() anti-patterns (4h)
- [ ] Final performance testing (8h)
- [ ] Documentation updates (4h)

**Total Week 6**: 20 hours

---

## Success Metrics

| Metric | Before | Target | Measurement |
|--------|--------|--------|-------------|
| `/api/stocks/compare` response time (5 stocks) | ~800ms | <200ms | Load test |
| Portfolio holdings query time (20 holdings) | ~500ms | <150ms | Query profiling |
| Stock info cache hit rate | 0% | >70% | Cache stats |
| Database connection pool utilization | N/A | <60% | Monitoring |

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Batch queries return too much data | High memory usage | Add pagination, limit batch size to 100 symbols |
| Cache invalidation bugs | Stale data shown | Add cache version tags, manual invalidation API |
| Breaking API contract | Client errors | Add feature flags, gradual rollout |

---

## Testing Strategy

1. **Unit Tests**: Each new batch method gets dedicated tests
2. **Integration Tests**: End-to-end API tests comparing batch vs loop
3. **Performance Tests**: Load tests with 100 concurrent requests
4. **Regression Tests**: Ensure results match before/after optimization

---

## Next Steps

1. ✅ Create this plan document
2. ⏳ Implement Task 2.1: StockRepository batch method
3. ⏳ Implement Task 2.2: KlineRepository batch method
4. ⏳ Refactor analysis.py to use batch queries
5. ⏳ Write integration tests

---

**Last Updated**: 2026-06-16  
**Owner**: Development Team
