import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { CacheManager } from './cache-manager.js';
import { unlinkSync, existsSync } from 'fs';

describe('CacheManager', () => {
  let manager: CacheManager;

  beforeEach(() => {
    manager = CacheManager.getInstance();
  });

  afterEach(() => {
    manager.destroy();
    const dbPath = '.pi-invest/cache.db';
    if (existsSync(dbPath)) {
      unlinkSync(dbPath);
    }
  });

  it('should be a singleton', () => {
    const instance1 = CacheManager.getInstance();
    const instance2 = CacheManager.getInstance();
    expect(instance1).toBe(instance2);
  });

  it('should get and set values in intraday namespace', async () => {
    await manager.set('intraday', 'test-key', 'test-value');
    const result = await manager.get<string>('intraday', 'test-key');
    expect(result).toBe('test-value');
  });

  it('should get and set values in daily namespace', async () => {
    await manager.set('daily', 'test-key', { data: 'test' });
    const result = await manager.get<{ data: string }>('daily', 'test-key');
    expect(result).toEqual({ data: 'test' });
  });

  it('should delete values', async () => {
    await manager.set('intraday', 'test-key', 'value');
    await manager.delete('intraday', 'test-key');
    const result = await manager.get('intraday', 'test-key');
    expect(result).toBeNull();
  });

  it('should clear namespace', async () => {
    await manager.set('intraday', 'key1', 'value1');
    await manager.set('intraday', 'key2', 'value2');
    await manager.clear('intraday');
    const result1 = await manager.get('intraday', 'key1');
    const result2 = await manager.get('intraday', 'key2');
    expect(result1).toBeNull();
    expect(result2).toBeNull();
  });

  it('should support batch get', async () => {
    await manager.set('intraday', 'key1', 'value1');
    await manager.set('intraday', 'key2', 'value2');
    const results = await manager.mget<string>('intraday', ['key1', 'key2', 'key3']);
    expect(results.size).toBe(2);
    expect(results.get('key1')).toBe('value1');
    expect(results.get('key2')).toBe('value2');
  });

  it('should support batch set', async () => {
    const entries = new Map([
      ['key1', 'value1'],
      ['key2', 'value2']
    ]);
    await manager.mset('intraday', entries);
    const result1 = await manager.get<string>('intraday', 'key1');
    const result2 = await manager.get<string>('intraday', 'key2');
    expect(result1).toBe('value1');
    expect(result2).toBe('value2');
  });

  it('should refresh cache with fetcher', async () => {
    let fetchCount = 0;
    const fetcher = async () => {
      fetchCount++;
      return `value-${fetchCount}`;
    };

    const result1 = await manager.refresh('intraday', 'test-key', fetcher);
    expect(result1).toBe('value-1');
    expect(fetchCount).toBe(1);

    const cached = await manager.get<string>('intraday', 'test-key');
    expect(cached).toBe('value-1');

    const result2 = await manager.refresh('intraday', 'test-key', fetcher);
    expect(result2).toBe('value-2');
    expect(fetchCount).toBe(2);
  });

  it('should invalidate by pattern', async () => {
    await manager.set('intraday', 'user:123', 'value1');
    await manager.set('intraday', 'user:456', 'value2');
    await manager.set('intraday', 'product:789', 'value3');

    const count = await manager.invalidateByPattern('intraday', 'user:*');
    expect(count).toBe(2);

    const user1 = await manager.get('intraday', 'user:123');
    const user2 = await manager.get('intraday', 'user:456');
    const product = await manager.get('intraday', 'product:789');

    expect(user1).toBeNull();
    expect(user2).toBeNull();
    expect(product).toBe('value3');
  });
});
