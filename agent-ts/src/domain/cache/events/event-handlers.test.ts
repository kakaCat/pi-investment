import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { registerCacheEventHandlers, CacheEvents, emitCacheEvent } from './event-handlers.js';
import { CacheManager } from '../core/cache-manager.js';
import { eventBus } from '../core/event-bus.js';
import { StorageFactory } from '../storage/storage-factory.js';
import { unlinkSync, existsSync, mkdtempSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

describe('Event Handlers', () => {
  let cacheManager: CacheManager;
  let testDir: string;

  beforeEach(() => {
    // Create temporary directory for test
    testDir = mkdtempSync(join(tmpdir(), 'cache-test-'));

    // Configure factory to use test paths
    StorageFactory.setTestPaths(testDir);

    // Reset and get fresh CacheManager instance
    CacheManager.resetInstance();
    cacheManager = CacheManager.getInstance();
    eventBus.clear();
    registerCacheEventHandlers();
  });

  afterEach(() => {
    cacheManager.destroy();
    CacheManager.resetInstance();
    StorageFactory.resetPaths();

    // Clean up test directory
    if (existsSync(testDir)) {
      rmSync(testDir, { recursive: true, force: true });
    }
  });

  it('should clear intraday cache on trading day change', async () => {
    await cacheManager.set('intraday', 'test-key', 'test-value');
    await cacheManager.set('daily', 'other-key', 'other-value');

    await CacheEvents.tradingDayChange();

    const intradayValue = await cacheManager.get('intraday', 'test-key');
    const dailyValue = await cacheManager.get('daily', 'other-key');

    expect(intradayValue).toBeNull();
    expect(dailyValue).toBe('other-value');
  });

  it('should invalidate quarterly cache on financial report', async () => {
    await cacheManager.set('quarterly', 'financial:600000:balance', { data: 'old' });
    await cacheManager.set('quarterly', 'financial:600001:balance', { data: 'other' });

    await CacheEvents.financialReport('600000');

    const invalidated = await cacheManager.get('quarterly', 'financial:600000:balance');
    const other = await cacheManager.get('quarterly', 'financial:600001:balance');

    expect(invalidated).toBeNull();
    expect(other).toEqual({ data: 'other' });
  });

  it('should invalidate daily cache on announcement', async () => {
    await cacheManager.set('daily', 'announcement:600000:list', ['ann1']);
    await cacheManager.set('daily', 'announcement:600001:list', ['ann2']);

    await CacheEvents.announcement('600000');

    const invalidated = await cacheManager.get('daily', 'announcement:600000:list');
    const other = await cacheManager.get('daily', 'announcement:600001:list');

    expect(invalidated).toBeNull();
    expect(other).toEqual(['ann2']);
  });

  it('should invalidate quarterly cache on holder change', async () => {
    await cacheManager.set('quarterly', 'holder:600000:top10', [{ name: 'holder1' }]);
    await cacheManager.set('quarterly', 'holder:600001:top10', [{ name: 'holder2' }]);

    await CacheEvents.holderChange('600000');

    const invalidated = await cacheManager.get('quarterly', 'holder:600000:top10');
    const other = await cacheManager.get('quarterly', 'holder:600001:top10');

    expect(invalidated).toBeNull();
    expect(other).toEqual([{ name: 'holder2' }]);
  });

  it('should handle manual invalidation', async () => {
    await cacheManager.set('intraday', 'manual:key1', 'value1');
    await cacheManager.set('intraday', 'manual:key2', 'value2');
    await cacheManager.set('intraday', 'other:key3', 'value3');

    await CacheEvents.manualInvalidate('intraday', 'manual:*');

    const key1 = await cacheManager.get('intraday', 'manual:key1');
    const key2 = await cacheManager.get('intraday', 'manual:key2');
    const key3 = await cacheManager.get('intraday', 'other:key3');

    expect(key1).toBeNull();
    expect(key2).toBeNull();
    expect(key3).toBe('value3');
  });

  it('should handle cache:clear event', async () => {
    await cacheManager.set('intraday', 'key1', 'value1');
    await cacheManager.set('intraday', 'key2', 'value2');

    await emitCacheEvent({
      type: 'cache:clear',
      timestamp: Date.now(),
      payload: { namespace: 'intraday' }
    });

    const key1 = await cacheManager.get('intraday', 'key1');
    const key2 = await cacheManager.get('intraday', 'key2');

    expect(key1).toBeNull();
    expect(key2).toBeNull();
  });

  it('should handle cache:refresh event', async () => {
    await cacheManager.set('intraday', 'refresh-key', 'old-value');

    await emitCacheEvent({
      type: 'cache:refresh',
      timestamp: Date.now(),
      payload: { namespace: 'intraday', key: 'refresh-key' }
    });

    const value = await cacheManager.get('intraday', 'refresh-key');
    expect(value).toBeNull();
  });

  it('should handle cache:invalidate event', async () => {
    await cacheManager.set('daily', 'pattern:key1', 'value1');
    await cacheManager.set('daily', 'pattern:key2', 'value2');
    await cacheManager.set('daily', 'other:key3', 'value3');

    await emitCacheEvent({
      type: 'cache:invalidate',
      timestamp: Date.now(),
      payload: { namespace: 'daily', pattern: 'pattern:*' }
    });

    const key1 = await cacheManager.get('daily', 'pattern:key1');
    const key2 = await cacheManager.get('daily', 'pattern:key2');
    const key3 = await cacheManager.get('daily', 'other:key3');

    expect(key1).toBeNull();
    expect(key2).toBeNull();
    expect(key3).toBe('value3');
  });
});
