import type { CacheNamespace, CacheEvent } from './types.js';
import { IntradayCache } from '../namespaces/intraday-cache.js';
import { DailyCache } from '../namespaces/daily-cache.js';
import { QuarterlyCache } from '../namespaces/quarterly-cache.js';
import { StaticCache } from '../namespaces/static-cache.js';
import type { BaseNamespace } from '../namespaces/base-namespace.js';

export class CacheManager {
  private static instance: CacheManager | null = null;
  private namespaces: Record<CacheNamespace, BaseNamespace>;

  private constructor() {
    this.namespaces = {
      intraday: new IntradayCache(),
      daily: new DailyCache(),
      quarterly: new QuarterlyCache(),
      static: new StaticCache()
    };
  }

  static getInstance(): CacheManager {
    if (!CacheManager.instance) {
      CacheManager.instance = new CacheManager();
    }
    return CacheManager.instance;
  }

  async get<T>(namespace: CacheNamespace, key: string): Promise<T | null> {
    return this.namespaces[namespace].get<T>(key);
  }

  async set<T>(namespace: CacheNamespace, key: string, value: T, ttl?: number): Promise<void> {
    await this.namespaces[namespace].set(key, value, ttl);
  }

  async delete(namespace: CacheNamespace, key: string): Promise<void> {
    await this.namespaces[namespace].delete(key);
  }

  async clear(namespace: CacheNamespace): Promise<void> {
    await this.namespaces[namespace].clear();
  }

  async mget<T>(namespace: CacheNamespace, keys: string[]): Promise<Map<string, T>> {
    const ns = this.namespaces[namespace];
    const results = new Map<string, T>();

    for (const key of keys) {
      const value = await ns.get<T>(key);
      if (value !== null) {
        results.set(key, value);
      }
    }

    return results;
  }

  async mset<T>(namespace: CacheNamespace, entries: Map<string, T>, ttl?: number): Promise<void> {
    const ns = this.namespaces[namespace];
    for (const [key, value] of entries.entries()) {
      await ns.set(key, value, ttl);
    }
  }

  async refresh<T>(
    namespace: CacheNamespace,
    key: string,
    fetcher: () => Promise<T>
  ): Promise<T> {
    await this.delete(namespace, key);
    const value = await fetcher();
    await this.set(namespace, key, value);
    return value;
  }

  async invalidateByPattern(namespace: CacheNamespace, pattern: string): Promise<number> {
    const keys = await this.namespaces[namespace].keys(pattern);
    await Promise.all(keys.map(k => this.delete(namespace, k)));
    return keys.length;
  }

  async invalidateByEvent(event: CacheEvent): Promise<void> {
    if (event.payload?.namespace) {
      if (event.payload.pattern) {
        await this.invalidateByPattern(event.payload.namespace, event.payload.pattern);
      } else {
        await this.clear(event.payload.namespace);
      }
    }
  }

  destroy(): void {
    // Close all storage connections
    for (const namespace of Object.values(this.namespaces)) {
      const storage = namespace.getStorage();
      if (storage && typeof storage.destroy === 'function') {
        storage.destroy();
      }
    }
    CacheManager.instance = null;
  }
}

export const cacheManager = CacheManager.getInstance();
