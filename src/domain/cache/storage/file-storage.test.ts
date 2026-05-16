import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { FileStorage } from './file-storage.js';
import { mkdtempSync, rmSync, existsSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

describe('FileStorage', () => {
  let testDir: string;
  let testFilePath: string;
  let storage: FileStorage;

  beforeEach(() => {
    testDir = mkdtempSync(join(tmpdir(), 'cache-test-'));
    testFilePath = join(testDir, 'test-static.json');
    storage = new FileStorage(testFilePath);
  });

  afterEach(() => {
    if (existsSync(testDir)) {
      rmSync(testDir, { recursive: true, force: true });
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

  it('should persist data to disk', async () => {
    const expiresAt = Date.now() + 10000;
    await storage.set('test-key', 'test-value', expiresAt);

    const newStorage = new FileStorage(testFilePath);
    const result = await newStorage.get<string>('test-key');
    expect(result).toBe('test-value');
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

  it('should cleanup expired entries', async () => {
    const expiredAt = Date.now() - 1000;
    const validAt = Date.now() + 10000;
    await storage.set('expired1', 'value1', expiredAt);
    await storage.set('valid', 'value2', validAt);
    const cleaned = await storage.cleanup();
    expect(cleaned).toBe(1);
    const size = await storage.size();
    expect(size).toBe(1);
  });
});
