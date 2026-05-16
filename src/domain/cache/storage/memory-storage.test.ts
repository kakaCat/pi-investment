import { describe, it, expect, beforeEach } from '@jest/globals';
import { MemoryStorage } from './memory-storage.js';

describe('MemoryStorage', () => {
  let storage: MemoryStorage;

  beforeEach(() => {
    storage = new MemoryStorage(100);
  });

  it('should return null for non-existent key', async () => {
    const result = await storage.get('non-existent');
    expect(result).toBeNull();
  });

  it('should store and retrieve value', async () => {
    const expiresAt = Date.now() + 10000;
    await storage.set('test-key', 'test-value', expiresAt);
    const result = await storage.get<string>('test-key');
    expect(result).toBe('test-value');
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

  it('should enforce maxSize with LRU eviction', async () => {
    const smallStorage = new MemoryStorage(3);
    const expiresAt = Date.now() + 10000;

    await smallStorage.set('key1', 'value1', expiresAt);
    await smallStorage.set('key2', 'value2', expiresAt);
    await smallStorage.set('key3', 'value3', expiresAt);
    await smallStorage.set('key4', 'value4', expiresAt);

    const size = await smallStorage.size();
    expect(size).toBe(3);

    const key1 = await smallStorage.get('key1');
    expect(key1).toBeNull();
  });

  it('should support batch get', async () => {
    const expiresAt = Date.now() + 10000;
    await storage.set('key1', 'value1', expiresAt);
    await storage.set('key2', 'value2', expiresAt);

    const results = await storage.mget<string>(['key1', 'key2', 'key3']);
    expect(results.size).toBe(2);
    expect(results.get('key1')).toBe('value1');
    expect(results.get('key2')).toBe('value2');
    expect(results.has('key3')).toBe(false);
  });

  it('should support batch set', async () => {
    const expiresAt = Date.now() + 10000;
    const entries = new Map([
      ['key1', { value: 'value1', expiresAt }],
      ['key2', { value: 'value2', expiresAt }]
    ]);

    await storage.mset(entries);
    const key1 = await storage.get<string>('key1');
    const key2 = await storage.get<string>('key2');
    expect(key1).toBe('value1');
    expect(key2).toBe('value2');
  });
});
