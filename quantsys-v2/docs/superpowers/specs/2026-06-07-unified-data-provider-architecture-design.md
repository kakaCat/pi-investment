# Unified Data Provider Architecture Design

**Date:** 2026-06-07  
**Status:** Design Approved  
**Author:** Claude (Kiro)

## Executive Summary

Migrate all direct `akshare` imports in service files to a unified `DataProviderManager` architecture. This design consolidates existing multi-source patterns (`RealtimeQuoteService`, `quote_providers`, `financial_providers`) into a single infrastructure layer at `infrastructure/data_providers/`, providing automatic failover, health tracking, and source attribution for all external data access.

## Background

### Current State Problems

1. **Scattered Data Access**: 9 service files directly `import akshare`, bypassing any abstraction layer
2. **Inconsistent Patterns**: `services/quote_providers/` and `services/financial_providers/` exist but are not used consistently
3. **No Unified Failover**: Only realtime quotes have multi-source failover via `RealtimeQuoteService`
4. **Architecture Violation**: Providers are in `services/` layer instead of `infrastructure/` layer
5. **Duplicate Code**: Each service implements its own error handling and retry logic

### Services Requiring Migration

| Service File | Direct akshare Usage | Functions |
|--------------|---------------------|-----------|
| `stock_data_service.py` | 3 methods | announcements, news, batch_quotes |
| `dividend_data_source.py` | 1 method | dividends |
| `dividend_service.py` | 3 methods | dividends, calendar, high_dividend_screen |
| `valuation_data_service.py` | 1 method | valuation |
| `lhb_data_source.py` | 2 methods | lhb_stock, lhb_daily |
| `market_data_service.py` | 5 methods | overview, sectors, fund_flow, etc. |
| `trading_calendar_service.py` | 1 method | trading_calendar |
| `strategy_code_service.py` | 2 methods | financial data injection |
| `financial_analysis_service.py` | 3 methods | income, balance, cashflow |

**Total:** 21 methods across 9 service files

## Design Goals

1. **Unified Architecture**: Single infrastructure layer for all external data access
2. **Automatic Failover**: Multi-source failover for all data types (not just quotes)
3. **Health Tracking**: Cache provider success/failure stats to identify channel issues
4. **Source Attribution**: All returned data includes `source` field indicating which provider succeeded
5. **Zero Config**: Hardcoded provider priorities in code (no YAML/config files)
6. **Backward Compatible**: Service method signatures and API responses unchanged (except adding `source` field)


## Architecture Design

### Directory Structure

```
infrastructure/
└── data_providers/
    ├── __init__.py
    ├── manager.py              # DataProviderManager (unified coordinator)
    ├── base.py                 # BaseDataProvider interface
    ├── models.py               # Data models (QuoteData, FinancialData, etc.)
    └── providers/
        ├── __init__.py
        ├── quote/              # Realtime quotes
        │   ├── __init__.py
        │   ├── sina.py         # Moved from services/quote_providers/
        │   ├── eastmoney.py
        │   ├── akshare.py
        │   ├── tencent.py
        │   └── netease.py
        ├── financial/          # Financial data
        │   ├── __init__.py
        │   ├── eastmoney.py    # Moved from services/financial_providers/
        │   ├── akshare.py
        │   └── sina.py
        ├── dividend/           # Dividend data
        │   ├── __init__.py
        │   └── akshare.py
        ├── market/             # Market data
        │   ├── __init__.py
        │   ├── eastmoney.py
        │   └── akshare.py
        └── stock/              # Stock basic data
            ├── __init__.py
            └── akshare.py

services/                       # Business logic layer
├── stock_data_service.py       # Calls DataProviderManager
├── market_data_service.py      # Calls DataProviderManager
├── dividend_service.py         # Calls DataProviderManager
└── ...

# Directories to DELETE after migration:
❌ services/quote_providers/
❌ services/financial_providers/
❌ data_sources/
❌ services/realtime_quote_service.py (merged into DataProviderManager)
```

### Core Components

#### 1. Data Models (models.py)

All data models include `source` and `timestamp` fields for tracking data origin.

**QuoteData** - Realtime quote (existing, keep unchanged)
**FinancialData** - Financial statements and indicators
**DividendData** - Dividend records and calendar
**MarketData** - Market overview, sectors, fund flow, LHB
**StockData** - Announcements, news, trading calendar

#### 2. Provider Interface (base.py)

Abstract base classes for each domain:
- `BaseDataProvider` - Generic provider interface
- `QuoteProvider` - Realtime quotes
- `FinancialProvider` - Financial data
- `DividendProvider` - Dividend data
- `MarketProvider` - Market data
- `StockProvider` - Stock basic data

#### 3. DataProviderManager (manager.py)

Unified coordinator with hardcoded provider priorities:

```python
class DataProviderManager:
    def __init__(self):
        # Hardcoded priorities (no config files)
        self.quote_providers = [Sina(), Eastmoney(), Akshare(), ...]
        self.financial_providers = [Eastmoney(), Akshare(), Sina()]
        self.dividend_providers = [Akshare()]
        self.market_providers = [Eastmoney(), Akshare()]
        self.stock_providers = [Akshare()]
        
        # Health tracking
        self.provider_stats = {}
    
    def get_quote(self, symbol: str) -> dict:
        return self._try_providers(self.quote_providers, 'get_quote', symbol)
    
    def _try_providers(self, providers, method_name, *args, **kwargs):
        for provider in providers:
            try:
                result = provider.method(*args, **kwargs)
                if result:
                    self._record_success(provider.name)
                    return {'success': True, 'data': result, 'source': provider.name}
                self._record_failure(provider.name)
            except Exception:
                self._record_failure(provider.name)
        return {'success': False, 'error': 'All providers failed'}
```


## Migration Strategy

### Phase 1: Create New Architecture

1. Create `infrastructure/data_providers/` directory structure
2. Implement `base.py` - unified provider interface
3. Implement `models.py` - data models
4. Implement `manager.py` - DataProviderManager core

**Deliverables:**
- ✅ Base infrastructure in place
- ✅ Manager with hardcoded provider priorities
- ✅ Health tracking system

### Phase 2: Migrate Providers

1. Move `services/quote_providers/` → `infrastructure/data_providers/providers/quote/`
2. Move `services/financial_providers/` → `infrastructure/data_providers/providers/financial/`
3. Create new providers for `dividend/`, `market/`, `stock/` domains
4. Update all providers to inherit from new base classes

**Deliverables:**
- ✅ All providers in `infrastructure/data_providers/providers/`
- ✅ All providers inherit from `BaseDataProvider` subclasses
- ✅ Old provider directories marked for deletion

### Phase 3: Refactor Services

Refactor 9 service files (21 methods total).

**Before:**
```python
def get_announcements(self, symbol: str):
    import akshare as ak
    df = ak.stock_notice_report(symbol=symbol)
    return {'success': True, 'data': df.to_dict('records')}
```

**After:**
```python
def __init__(self):
    from infrastructure.data_providers import get_data_provider_manager
    self.provider_manager = get_data_provider_manager()

def get_announcements(self, symbol: str):
    result = self.provider_manager.get_announcements(symbol)
    
    if result['success']:
        stock_data = result['data']
        return {
            'success': True,
            'data': {
                'symbol': stock_data.symbol,
                'announcements': stock_data.data,
                'total': stock_data.total,
                'source': stock_data.source,  # ✅ New field
                'update_time': stock_data.timestamp
            }
        }
    
    return {'success': False, 'error': result['error']}
```

**Deliverables:**
- ✅ All 9 service files refactored
- ✅ No direct `import akshare` in services
- ✅ All responses include `source` field

### Phase 4: Cleanup

1. Delete `services/quote_providers/`
2. Delete `services/financial_providers/`
3. Delete `data_sources/` (old multi-source architecture)
4. Delete `services/realtime_quote_service.py` (merged into DataProviderManager)

**Deliverables:**
- ✅ Clean architecture with single data provider infrastructure
- ✅ No duplicate code or parallel implementations


## Error Handling

### Three-Layer Error Handling

**Layer 1: Provider Level**
- Return `None` on failure (triggers failover)
- Log warnings for debugging
- No exceptions should bubble up

**Layer 2: Manager Level**
- Try all providers in priority order
- Track success/failure stats
- Return structured error when all providers fail

**Layer 3: Service Level**
- Convert manager errors to user-friendly messages
- Log errors for monitoring
- Maintain backward-compatible response format

### Example Error Flow

```python
# Layer 1: Provider
class AkshareStockProvider(StockProvider):
    def get_announcements(self, symbol: str) -> Optional[StockData]:
        try:
            import akshare as ak
            df = ak.stock_notice_report(symbol=symbol)
            if df is None or df.empty:
                return None  # Trigger failover
            return StockData(...)
        except Exception as e:
            logger.warning(f"{self.name} failed: {e}")
            return None  # Trigger failover

# Layer 2: Manager
def get_announcements(self, symbol: str) -> dict:
    for provider in self.stock_providers:
        result = provider.get_announcements(symbol)
        if result:
            self._record_success(provider.name)
            return {'success': True, 'data': result, 'source': result.source}
        self._record_failure(provider.name)
    
    return {'success': False, 'error': 'All providers failed'}

# Layer 3: Service
def get_announcements(self, symbol: str) -> Dict[str, Any]:
    result = self.provider_manager.get_announcements(symbol)
    if not result['success']:
        logger.error(f"Failed to get announcements for {symbol}")
        return {
            'success': False,
            'error': '暂时无法获取股票公告，请稍后再试',
            'data': None
        }
    return {'success': True, 'data': {...}}
```


## Testing Strategy

### Unit Tests (Provider Layer)

```python
def test_akshare_stock_provider_get_announcements():
    provider = AkshareStockProvider()
    result = provider.get_announcements('600519')
    
    assert result is not None
    assert result.symbol == '600519'
    assert result.source == 'akshare'
    assert len(result.data) > 0

def test_provider_returns_none_on_failure():
    provider = AkshareStockProvider()
    result = provider.get_announcements('INVALID')
    assert result is None
```

### Integration Tests (Manager Layer)

```python
def test_manager_failover_mechanism():
    manager = DataProviderManager()
    with patch.object(manager.stock_providers[0], 'get_announcements', return_value=None):
        result = manager.get_announcements('600519')
    assert result['success'] is True
    assert result['source'] != manager.stock_providers[0].name

def test_manager_all_providers_fail():
    manager = DataProviderManager()
    for provider in manager.stock_providers:
        with patch.object(provider, 'get_announcements', return_value=None):
            pass
    result = manager.get_announcements('600519')
    assert result['success'] is False

def test_provider_stats_tracking():
    manager = DataProviderManager()
    for _ in range(10):
        manager.get_announcements('600519')
    stats = manager.get_provider_health()
    assert len(stats) > 0
```

### End-to-End Tests (Service → API)

```python
def test_get_announcements_endpoint(client):
    response = client.get('/api/stock/600519/announcements')
    assert response.status_code == 200
    data = response.json()
    assert data['success'] is True
    assert 'source' in data['data']
    assert data['data']['total'] > 0

def test_invalid_symbol_handling(client):
    response = client.get('/api/stock/INVALID/announcements')
    assert response.status_code == 200
    data = response.json()
    assert data['success'] is False
```

### Coverage Targets

- **Provider Layer:** 90%+ (core data fetching logic)
- **Manager Layer:** 95%+ (failover logic must be fully tested)
- **Service Layer:** 80%+ (business logic)
- **End-to-End:** 100% (all API endpoints)


## Impact Analysis

### Breaking Changes

**None.** This is an internal refactoring with no breaking changes:
- ✅ API endpoints unchanged
- ✅ Service method signatures unchanged
- ✅ Response data format unchanged (only adds `source` field)
- ✅ CLI commands unchanged

### New Features

- ✅ Multi-source failover for all data types (not just quotes)
- ✅ Provider health tracking (`get_provider_health()`)
- ✅ Source attribution (all responses include `source` field)
- ✅ Automatic retry logic (no manual error handling in services)

### Performance Impact

**Positive:**
- Faster recovery from provider failures (automatic failover)
- Better observability (health stats identify slow/failing providers)

**Neutral:**
- Negligible overhead from failover logic (< 100ms per request)
- No additional latency when primary provider succeeds

## Success Criteria

1. ✅ All 9 service files migrated (no direct `import akshare`)
2. ✅ All 21 methods refactored to use DataProviderManager
3. ✅ All tests passing (unit, integration, e2e)
4. ✅ Test coverage targets met (90%+ for providers, 95%+ for manager)
5. ✅ Old directories deleted (`services/quote_providers/`, `services/financial_providers/`, `data_sources/`)
6. ✅ API responses include `source` field
7. ✅ Provider health stats accessible via `get_provider_health()`
8. ✅ Zero regressions (all existing functionality works)

## Future Enhancements

**Out of scope for this migration:**
- Adding new data sources (eastmoney, tencent for non-quote data)
- Circuit breaker pattern (prevent repeated calls to failing providers)
- Response caching (TTL-based cache for expensive queries)
- Provider priority adjustment based on success rate

These can be added incrementally after the unified architecture is in place.

## References

- Existing implementation: `services/realtime_quote_service.py` (pattern to replicate)
- Provider examples: `services/quote_providers/` (to be moved)
- CLAUDE.md: Architecture layers and testing requirements
