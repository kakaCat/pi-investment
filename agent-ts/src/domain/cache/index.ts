// Core
export { CacheManager } from './core/cache-manager.js';
export { getNamespaceConfig, isValidNamespace, NAMESPACE_CONFIGS } from './core/cache-config.js';
export { EventBus, eventBus } from './core/event-bus.js';
export { CacheMonitor, cacheMonitor } from './core/cache-monitor.js';
export type {
  CacheNamespace,
  CacheConfig,
  CacheEntry,
  CacheEvent,
  CacheEventType,
  CacheMetrics,
  PerformanceStats,
  SlowQuery
} from './core/types.js';

// Namespaces
export { IntradayCache } from './namespaces/intraday-cache.js';
export { DailyCache } from './namespaces/daily-cache.js';
export { QuarterlyCache } from './namespaces/quarterly-cache.js';
export { StaticCache } from './namespaces/static-cache.js';
export { BaseNamespace } from './namespaces/base-namespace.js';

// Storage
export type { IStorage } from './storage/storage-interface.js';
export { MemoryStorage } from './storage/memory-storage.js';
export { FileStorage } from './storage/file-storage.js';
export { StorageFactory } from './storage/storage-factory.js';

// Events
export { registerCacheEventHandlers, emitCacheEvent, CacheEvents } from './events/event-handlers.js';

// Monitoring
export { CacheAdmin, cacheAdmin } from './monitoring/cache-admin.js';
export { CachePerformance, cachePerformance } from './monitoring/cache-performance.js';
