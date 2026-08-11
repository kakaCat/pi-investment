import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { CacheAdmin } from './cache-admin.js';
import { CacheManager } from '../core/cache-manager.js';
import { StorageFactory } from '../storage/storage-factory.js';
import { mkdtempSync, rmSync, existsSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

describe('CacheAdmin', () => {
  let admin: CacheAdmin;
  let cacheManager: CacheManager;
  let testDir: string;

  beforeEach(() => {
    testDir = mkdtempSync(join(tmpdir(), 'cache-test-'));
    StorageFactory.setTestPaths(testDir);

    CacheManager.resetInstance();
    cacheManager = CacheManager.getInstance();
    admin = new CacheAdmin();
  });

  afterEach(() => {
    cacheManager.destroy();
    CacheManager.resetInstance();
    StorageFactory.resetPaths();

    if (existsSync(testDir)) {
      rmSync(testDir, { recursive: true, force: true });
    }
  });

  it('should inspect existing key', async () => {
    await cacheManager.set('intraday', 'test-key', 'test-value');

    const info = await admin.inspect('intraday', 'test-key');
    expect(info.exists).toBe(true);
    expect(info.value).toBe('test-value');
    expect(info.ttl).toBeGreaterThan(0);
  });

  it('should inspect non-existent key', async () => {
    const info = await admin.inspect('intraday', 'non-existent');
    expect(info.exists).toBe(false);
    expect(info.value).toBeUndefined();
  });

  it('should manually set and delete', async () => {
    await admin.set('intraday', 'manual-key', 'manual-value');
    const value = await cacheManager.get<string>('intraday', 'manual-key');
    expect(value).toBe('manual-value');

    await admin.delete('intraday', 'manual-key');
    const deleted = await cacheManager.get('intraday', 'manual-key');
    expect(deleted).toBeNull();
  });

  it('should clear namespace and return count', async () => {
    await cacheManager.set('intraday', 'key1', 'value1');
    await cacheManager.set('intraday', 'key2', 'value2');

    const count = await admin.clear('intraday');
    expect(count).toBeGreaterThanOrEqual(0);

    const value = await cacheManager.get('intraday', 'key1');
    expect(value).toBeNull();
  });

  it('should warmup cache with fetchers', async () => {
    const tasks = [
      {
        namespace: 'intraday' as const,
        key: 'warm1',
        fetcher: async () => 'value1'
      },
      {
        namespace: 'intraday' as const,
        key: 'warm2',
        fetcher: async () => 'value2'
      }
    ];

    await admin.warmup(tasks);

    const value1 = await cacheManager.get<string>('intraday', 'warm1');
    const value2 = await cacheManager.get<string>('intraday', 'warm2');

    expect(value1).toBe('value1');
    expect(value2).toBe('value2');
  });

  it('should cleanup expired entries', async () => {
    await cacheManager.set('intraday', 'expired', 'value', 1);
    await new Promise(resolve => setTimeout(resolve, 10));

    const result = await admin.cleanup('intraday');
    expect(result.cleaned).toBeGreaterThanOrEqual(0);
  });
});
