import { readFile, writeFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import { dirname } from 'path';
import type { IStorage } from './storage-interface.js';

interface FileStorageData {
  [key: string]: {
    value: unknown;
    expiresAt: number;
  };
}

export class FileStorage implements IStorage {
  private filePath: string;
  private cache: FileStorageData;
  private loaded: boolean;

  constructor(filePath: string) {
    this.filePath = filePath;
    this.cache = {};
    this.loaded = false;
  }

  private async ensureLoaded(): Promise<void> {
    if (this.loaded) return;

    const dir = dirname(this.filePath);
    if (!existsSync(dir)) {
      await mkdir(dir, { recursive: true });
    }

    if (existsSync(this.filePath)) {
      try {
        const content = await readFile(this.filePath, 'utf-8');
        this.cache = JSON.parse(content) as FileStorageData;
      } catch (error) {
        console.error(`Failed to load cache from ${this.filePath}:`, error);
        this.cache = {};
      }
    }

    this.loaded = true;
  }

  private async persist(): Promise<void> {
    const content = JSON.stringify(this.cache, null, 2);
    const tempPath = `${this.filePath}.tmp`;

    await writeFile(tempPath, content, 'utf-8');
    await writeFile(this.filePath, content, 'utf-8');
  }

  async get<T>(key: string): Promise<T | null> {
    await this.ensureLoaded();

    const entry = this.cache[key];
    if (!entry) return null;

    if (Date.now() > entry.expiresAt) {
      delete this.cache[key];
      await this.persist();
      return null;
    }

    return entry.value as T;
  }

  async set<T>(key: string, value: T, expiresAt: number): Promise<void> {
    await this.ensureLoaded();

    this.cache[key] = { value, expiresAt };
    await this.persist();
  }

  async delete(key: string): Promise<void> {
    await this.ensureLoaded();

    delete this.cache[key];
    await this.persist();
  }

  async clear(): Promise<void> {
    this.cache = {};
    this.loaded = true;
    await this.persist();
  }

  async mget<T>(keys: string[]): Promise<Map<string, T>> {
    await this.ensureLoaded();

    const results = new Map<string, T>();
    const now = Date.now();

    for (const key of keys) {
      const entry = this.cache[key];
      if (entry && now <= entry.expiresAt) {
        results.set(key, entry.value as T);
      }
    }

    return results;
  }

  async mset<T>(entries: Map<string, { value: T; expiresAt: number }>): Promise<void> {
    await this.ensureLoaded();

    for (const [key, { value, expiresAt }] of entries.entries()) {
      this.cache[key] = { value, expiresAt };
    }

    await this.persist();
  }

  async keys(pattern?: string): Promise<string[]> {
    await this.ensureLoaded();

    const allKeys = Object.keys(this.cache);
    if (!pattern) return allKeys;

    const regex = new RegExp(pattern.replace(/\*/g, '.*'));
    return allKeys.filter(key => regex.test(key));
  }

  async size(): Promise<number> {
    await this.ensureLoaded();
    return Object.keys(this.cache).length;
  }

  async cleanup(): Promise<number> {
    await this.ensureLoaded();

    const now = Date.now();
    let cleaned = 0;

    for (const key of Object.keys(this.cache)) {
      if (now > this.cache[key].expiresAt) {
        delete this.cache[key];
        cleaned++;
      }
    }

    if (cleaned > 0) {
      await this.persist();
    }

    return cleaned;
  }

  destroy(): void {
    // FileStorage doesn't need cleanup
  }
}
