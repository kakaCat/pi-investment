import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { SQLiteStorage } from './sqlite-storage.js';
import { unlinkSync, existsSync } from 'fs';

describe('SQLiteStorage', () => {
  const testDbPath = '.pi-invest/test-cache.db';
  let storage: SQLiteStorage;

  beforeEach(() => {
    if (existsSync(testDbPath)) {
      unlinkSync(testDbPath);
    }
    storage = new SQLiteStorage(testDbPath, 'daily');
  });

  afterEach(() => {
    storage.destroy();
    if (existsSync(testDbPath)) {
      unlinkSync(testDbPath);
    }
  });

  it('should return null for non-existent key', async () => {
    const result = await storage.get('non-existent');
    expect(result).toBeNull();
  });

  it('should store and retrieve value', async () => {
    const expiresAt = Date.now() + 10000;
    await storage.set('test-key', { data: 'test-value' }, expiresAt);
    const result = await storage.get<{ data: string }>('test-key');
    expect(result).toEqual({ data: 'test-value' });
  });

  it('should return null for expired key', async () => {
    const expiresAt = Date.now() - 1000;
    await storage.set('expired-key', 'value', expiresAt);
    const result = await storage.get('expired-key');
    expect(result).toBeNull();
  });

  it('should delete key', async () => {
    const expiresAt = Date.now() + 10000;
    await storage.set('test-key', 'value', expiresAt);
    await storage.delete('test-key');
    const result = await storage.get('test-key');
    expect(result).toBeNull();
  });

  it('should clear all entries', async () => {
    const expiresAt = Date.now() + 10000;
    await storage.set('key1', 'value1', expiresAt);
    await storage.set('key2', 'value2', expiresAt);
    await storage.clear();
    const size = await storage.size();
    expect(size).toBe(0);
  });

  it('should return all keys', async () => {
    const expiresAt = Date.now() + 10000;
    await storage.set('key1', 'value1', expiresAt);
    await storage.set('key2', 'value2', expiresAt);
    const keys = await storage.keys();
    expect(keys).toHaveLength(2);
    expect(keys).toContain('key1');
    expect(keys).toContain('key2');
  });

  it('should cleanup expired entries', async () => {
    const expiredAt = Date.now() - 1000;
    const validAt = Date.now() + 10000;
    await storage.set('expired1', 'value1', expiredAt);
    await storage.set('expired2', 'value2', expiredAt);
    await storage.set('valid', 'value3', validAt);
    const cleaned = await storage.cleanup();
    expect(cleaned).toBe(2);
    const size = await storage.size();
    expect(size).toBe(1);
  });

  it('should support batch operations', async () => {
    const expiresAt = Date.now() + 10000;
    const entries = new Map([
      ['key1', { value: 'value1', expiresAt }],
      ['key2', { value: 'value2', expiresAt }]
    ]);

    await storage.mset(entries);
    const results = await storage.mget<string>(['key1', 'key2']);
    expect(results.size).toBe(2);
    expect(results.get('key1')).toBe('value1');
    expect(results.get('key2')).toBe('value2');
  });

  it('should filter keys by pattern', async () => {
    const expiresAt = Date.now() + 10000;
    await storage.set('user:123', 'value1', expiresAt);
    await storage.set('user:456', 'value2', expiresAt);
    await storage.set('product:789', 'value3', expiresAt);

    const userKeys = await storage.keys('user:*');
    expect(userKeys).toHaveLength(2);
    expect(userKeys).toContain('user:123');
    expect(userKeys).toContain('user:456');
  });
});
