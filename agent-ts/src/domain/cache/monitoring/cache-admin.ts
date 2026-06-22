import type { CacheNamespace } from '../core/types.js';
import { CacheManager } from '../core/cache-manager.js';
import { writeFile, readFile } from 'fs/promises';

export class CacheAdmin {
  private cacheManager: CacheManager;

  constructor() {
    this.cacheManager = CacheManager.getInstance();
  }

  async inspect(namespace: CacheNamespace, key: string): Promise<{
    exists: boolean;
    value?: unknown;
    createdAt?: number;
    expiresAt?: number;
    ttl?: number;
  }> {
    const value = await this.cacheManager.get(namespace, key);

    if (value === null) {
      return { exists: false };
    }

    // Get metadata from storage if available
    const ns = this.cacheManager['namespaces'][namespace];
    if (ns) {
      const storage = ns.getStorage();
      const keys = await storage.keys();

      if (keys.includes(key)) {
        // For now, return basic info
        // TODO: Enhance storage interface to return metadata
        return {
          exists: true,
          value,
          ttl: 1000 // Placeholder
        };
      }
    }

    return {
      exists: true,
      value,
      ttl: undefined
    };
  }

  async set(namespace: CacheNamespace, key: string, value: unknown, ttl?: number): Promise<void> {
    await this.cacheManager.set(namespace, key, value, ttl);
  }

  async delete(namespace: CacheNamespace, key: string): Promise<void> {
    await this.cacheManager.delete(namespace, key);
  }

  async clear(namespace: CacheNamespace): Promise<number> {
    const ns = this.cacheManager['namespaces'][namespace];
    let count = 0;

    if (ns) {
      const keys = await ns.keys();
      count = keys.length;
    }

    await this.cacheManager.clear(namespace);
    return count;
  }

  async export(namespace: CacheNamespace, filePath: string): Promise<void> {
    const entries: Record<string, unknown> = {};

    const ns = this.cacheManager['namespaces'][namespace];
    if (ns) {
      const keys = await ns.keys();

      for (const key of keys) {
        const value = await ns.get(key);
        if (value !== null) {
          entries[key] = value;
        }
      }
    }

    const content = JSON.stringify(entries, null, 2);
    await writeFile(filePath, content, 'utf-8');
  }

  async import(namespace: CacheNamespace, filePath: string): Promise<number> {
    const content = await readFile(filePath, 'utf-8');
    const entries = JSON.parse(content) as Record<string, unknown>;

    let count = 0;
    for (const [key, value] of Object.entries(entries)) {
      await this.cacheManager.set(namespace, key, value);
      count++;
    }

    return count;
  }

  async warmup(tasks: Array<{
    namespace: CacheNamespace;
    key: string;
    fetcher: () => Promise<unknown>;
  }>): Promise<void> {
    await Promise.all(
      tasks.map(async ({ namespace, key, fetcher }) => {
        const value = await fetcher();
        await this.cacheManager.set(namespace, key, value);
      })
    );
  }

  async cleanup(namespace?: CacheNamespace): Promise<{
    cleaned: number;
    remaining: number;
  }> {
    let cleaned = 0;
    let remaining = 0;

    if (namespace) {
      const ns = this.cacheManager['namespaces'][namespace];
      if (ns) {
        const storage = ns.getStorage();
        cleaned = await storage.cleanup();
        const keys = await storage.keys();
        remaining = keys.length;
      }
    } else {
      // Cleanup all namespaces
      const namespaces: CacheNamespace[] = ['intraday', 'daily', 'quarterly', 'static'];

      for (const ns of namespaces) {
        const namespace = this.cacheManager['namespaces'][ns];
        if (namespace) {
          const storage = namespace.getStorage();
          cleaned += await storage.cleanup();
        }
      }

      // Count remaining across all namespaces
      for (const ns of namespaces) {
        const namespace = this.cacheManager['namespaces'][ns];
        if (namespace) {
          const storage = namespace.getStorage();
          const keys = await storage.keys();
          remaining += keys.length;
        }
      }
    }

    return {
      cleaned,
      remaining
    };
  }
}

export const cacheAdmin = new CacheAdmin();
