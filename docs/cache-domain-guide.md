# Cache Domain Usage Guide

## Overview

The Cache Domain provides a unified, namespace-based caching system for the PI Investment platform. It replaces multiple legacy caching implementations with a single, consistent API that supports multiple storage backends and automatic TTL management.

## Architecture

### Core Components

1. **CacheManager** - Singleton manager for all cache operations
2. **Namespaces** - Four isolated cache namespaces with different TTL policies
3. **Storage Backends** - Memory, SQLite, and File storage implementations
4. **Adapters** - Backward-compatible wrappers for legacy services

### Namespaces

| Namespace | TTL | Storage | Use Case |
|-----------|-----|---------|----------|
| `intraday` | 5 minutes | Memory | Real-time market data, intraday quotes |
| `daily` | 24 hours | SQLite | Daily K-lines, technical indicators |
| `quarterly` | 90 days | SQLite | Financial statements, earnings data |
| `static` | 1 year | File | FX rates, stock info, sector lists |

## Basic Usage

### Getting Started

```typescript
import { CacheManager } from './domain/cache/core/cache-manager.js';

const cacheManager = CacheManager.getInstance();
```

### Set and Get Operations

```typescript
// Set a value in the daily namespace
await cacheManager.set('daily', 'stock:000001:info', {
  symbol: '000001',
  name: '平安银行',
  price: 12.50
});

// Get a value
const stockInfo = await cacheManager.get('daily', 'stock:000001:info');
console.log(stockInfo); // { symbol: '000001', name: '平安银行', price: 12.50 }

// Get returns null if key doesn't exist
const missing = await cacheManager.get('daily', 'non-existent-key');
console.log(missing); // null
```

### Custom TTL

```typescript
// Override namespace default TTL (in seconds)
await cacheManager.set('intraday', 'temp-data', { value: 123 }, 60); // 1 minute
```

### Delete Operations

```typescript
// Delete a single key
await cacheManager.delete('daily', 'stock:000001:info');

// Clear entire namespace
await cacheManager.clear('daily');
```

### Pattern-Based Invalidation

```typescript
// Invalidate all K-line data for symbol 000001
const count = await cacheManager.invalidateByPattern('daily', 'kline:000001:*');
console.log(`Invalidated ${count} cache entries`);
```

### Batch Operations

```typescript
// Batch get (mget)
const keys = ['stock:000001:info', 'stock:000002:info', 'stock:600000:info'];
const results = await cacheManager.mget('daily', keys);
console.log(results.size); // Number of found keys
console.log(results.get('stock:000001:info')); // Stock info or undefined

// Batch set (mset)
const entries = new Map([
  ['stock:000001:info', { symbol: '000001', price: 12.50 }],
  ['stock:000002:info', { symbol: '000002', price: 8.30 }],
]);
await cacheManager.mset('daily', entries);
```

### Refresh Pattern

```typescript
// Refresh cache with new data
const freshData = await cacheManager.refresh(
  'daily',
  'stock:000001:info',
  async () => {
    // Fetch fresh data from API
    return await fetchStockInfo('000001');
  }
);
```

## Using Adapters

Adapters provide backward-compatible interfaces for legacy services while using the new cache system under the hood.

### KlineCacheAdapter

```typescript
import { KlineCacheAdapter } from './services/data/kline-cache-adapter.js';
import { StockDBService } from './services/data/stock-db-service.js';

const db = new StockDBService('/path/to/stocks.db');
const klineCache = new KlineCacheAdapter(db);

// Get K-line history (automatically cached in 'daily' namespace)
const klines = await klineCache.getHistory('000001', '2024-01-01', '2024-12-31');

// Incremental update (invalidates related cache entries)
const newRecords = await klineCache.updateSymbol('000001', 730);
console.log(`Added ${newRecords} new K-line records`);
```

### FxRateServiceAdapter

```typescript
import { FxRateServiceAdapter } from './services/fx-rate-service-adapter.js';

const fxService = new FxRateServiceAdapter('/path/to/pi-dir');

// Get FX rate (automatically cached in 'daily' namespace)
const rate = await fxService.getRate('HKDCNY');
console.log(`HKD to CNY: ${rate}`);

// Force update cache
await fxService.updateCache();
```

### Python Caller Resilient Adapter

```typescript
import { callPythonResilient, clearAllCaches } from './infrastructure/tools/shared/python-caller-resilient-adapter.js';

// Call Python function with automatic caching
const result = await callPythonResilient('get_stock_realtime_price', {
  symbol: '000001'
});

const data = JSON.parse(result);
console.log(data);

// Clear all Python call caches
await clearAllCaches();
```

## Advanced Patterns

### Cache-Aside Pattern

```typescript
async function getStockInfo(symbol: string) {
  const cacheKey = `stock:${symbol}:info`;
  
  // Try cache first
  let info = await cacheManager.get('daily', cacheKey);
  
  if (!info) {
    // Cache miss - fetch from source
    info = await fetchStockInfoFromAPI(symbol);
    
    // Store in cache
    await cacheManager.set('daily', cacheKey, info);
  }
  
  return info;
}
```

### Write-Through Pattern

```typescript
async function updateStockPrice(symbol: string, price: number) {
  // Update database
  await db.updateStockPrice(symbol, price);
  
  // Update cache immediately
  const cacheKey = `stock:${symbol}:price`;
  await cacheManager.set('intraday', cacheKey, price);
}
```

### Lazy Loading with Refresh

```typescript
async function getFinancialData(symbol: string, quarter: string) {
  const cacheKey = `financial:${symbol}:${quarter}`;
  
  return await cacheManager.refresh('quarterly', cacheKey, async () => {
    return await fetchFinancialData(symbol, quarter);
  });
}
```

## Migration Guide

### Migrating from Legacy KlineCacheService

**Before:**
```typescript
import { KlineCacheService } from './services/data/kline-cache-service.js';

const cache = new KlineCacheService(db);
const klines = await cache.getHistory('000001', '2024-01-01', '2024-12-31');
```

**After:**
```typescript
import { KlineCacheAdapter } from './services/data/kline-cache-adapter.js';

const cache = new KlineCacheAdapter(db);
const klines = await cache.getHistory('000001', '2024-01-01', '2024-12-31');
```

### Migrating from Legacy FxRateService

**Before:**
```typescript
import { FxRateService } from './services/fx-rate-service.js';

const fxService = new FxRateService(piDir);
const rate = await fxService.getRate('HKDCNY');
```

**After:**
```typescript
import { FxRateServiceAdapter } from './services/fx-rate-service-adapter.js';

const fxService = new FxRateServiceAdapter(piDir);
const rate = await fxService.getRate('HKDCNY');
```

### Migrating from Legacy python-caller-resilient

**Before:**
```typescript
import { callPythonResilient } from './infrastructure/tools/shared/python-caller-resilient.js';

const result = await callPythonResilient('get_stock_info', { symbol: '000001' });
```

**After:**
```typescript
import { callPythonResilient } from './infrastructure/tools/shared/python-caller-resilient-adapter.js';

const result = await callPythonResilient('get_stock_info', { symbol: '000001' });
```

## Best Practices

### 1. Choose the Right Namespace

- Use `intraday` for data that changes frequently (every few minutes)
- Use `daily` for data that updates once per day
- Use `quarterly` for financial reports and earnings data
- Use `static` for rarely-changing reference data

### 2. Use Descriptive Cache Keys

```typescript
// Good - clear hierarchy and purpose
'kline:000001:2024-01-01:2024-12-31'
'stock:000001:info'
'financial:000001:Q1-2024'

// Bad - ambiguous
'data1'
'cache_000001'
'temp'
```

### 3. Handle Cache Misses Gracefully

```typescript
const cached = await cacheManager.get('daily', key);
if (!cached) {
  // Always have a fallback strategy
  return await fetchFromSource();
}
return cached;
```

### 4. Use Pattern Invalidation for Related Data

```typescript
// When updating a stock, invalidate all related cache entries
await cacheManager.invalidateByPattern('daily', `stock:${symbol}:*`);
```

### 5. Avoid Caching Errors

```typescript
try {
  const data = await fetchData();
  await cacheManager.set('daily', key, data);
} catch (error) {
  // Don't cache error responses
  console.error('Failed to fetch data:', error);
  throw error;
}
```

### 6. Use Batch Operations for Multiple Keys

```typescript
// Efficient - single batch operation
const results = await cacheManager.mget('daily', keys);

// Inefficient - multiple individual operations
for (const key of keys) {
  await cacheManager.get('daily', key);
}
```

## Performance Considerations

### Memory Usage

- `intraday` namespace uses in-memory storage (fast but limited capacity)
- `daily` and `quarterly` use SQLite (persistent, good for large datasets)
- `static` uses file storage (persistent, good for structured data)

### TTL and Expiration

- Expired entries are automatically removed on access
- Use `clear()` to manually purge a namespace
- Use `invalidateByPattern()` for selective cleanup

### Concurrency

- All operations are async and support concurrent access
- SQLite storage uses WAL mode for better concurrency
- Memory storage is thread-safe

## Troubleshooting

### Cache Not Working

```typescript
// Check if data is actually cached
const value = await cacheManager.get('daily', 'my-key');
console.log('Cached value:', value);

// Verify TTL hasn't expired
// Daily namespace TTL is 24 hours - data older than that is auto-deleted
```

### Performance Issues

```typescript
// Use batch operations for multiple keys
const results = await cacheManager.mget('daily', keys);

// Use pattern invalidation instead of clearing entire namespace
await cacheManager.invalidateByPattern('daily', 'stock:000001:*');
```

### Storage Issues

```typescript
// For SQLite errors, check database file permissions
// For file storage errors, check directory write permissions

// Destroy and recreate cache manager if needed
cacheManager.destroy();
const newManager = CacheManager.getInstance();
```

## Testing

### Unit Tests

```typescript
import { CacheManager } from './domain/cache/core/cache-manager.js';

describe('My Service', () => {
  let cacheManager: CacheManager;

  beforeEach(async () => {
    cacheManager = CacheManager.getInstance();
    await cacheManager.clear('daily'); // Clear test data
  });

  it('should cache data', async () => {
    await cacheManager.set('daily', 'test-key', { value: 123 });
    const result = await cacheManager.get('daily', 'test-key');
    expect(result).toEqual({ value: 123 });
  });
});
```

### Integration Tests

See `src/domain/cache/__tests__/integration/cache-system-e2e.test.ts` for comprehensive integration test examples.

## API Reference

### CacheManager

#### `getInstance(): CacheManager`
Get the singleton CacheManager instance.

#### `get<T>(namespace, key): Promise<T | null>`
Get a value from cache. Returns null if not found or expired.

#### `set<T>(namespace, key, value, ttl?): Promise<void>`
Set a value in cache. Optional TTL overrides namespace default.

#### `delete(namespace, key): Promise<void>`
Delete a single cache entry.

#### `clear(namespace): Promise<void>`
Clear all entries in a namespace.

#### `mget<T>(namespace, keys): Promise<Map<string, T>>`
Get multiple values in a single operation.

#### `mset<T>(namespace, entries, ttl?): Promise<void>`
Set multiple values in a single operation.

#### `refresh<T>(namespace, key, fetcher): Promise<T>`
Delete existing cache entry and fetch fresh data.

#### `invalidateByPattern(namespace, pattern): Promise<number>`
Delete all entries matching a glob pattern. Returns count of deleted entries.

#### `destroy(): void`
Close all storage connections and reset singleton.

## Support

For issues or questions:
- Check the integration tests for usage examples
- Review the source code in `src/domain/cache/`
- Contact the development team

## Changelog

### Version 1.0.0 (2026-05-16)
- Initial release
- Four namespaces with different TTL policies
- Three storage backends (Memory, SQLite, File)
- Backward-compatible adapters for legacy services
- Pattern-based invalidation
- Batch operations support
