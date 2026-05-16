# Cache Domain Migration Guide

## Overview

This guide helps you migrate from the legacy caching implementations to the new unified Cache Domain system.

## What Changed?

### Before: Multiple Cache Implementations

The old system had three separate caching implementations:

1. **KlineCacheService** - SQLite-based K-line caching
2. **FxRateService** - JSON file-based FX rate caching  
3. **python-caller-resilient** - In-memory Python call result caching

Each had its own API, storage mechanism, and TTL logic.

### After: Unified Cache Domain

The new system provides:

1. **Single API** - CacheManager with consistent interface
2. **Four Namespaces** - intraday, daily, quarterly, static
3. **Three Storage Backends** - Memory, SQLite, File
4. **Backward-Compatible Adapters** - Drop-in replacements for legacy services

## Migration Steps

### Step 1: Update Imports

#### KlineCacheService → KlineCacheAdapter

**Before:**
```typescript
import { KlineCacheService } from './services/data/kline-cache-service.js';
```

**After:**
```typescript
import { KlineCacheAdapter } from './services/data/kline-cache-adapter.js';
```

#### FxRateService → FxRateServiceAdapter

**Before:**
```typescript
import { FxRateService } from './services/fx-rate-service.js';
```

**After:**
```typescript
import { FxRateServiceAdapter } from './services/fx-rate-service-adapter.js';
```

#### python-caller-resilient → python-caller-resilient-adapter

**Before:**
```typescript
import { callPythonResilient } from './infrastructure/tools/shared/python-caller-resilient.js';
```

**After:**
```typescript
import { callPythonResilient } from './infrastructure/tools/shared/python-caller-resilient-adapter.js';
```

### Step 2: Update Code (No API Changes Required!)

The adapters maintain the same API as the legacy services, so your existing code should work without changes:

```typescript
// KlineCacheAdapter - API unchanged
const cache = new KlineCacheAdapter(db);
const klines = await cache.getHistory('000001', '2024-01-01', '2024-12-31');
await cache.updateSymbol('000001', 730);

// FxRateServiceAdapter - API unchanged
const fxService = new FxRateServiceAdapter(piDir);
const rate = await fxService.getRate('HKDCNY');
await fxService.updateCache();

// callPythonResilient - API unchanged
const result = await callPythonResilient('get_stock_info', { symbol: '000001' });
```

### Step 3: Test Your Changes

Run your existing tests to verify everything works:

```bash
npm test
```

All tests should pass without modification.

### Step 4: Clean Up (Optional)

If you have any direct references to the old cache files, you can remove them:

- Old K-line database: `~/.pi/stocks.db` (backed up to `~/.pi/stocks.db.backup-YYYYMMDD`)
- Old FX rates file: `~/.pi/fx-rates.json` (still used during transition period)

## Data Migration

### Automatic Migration

The adapters automatically handle data migration:

1. **KlineCacheAdapter**
   - Reads from old SQLite database if data exists
   - Writes to both old database and new cache (transition period)
   - New cache takes precedence for reads

2. **FxRateServiceAdapter**
   - Reads from old JSON file if cache miss
   - Writes to both JSON file and new cache (transition period)
   - New cache takes precedence for reads

3. **python-caller-resilient-adapter**
   - Uses new cache system exclusively
   - Old in-memory cache is not migrated (short TTL makes this unnecessary)

### Manual Migration (If Needed)

If you need to manually migrate data:

```typescript
import { CacheManager } from './domain/cache/core/cache-manager.js';
import { readFileSync } from 'fs';

const cacheManager = CacheManager.getInstance();

// Example: Migrate custom cache data
const oldData = JSON.parse(readFileSync('old-cache.json', 'utf-8'));
for (const [key, value] of Object.entries(oldData)) {
  await cacheManager.set('daily', key, value);
}
```

## Advanced: Using CacheManager Directly

If you want to use the new cache system directly (instead of through adapters), here's how:

### Example 1: Caching Stock Info

**Before (custom implementation):**
```typescript
const cache = new Map();

function getStockInfo(symbol: string) {
  if (cache.has(symbol)) {
    return cache.get(symbol);
  }
  const info = await fetchStockInfo(symbol);
  cache.set(symbol, info);
  return info;
}
```

**After (using CacheManager):**
```typescript
import { CacheManager } from './domain/cache/core/cache-manager.js';

const cacheManager = CacheManager.getInstance();

async function getStockInfo(symbol: string) {
  const cacheKey = `stock:${symbol}:info`;
  
  let info = await cacheManager.get('daily', cacheKey);
  if (!info) {
    info = await fetchStockInfo(symbol);
    await cacheManager.set('daily', cacheKey, info);
  }
  
  return info;
}
```

### Example 2: Caching with TTL

**Before (custom implementation):**
```typescript
const cache = new Map();
const ttls = new Map();

function setWithTTL(key: string, value: any, ttlSeconds: number) {
  cache.set(key, value);
  ttls.set(key, Date.now() + ttlSeconds * 1000);
}

function getWithTTL(key: string) {
  const expiry = ttls.get(key);
  if (expiry && Date.now() > expiry) {
    cache.delete(key);
    ttls.delete(key);
    return null;
  }
  return cache.get(key);
}
```

**After (using CacheManager):**
```typescript
import { CacheManager } from './domain/cache/core/cache-manager.js';

const cacheManager = CacheManager.getInstance();

async function setWithTTL(key: string, value: any, ttlSeconds: number) {
  await cacheManager.set('intraday', key, value, ttlSeconds);
}

async function getWithTTL(key: string) {
  return await cacheManager.get('intraday', key);
}
```

### Example 3: Pattern-Based Invalidation

**Before (custom implementation):**
```typescript
const cache = new Map();

function invalidateByPrefix(prefix: string) {
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) {
      cache.delete(key);
    }
  }
}
```

**After (using CacheManager):**
```typescript
import { CacheManager } from './domain/cache/core/cache-manager.js';

const cacheManager = CacheManager.getInstance();

async function invalidateByPrefix(prefix: string) {
  const count = await cacheManager.invalidateByPattern('daily', `${prefix}*`);
  console.log(`Invalidated ${count} entries`);
}
```

## Namespace Selection Guide

Choose the appropriate namespace based on your data's update frequency:

| Data Type | Namespace | TTL | Example |
|-----------|-----------|-----|---------|
| Real-time quotes | `intraday` | 5 min | Stock prices, market overview |
| Daily K-lines | `daily` | 24 hrs | Historical prices, technical indicators |
| Financial reports | `quarterly` | 90 days | Earnings, balance sheets |
| Reference data | `static` | 1 year | Stock info, FX rates, sector lists |

## Troubleshooting

### Issue: Cache not working after migration

**Solution:** Verify you're using the adapter, not the old service:

```typescript
// Wrong - old service (deleted)
import { KlineCacheService } from './services/data/kline-cache-service.js';

// Correct - new adapter
import { KlineCacheAdapter } from './services/data/kline-cache-adapter.js';
```

### Issue: Data not persisting across restarts

**Solution:** Check which namespace you're using:

- `intraday` uses memory storage (not persistent)
- `daily`, `quarterly`, `static` use persistent storage

```typescript
// Not persistent
await cacheManager.set('intraday', key, value);

// Persistent
await cacheManager.set('daily', key, value);
```

### Issue: Cache returning stale data

**Solution:** Use pattern invalidation or refresh:

```typescript
// Invalidate specific pattern
await cacheManager.invalidateByPattern('daily', `stock:${symbol}:*`);

// Or force refresh
const fresh = await cacheManager.refresh('daily', key, async () => {
  return await fetchFreshData();
});
```

### Issue: Performance degradation

**Solution:** Use batch operations:

```typescript
// Slow - multiple individual operations
for (const key of keys) {
  await cacheManager.get('daily', key);
}

// Fast - single batch operation
const results = await cacheManager.mget('daily', keys);
```

## Rollback Plan

If you need to rollback to the old system:

1. The old cache files are still being written during the transition period
2. Revert your import statements to use the old services
3. The old data files (`stocks.db`, `fx-rates.json`) are still intact

**Note:** After the transition period ends, the adapters will stop writing to old files.

## Benefits of Migration

### 1. Unified API
- Single, consistent interface for all caching needs
- Easier to learn and maintain

### 2. Better Performance
- Optimized storage backends for each use case
- Batch operations support
- Efficient pattern-based invalidation

### 3. Improved Reliability
- Automatic TTL management
- Graceful error handling
- Persistent storage for critical data

### 4. Better Testing
- Easier to mock and test
- Comprehensive test coverage
- Integration tests included

### 5. Future-Proof
- Extensible architecture
- Easy to add new namespaces or storage backends
- Event-driven invalidation support

## Timeline

- **Phase 1 (Current):** Adapters write to both old and new systems
- **Phase 2 (1 month):** Adapters read from new system only, still write to old
- **Phase 3 (2 months):** Adapters use new system exclusively, old files can be deleted

## Support

If you encounter issues during migration:

1. Check this guide for common solutions
2. Review the [Cache Domain Usage Guide](./cache-domain-guide.md)
3. Look at integration tests in `src/domain/cache/__tests__/integration/`
4. Contact the development team

## Checklist

Use this checklist to track your migration progress:

- [ ] Updated imports to use adapters
- [ ] Ran tests to verify functionality
- [ ] Reviewed code for direct cache file access
- [ ] Updated any custom caching logic to use CacheManager
- [ ] Tested in development environment
- [ ] Tested in staging environment
- [ ] Monitored performance after deployment
- [ ] Verified data persistence
- [ ] Documented any custom cache usage patterns

## Examples

### Complete Migration Example

**Before:**
```typescript
// services/stock-service.ts
import { KlineCacheService } from './data/kline-cache-service.js';
import { FxRateService } from './fx-rate-service.js';

export class StockService {
  private klineCache: KlineCacheService;
  private fxService: FxRateService;

  constructor(db: StockDBService, piDir: string) {
    this.klineCache = new KlineCacheService(db);
    this.fxService = new FxRateService(piDir);
  }

  async getKlines(symbol: string, start: string, end: string) {
    return await this.klineCache.getHistory(symbol, start, end);
  }

  async getFxRate(pair: string) {
    return await this.fxService.getRate(pair);
  }
}
```

**After:**
```typescript
// services/stock-service.ts
import { KlineCacheAdapter } from './data/kline-cache-adapter.js';
import { FxRateServiceAdapter } from './fx-rate-service-adapter.js';

export class StockService {
  private klineCache: KlineCacheAdapter;
  private fxService: FxRateServiceAdapter;

  constructor(db: StockDBService, piDir: string) {
    this.klineCache = new KlineCacheAdapter(db);
    this.fxService = new FxRateServiceAdapter(piDir);
  }

  async getKlines(symbol: string, start: string, end: string) {
    return await this.klineCache.getHistory(symbol, start, end);
  }

  async getFxRate(pair: string) {
    return await this.fxService.getRate(pair);
  }
}
```

**Changes:** Only the import statements changed. The rest of the code remains identical.

## Conclusion

The migration to the Cache Domain is designed to be seamless. In most cases, you only need to update import statements. The adapters handle backward compatibility and data migration automatically.

For new code, consider using CacheManager directly for more flexibility and better integration with the cache system.
