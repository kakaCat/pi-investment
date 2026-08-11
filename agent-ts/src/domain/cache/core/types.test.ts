import { describe, it, expect } from '@jest/globals';
import type { CacheNamespace, StorageType, CacheEntry, CacheConfig, CacheEvent, CacheEventType } from './types.js';

describe('Cache Types', () => {
  it('should accept valid CacheNamespace values', () => {
    const namespaces: CacheNamespace[] = ['intraday', 'daily', 'quarterly', 'static'];
    expect(namespaces).toHaveLength(4);
  });

  it('should accept valid StorageType values', () => {
    const types: StorageType[] = ['memory', 'file'];
    expect(types).toHaveLength(2);
  });

  it('should create valid CacheEntry', () => {
    const entry: CacheEntry<string> = {
      key: 'test:key',
      value: 'test-value',
      namespace: 'daily',
      createdAt: Date.now(),
      expiresAt: Date.now() + 1000,
      metadata: { source: 'test' }
    };
    expect(entry.key).toBe('test:key');
    expect(entry.value).toBe('test-value');
  });

  it('should create valid CacheConfig', () => {
    const config: CacheConfig = {
      namespace: 'intraday',
      ttl: 2 * 60 * 1000,
      storageType: 'memory',
      maxSize: 500,
      autoCleanup: true
    };
    expect(config.namespace).toBe('intraday');
    expect(config.ttl).toBe(120000);
  });

  it('should create valid CacheEvent', () => {
    const event: CacheEvent = {
      type: 'trading_day_change' as CacheEventType,
      timestamp: Date.now(),
      payload: {
        namespace: 'intraday'
      }
    };
    expect(event.type).toBe('trading_day_change');
  });
});
