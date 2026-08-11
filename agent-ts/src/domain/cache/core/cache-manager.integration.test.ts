import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { CacheManager } from './cache-manager.js';
import { EventBus } from './event-bus.js';
import { CacheMonitor } from './cache-monitor.js';
import { StorageFactory } from '../storage/storage-factory.js';
import { mkdtempSync, rmSync, existsSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

describe('CacheManager Integration', () => {
  let manager: CacheManager;
  let eventBus: EventBus;
  let monitor: CacheMonitor;
  let testDir: string;

  beforeEach(() => {
    // Create temporary directory for test
    testDir = mkdtempSync(join(tmpdir(), 'cache-test-'));

    // Configure factory to use test paths
    StorageFactory.setTestPaths(testDir);

    // Reset and get fresh instances
    CacheManager.resetInstance();
    manager = CacheManager.getInstance();
    eventBus = EventBus.getInstance();
    monitor = CacheMonitor.getInstance();
    monitor.reset();
    eventBus.clear();
  });

  afterEach(() => {
    manager.destroy();
    CacheManager.resetInstance();
    StorageFactory.resetPaths();

    // Clean up test directory
    if (existsSync(testDir)) {
      rmSync(testDir, { recursive: true, force: true });
    }
  });

  it('should integrate with EventBus for invalidation', async () => {
    await manager.set('intraday', 'test-key', 'test-value');

    const value1 = await manager.get('intraday', 'test-key');
    expect(value1).toBe('test-value');

    // Emit invalidation event
    await eventBus.emit({
      type: 'cache:invalidate',
      timestamp: Date.now(),
      payload: {
        namespace: 'intraday',
        pattern: 'test-*'
      }
    });

    // Subscribe to invalidation events
    eventBus.on('cache:invalidate', async (event) => {
      if (event.payload?.namespace && event.payload.pattern) {
        await manager.invalidateByPattern(event.payload.namespace, event.payload.pattern);
      }
    });

    // Emit another invalidation
    await eventBus.emit({
      type: 'cache:invalidate',
      timestamp: Date.now(),
      payload: {
        namespace: 'intraday',
        pattern: 'test-*'
      }
    });

    const value2 = await manager.get('intraday', 'test-key');
    expect(value2).toBeNull();
  });

  it('should work across all namespaces', async () => {
    await manager.set('intraday', 'key1', 'value1');
    await manager.set('daily', 'key2', 'value2');
    await manager.set('quarterly', 'key3', 'value3');
    await manager.set('static', 'key4', 'value4');

    const v1 = await manager.get('intraday', 'key1');
    const v2 = await manager.get('daily', 'key2');
    const v3 = await manager.get('quarterly', 'key3');
    const v4 = await manager.get('static', 'key4');

    expect(v1).toBe('value1');
    expect(v2).toBe('value2');
    expect(v3).toBe('value3');
    expect(v4).toBe('value4');
  });

  it('should handle complex data types', async () => {
    const complexData = {
      user: { id: 123, name: 'Test User' },
      items: [1, 2, 3],
      metadata: { created: Date.now() }
    };

    await manager.set('daily', 'complex-key', complexData);
    const retrieved = await manager.get<typeof complexData>('daily', 'complex-key');

    expect(retrieved).toEqual(complexData);
  });

  it('should support custom TTL', async () => {
    await manager.set('intraday', 'short-ttl', 'value', 100); // 100ms TTL

    const immediate = await manager.get('intraday', 'short-ttl');
    expect(immediate).toBe('value');

    await new Promise(resolve => setTimeout(resolve, 150));

    const expired = await manager.get('intraday', 'short-ttl');
    expect(expired).toBeNull();
  });

  it('should handle batch operations efficiently', async () => {
    const entries = new Map([
      ['key1', 'value1'],
      ['key2', 'value2'],
      ['key3', 'value3']
    ]);

    await manager.mset('intraday', entries);

    const results = await manager.mget<string>('intraday', ['key1', 'key2', 'key3', 'key4']);

    expect(results.size).toBe(3);
    expect(results.get('key1')).toBe('value1');
    expect(results.get('key2')).toBe('value2');
    expect(results.get('key3')).toBe('value3');
    expect(results.has('key4')).toBe(false);
  });

  it('should refresh cache with fetcher', async () => {
    let fetchCount = 0;
    const fetcher = async () => {
      fetchCount++;
      return `fetched-${fetchCount}`;
    };

    const result1 = await manager.refresh('intraday', 'refresh-key', fetcher);
    expect(result1).toBe('fetched-1');
    expect(fetchCount).toBe(1);

    const cached = await manager.get<string>('intraday', 'refresh-key');
    expect(cached).toBe('fetched-1');

    const result2 = await manager.refresh('intraday', 'refresh-key', fetcher);
    expect(result2).toBe('fetched-2');
    expect(fetchCount).toBe(2);
  });

  it('should invalidate by pattern across multiple keys', async () => {
    await manager.set('intraday', 'user:123:profile', { name: 'User 123' });
    await manager.set('intraday', 'user:123:settings', { theme: 'dark' });
    await manager.set('intraday', 'user:456:profile', { name: 'User 456' });
    await manager.set('intraday', 'product:789', { name: 'Product' });

    const count = await manager.invalidateByPattern('intraday', 'user:123:*');
    expect(count).toBe(2);

    const profile = await manager.get('intraday', 'user:123:profile');
    const settings = await manager.get('intraday', 'user:123:settings');
    const otherUser = await manager.get('intraday', 'user:456:profile');
    const product = await manager.get('intraday', 'product:789');

    expect(profile).toBeNull();
    expect(settings).toBeNull();
    expect(otherUser).toEqual({ name: 'User 456' });
    expect(product).toEqual({ name: 'Product' });
  });

  it('should handle concurrent operations', async () => {
    const operations = [];

    for (let i = 0; i < 10; i++) {
      operations.push(manager.set('intraday', `key-${i}`, `value-${i}`));
    }

    await Promise.all(operations);

    const keys = Array.from({ length: 10 }, (_, i) => `key-${i}`);
    const results = await manager.mget<string>('intraday', keys);

    expect(results.size).toBe(10);
    for (let i = 0; i < 10; i++) {
      expect(results.get(`key-${i}`)).toBe(`value-${i}`);
    }
  });

  it('should clear namespace without affecting others', async () => {
    await manager.set('intraday', 'key1', 'value1');
    await manager.set('daily', 'key2', 'value2');

    await manager.clear('intraday');

    const v1 = await manager.get('intraday', 'key1');
    const v2 = await manager.get('daily', 'key2');

    expect(v1).toBeNull();
    expect(v2).toBe('value2');
  });

  it('should handle event-driven invalidation', async () => {
    await manager.set('intraday', 'event-key', 'initial-value');

    // Subscribe manager to invalidation events
    eventBus.on('cache:invalidate', async (event) => {
      await manager.invalidateByEvent(event);
    });

    // Emit invalidation event
    await eventBus.emit({
      type: 'cache:invalidate',
      timestamp: Date.now(),
      payload: {
        namespace: 'intraday',
        pattern: 'event-*'
      }
    });

    const value = await manager.get('intraday', 'event-key');
    expect(value).toBeNull();
  });
});
