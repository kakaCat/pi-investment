# Enhanced Financial Data Service Design

**Date:** 2026-06-04  
**Author:** Claude (Kiro AI Agent)  
**Status:** Draft

## Overview

为财务数据服务添加类似实时行情（quote_v2）的多数据源增强特性：熔断器、缓存、source 参数控制。采用包装器模式，零侵入现有代码，实现渐进式迁移。

## Goals

1. **提升性能** — 通过缓存减少重复 API 调用，缓存命中率 > 70%
2. **提升可靠性** — 通过熔断器防止持续调用失败的数据源
3. **提升灵活性** — 通过 source 参数让用户控制缓存策略
4. **保持兼容** — 现有代码零改动，V1/V2 并行运行

## Non-Goals

- 不迁移到 DataSourceManager（保持架构独立）
- 不修改现有 FinancialDataService 代码（包装器模式）
- 不实现分层缓存（统一 TTL 简化实现）
- 不添加本地数据库持久化（财务数据仍从数据源实时获取）

## Design

### Architecture

```
┌─────────────────────────────────────────────┐
│   API Layer (routes/financials_v2.py)      │
│   GET /api/v2/stock/<symbol>/financials    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  EnhancedFinancialDataService (new)        │
│  ┌─────────────────────────────────────┐   │
│  │ DataSourceCache (ttl=300s)          │   │
│  │ max_size=1000, LRU eviction         │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │ CircuitBreaker per provider         │   │
│  │ failure_threshold=3, timeout=60s    │   │
│  └─────────────────────────────────────┘   │
│  ┌─────────────────────────────────────┐   │
│  │ Statistics tracking                 │   │
│  │ cache hits, provider stats, etc     │   │
│  └─────────────────────────────────────┘   │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  FinancialDataService (existing, no change) │
│  - Multi-provider fallback                  │
│  - Data validation                          │
│  - Providers: Tushare → Sina Web → Sina    │
│              → Eastmoney                    │
└─────────────────────────────────────────────┘
```

### Key Components

#### 1. EnhancedFinancialDataService

```python
class EnhancedFinancialDataService:
    """Enhanced financial data service with caching and circuit breaker.
    
    Features:
    - Cache (5 min TTL)
    - Circuit breaker (per provider)
    - source parameter (auto/fresh/cache_only)
    - Statistics tracking
    """
    
    def __init__(
        self,
        base_service: Optional[FinancialDataService] = None,
        cache_ttl: int = 300,
        circuit_breaker_cooldown: int = 60
    ):
        self.base_service = base_service or FinancialDataService()
        self.cache = DataSourceCache(ttl=cache_ttl, max_size=1000)
        self.circuit_breakers = {
            provider.name: CircuitBreaker(
                failure_threshold=3,
                timeout=circuit_breaker_cooldown
            )
            for provider in self.base_service.providers
        }
        self.stats = {...}  # Statistics tracking
    
    def get_financial_data(
        self,
        symbol: str,
        statement_type: str = 'all',
        periods: int = 4,
        source: str = 'auto'
    ) -> FinancialData:
        """Get financial data with caching and circuit breaker."""
```

#### 2. Source Parameter Behavior

| source | Behavior |
|--------|----------|
| `auto` (default) | Cache first → If miss, call data source with circuit breaker → Update cache |
| `fresh` | Skip cache → Call data source with circuit breaker → Update cache |
| `cache_only` | Only check cache → If miss, raise error (no data source call) |

#### 3. Circuit Breaker Logic

```python
def _get_data_with_circuit_breaker(self, symbol, statement_type, periods):
    """Fetch data with circuit breaker protection."""
    
    # Skip providers with open circuit breakers
    available_providers = [
        p for p in self.base_service.providers
        if self.circuit_breakers[p.name].is_available()
    ]
    
    # If all breakers are open, try to recover the oldest one
    if not available_providers:
        self._try_recover_oldest_breaker()
        available_providers = [...]
    
    # Try each available provider
    for provider in available_providers:
        try:
            data = provider.get_financial_data(...)
            if self.base_service._is_valid_financial_data(data):
                self.circuit_breakers[provider.name].record_success()
                return data
            else:
                self.circuit_breakers[provider.name].record_failure()
        except Exception:
            self.circuit_breakers[provider.name].record_failure()
    
    # All providers failed
    raise AllProvidersFailedError(...)
```

#### 4. Cache Key Strategy

```python
def _make_cache_key(self, symbol, statement_type, periods):
    """Generate cache key.
    
    Format: financial:{symbol}:{statement_type}:{periods}
    Example: financial:600519:all:4
    """
    return f"financial:{symbol}:{statement_type}:{periods}"
```

### API Integration

#### New V2 Endpoint

```python
# quantsys-v2/api/routes/financials_v2.py

@financials_v2_bp.route('/api/v2/stock/<symbol>/financials', methods=['GET'])
def get_financial_data_v2(symbol):
    """Get financial data V2 with caching and circuit breaker.
    
    Query Parameters:
        statement_type: income/balance/cash_flow/all (default: all)
        periods: number of periods (default: 4)
        source: auto/fresh/cache_only (default: auto)
    
    Response:
        {
            "success": true,
            "data": {...},
            "cached": true,
            "source": "sina_web"
        }
    """
    statement_type = request.args.get('statement_type', 'all')
    periods = int(request.args.get('periods', 4))
    source = request.args.get('source', 'auto')
    
    service = get_enhanced_financial_service()
    data = service.get_financial_data(symbol, statement_type, periods, source)
    
    return jsonify({
        'success': True,
        'data': data.to_dict(),
        'cached': service.was_cache_hit(),
        'source': data.source
    })
```

#### Statistics Endpoint

```python
@financials_v2_bp.route('/api/v2/financials/stats', methods=['GET'])
def get_stats():
    """Get service statistics.
    
    Response:
        {
            "success": true,
            "stats": {
                "total_requests": 100,
                "cache_hits": 70,
                "cache_hit_rate": "70.0%",
                "success_count": 95,
                "failure_count": 5,
                "provider_stats": {...},
                "circuit_breaker_status": {...},
                "cache_stats": {...}
            }
        }
    """
```

#### Cache Management Endpoints

```python
@financials_v2_bp.route('/api/v2/financials/cache/clear', methods=['POST'])
def clear_cache():
    """Clear cache."""

@financials_v2_bp.route('/api/v2/financials/stats/reset', methods=['POST'])
def reset_stats():
    """Reset statistics (keep cache and circuit breaker state)."""
```

### TypeScript Client Integration

```typescript
// src/infrastructure/adapters/quant/quant-v2-client.ts

export async function getFinancials(
  symbol: string,
  reportType?: 'income' | 'balance' | 'cash_flow' | 'all',
  periods: number = 4,
  source: 'auto' | 'fresh' | 'cache_only' = 'auto'
): Promise<FinancialData> {
  const url = `${V2_API_BASE}/api/v2/stock/${symbol}/financials`;
  const params = new URLSearchParams({
    statement_type: reportType || 'all',
    periods: periods.toString(),
    source
  });
  
  const response = await fetch(`${url}?${params}`, {
    signal: AbortSignal.timeout(V2_TIMEOUT_MS)
  });
  
  if (!response.ok) {
    throw new QuantV2Error(`财务数据查询失败 (${response.status})`, response.status);
  }
  
  const result = await response.json();
  return result.data;
}
```

### Tool Layer Integration

```typescript
// src/infrastructure/tools/data/fetch-financial-tool.ts

parameters: Type.Object({
  symbol: Type.String({ description: "股票代码" }),
  dataType: Type.Optional(...),
  reportType: Type.Optional(...),
  periods: Type.Optional(...),
  years: Type.Optional(...),
  source: Type.Optional(Type.Union([
    Type.Literal("auto"),
    Type.Literal("fresh"),
    Type.Literal("cache_only")
  ], {
    description: "数据源策略：auto=缓存优先（默认），fresh=强制刷新，cache_only=仅缓存"
  }))
}),

execute: async (_toolCallId, params) => {
  const { symbol, dataType, reportType, periods, years, source = 'auto' } = params;
  const data = await getFinancials(symbol, reportType, periods, source);
  // ...
}
```

## Error Handling

### Cache Errors

```python
# cache_only mode with cache miss
if source == 'cache_only' and not cached:
    raise FinancialDataCacheError(
        f"缓存未命中: {symbol}",
        suggestion="使用 source='auto' 或 'fresh' 以调用数据源"
    )
```

### Circuit Breaker Errors

```python
# All circuit breakers are open
if not available_providers:
    cooldown_times = {
        name: breaker.get_remaining_cooldown()
        for name, breaker in self.circuit_breakers.items()
        if breaker.state == CircuitState.OPEN
    }
    raise AllCircuitBreakersOpenError(
        "所有数据源熔断器都已打开",
        cooldown_times=cooldown_times,
        suggestion="请等待熔断器恢复或使用 reset_circuit_breakers() 手动重置"
    )
```

### Degradation Strategy

When all providers fail:

**Option 1: Return stale cache (recommended)**
```python
if expired_cache := self._get_expired_cache(cache_key):
    logger.warning(f"所有数据源失败，返回过期缓存: {symbol}")
    expired_cache.metadata['stale'] = True
    return expired_cache
```

**Option 2: Raise exception (default)**
```python
raise AllProvidersFailedError(
    f"所有数据源都无法获取 {symbol} 的财务数据",
    errors=provider_errors
)
```

## Configuration

### Default Values

```python
DEFAULT_CACHE_TTL = 300                    # 5 minutes
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 3      # 3 failures
DEFAULT_CIRCUIT_BREAKER_TIMEOUT = 60       # 60 seconds
DEFAULT_CACHE_MAX_SIZE = 1000              # 1000 entries
```

### Environment Variables (optional)

```bash
FINANCIAL_CACHE_TTL=300
FINANCIAL_CIRCUIT_BREAKER_THRESHOLD=3
FINANCIAL_CIRCUIT_BREAKER_TIMEOUT=60
FINANCIAL_CACHE_MAX_SIZE=1000
```

## Migration Strategy

### Phase 1: Create Enhanced Service (no impact)
- Create `EnhancedFinancialDataService` class
- Write unit tests
- No changes to existing code

### Phase 2: Add V2 API (parallel run)
- Create `/api/v2/stock/<symbol>/financials` endpoint
- Keep existing API endpoints unchanged
- Both APIs run in parallel

### Phase 3: TypeScript Client Migration
- Update `getFinancials()` to call v2 API
- Add `source` parameter support
- Backward compatible (source parameter optional, default 'auto')

### Phase 4: Tool Layer Migration
- Update `data_fetch_financial` tool to expose `source` parameter
- Agent can choose to use or ignore the parameter

### Phase 5: Validation and Monitoring
- Compare v1 and v2 API response consistency
- Monitor cache hit rate and circuit breaker status
- Collect performance metrics

### Phase 6: Deprecate V1 (optional)
- Mark old API as deprecated
- Guide users to use v2
- Keep v1 as fallback

## Testing

### Unit Tests

```python
# quantsys-v2/tests/services/test_enhanced_financial_data_service.py

class TestEnhancedFinancialDataService:
    def test_cache_hit_on_second_request(self)
    def test_fresh_mode_bypasses_cache(self)
    def test_cache_only_mode_fails_on_miss(self)
    def test_circuit_breaker_opens_after_failures(self)
    def test_circuit_breaker_skips_open_providers(self)
    def test_circuit_breaker_recovers_after_timeout(self)
    def test_fallback_to_second_provider_on_first_failure(self)
    def test_all_providers_failed_raises_exception(self)
    def test_stats_tracking(self)
    def test_cache_hit_rate_calculation(self)
```

### Integration Tests

```python
# quantsys-v2/tests/api/test_financials_v2_routes.py

class TestFinancialsV2Routes:
    def test_get_financial_data_auto_mode(self)
    def test_get_financial_data_fresh_mode(self)
    def test_get_financial_data_cache_only_mode(self)
    def test_stats_endpoint(self)
    def test_clear_cache_endpoint(self)
```

### E2E Tests

See `docs/testing/enhanced-financial-data-e2e-test.md`

### Performance Benchmarks

- Cache hit time: < 10ms
- First request time: < 3s
- Cache hit rate: > 70% (normal usage)
- Circuit breaker overhead: < 1ms

## File Changes

### New Files

```
quantsys-v2/
├── services/enhanced_financial_data_service.py
├── api/routes/financials_v2.py
└── tests/
    ├── services/test_enhanced_financial_data_service.py
    └── api/test_financials_v2_routes.py

docs/
├── superpowers/specs/2026-06-04-enhanced-financial-service-design.md
└── testing/enhanced-financial-data-e2e-test.md
```

### Modified Files

```
quantsys-v2/api/server.py                  # Register financials_v2_bp
src/infrastructure/adapters/quant/
  ├── quant-v2-client.ts                   # Add source parameter
  └── types.ts                             # Add source type
src/infrastructure/tools/data/
  └── fetch-financial-tool.ts              # Add source parameter
```

### Unchanged Files (important)

```
quantsys-v2/services/
  ├── financial_data_service.py            # No changes
  └── financial_providers.py               # No changes
```

## Backward Compatibility

### API Compatibility
- Existing API endpoints remain unchanged
- V2 endpoints use different paths (`/api/v2/...`)
- Old code continues to use `FinancialDataService` directly

### Parameter Compatibility
- `source` parameter is optional, default `'auto'`
- Calls without `source` parameter behave exactly like existing code

### Data Format Compatibility
- `FinancialData` object structure unchanged
- Only metadata fields added in response (`cached`, `source`, etc.)

## Monitoring

### Key Metrics

- **Cache hit rate** — Target: > 70%
- **Average response time** — Target: < 10ms (cache hit), < 3s (cache miss)
- **Provider success rate** — Target: > 90% per provider
- **Circuit breaker open count** — Alert if > 2 providers open simultaneously

### Logging

```python
# Circuit breaker state changes
logger.warning(f"熔断器打开: {provider.name}, 失败次数: {failure_count}")
logger.info(f"熔断器恢复: {provider.name}")

# Low cache hit rate
if cache_hit_rate < 0.3 and total_requests > 100:
    logger.warning(f"缓存命中率过低: {cache_hit_rate:.2%}")

# Low provider success rate
if provider_success_rate < 0.5 and provider_requests > 10:
    logger.error(f"数据源 {provider.name} 成功率过低: {provider_success_rate:.2%}")
```

## Success Criteria

✅ Cache hit rate > 70% in normal usage  
✅ Response time < 10ms for cache hits  
✅ Zero impact on existing code (no regressions)  
✅ Circuit breaker successfully prevents cascade failures  
✅ All unit tests pass (coverage > 90%)  
✅ All integration tests pass  
✅ E2E test demonstrates complete data flow  

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Cache invalidation issues | Use conservative TTL (5 min), provide `fresh` mode |
| Circuit breaker too aggressive | Use proven config (3 failures, 60s timeout) from quote_v2 |
| Memory leak from unbounded cache | Use max_size=1000 with LRU eviction |
| Breaking existing code | Wrapper pattern, no changes to existing code |
| V2 API inconsistent with V1 | Comprehensive integration tests comparing v1/v2 responses |

## Future Enhancements (out of scope)

- Migrate to DataSourceManager for unified infrastructure
- Tiered caching (different TTL per data type)
- Async/await support for improved concurrency
- Redis-backed distributed cache
- Prometheus metrics export
- Auto-tuning circuit breaker thresholds based on provider reliability

## References

- Existing implementation: `quantsys-v2/services/financial_data_service.py`
- Reference design: `quantsys-v2/api/routes/quote_v2.py`
- Cache implementation: `quantsys-v2/data_sources/cache.py`
- Circuit breaker implementation: `quantsys-v2/data_sources/circuit_breaker.py`
