import type { CacheEvent } from '../core/types.js';
import { CacheManager } from '../core/cache-manager.js';
import { eventBus } from '../core/event-bus.js';

/**
 * Register all cache event handlers
 */
export function registerCacheEventHandlers(): void {
  // Trading day change - clear intraday cache
  eventBus.on('trading_day_change', async (event: CacheEvent) => {
    console.log('[Cache] Trading day changed, clearing intraday cache');
    await CacheManager.getInstance().clear('intraday');
  });

  // Financial report - invalidate quarterly cache for specific symbol
  eventBus.on('financial_report', async (event: CacheEvent) => {
    const { symbol } = event.payload || {};
    if (!symbol) return;

    console.log(`[Cache] Financial report published for ${symbol}, invalidating quarterly cache`);
    await CacheManager.getInstance().invalidateByPattern('quarterly', `*:${symbol}:*`);
  });

  // Announcement - invalidate daily cache for specific symbol
  eventBus.on('announcement', async (event: CacheEvent) => {
    const { symbol } = event.payload || {};
    if (!symbol) return;

    console.log(`[Cache] Announcement for ${symbol}, invalidating daily cache`);
    await CacheManager.getInstance().invalidateByPattern('daily', `*:${symbol}:*`);
  });

  // Holder change - invalidate quarterly cache for specific symbol
  eventBus.on('holder_change', async (event: CacheEvent) => {
    const { symbol } = event.payload || {};
    if (!symbol) return;

    console.log(`[Cache] Holder change for ${symbol}, invalidating quarterly cache`);
    await CacheManager.getInstance().invalidateByPattern('quarterly', `*:${symbol}:*`);
  });

  // Manual invalidate - use the built-in invalidation logic
  eventBus.on('manual_invalidate', async (event: CacheEvent) => {
    await CacheManager.getInstance().invalidateByEvent(event);
  });

  // Cache lifecycle events
  eventBus.on('cache:invalidate', async (event: CacheEvent) => {
    await CacheManager.getInstance().invalidateByEvent(event);
  });

  eventBus.on('cache:clear', async (event: CacheEvent) => {
    if (event.payload?.namespace) {
      console.log(`[Cache] Clearing ${event.payload.namespace} namespace`);
      await CacheManager.getInstance().clear(event.payload.namespace);
    }
  });

  eventBus.on('cache:refresh', async (event: CacheEvent) => {
    const { namespace, key } = event.payload || {};
    if (namespace && key) {
      console.log(`[Cache] Refreshing ${namespace}:${key}`);
      await CacheManager.getInstance().delete(namespace, key);
    }
  });
}

/**
 * Emit a cache event
 */
export async function emitCacheEvent(event: CacheEvent): Promise<void> {
  await eventBus.emit(event);
}

/**
 * Helper functions to emit specific events
 */
export const CacheEvents = {
  tradingDayChange: async () => {
    await emitCacheEvent({
      type: 'trading_day_change',
      timestamp: Date.now()
    });
  },

  financialReport: async (symbol: string) => {
    await emitCacheEvent({
      type: 'financial_report',
      timestamp: Date.now(),
      payload: { symbol }
    });
  },

  announcement: async (symbol: string) => {
    await emitCacheEvent({
      type: 'announcement',
      timestamp: Date.now(),
      payload: { symbol }
    });
  },

  holderChange: async (symbol: string) => {
    await emitCacheEvent({
      type: 'holder_change',
      timestamp: Date.now(),
      payload: { symbol }
    });
  },

  manualInvalidate: async (namespace: string, pattern?: string) => {
    await emitCacheEvent({
      type: 'manual_invalidate',
      timestamp: Date.now(),
      payload: { namespace: namespace as any, pattern }
    });
  }
};
