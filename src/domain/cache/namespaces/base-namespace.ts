import type { IStorage } from '../storage/storage-interface.js';
import type { CacheConfig } from '../core/types.js';
import { StorageFactory } from '../storage/storage-factory.js';

export abstract class BaseNamespace {
  protected storage: IStorage;
  protected config: CacheConfig;

  constructor(config: CacheConfig) {
    this.config = config;
    this.storage = StorageFactory.create(config);
  }

  protected buildKey(identifier: string, params?: Record<string, unknown>): string {
    const paramStr = params ? `:${JSON.stringify(params)}` : '';
    return `${this.config.namespace}:${identifier}${paramStr}`;
  }

  protected getExpiresAt(customTtl?: number): number {
    const ttl = customTtl ?? this.config.ttl;
    return Date.now() + ttl;
  }

  async get<T>(key: string): Promise<T | null> {
    await this.beforeGet?.(key);
    const value = await this.storage.get<T>(key);
    await this.afterGet?.(key, value);
    return value;
  }

  async set<T>(key: string, value: T, customTtl?: number): Promise<void> {
    await this.beforeSet?.(key, value);
    const expiresAt = this.getExpiresAt(customTtl);
    await this.storage.set(key, value, expiresAt);
    await this.afterSet?.(key, value);
  }

  async delete(key: string): Promise<void> {
    await this.storage.delete(key);
  }

  async clear(): Promise<void> {
    await this.storage.clear();
  }

  async keys(pattern?: string): Promise<string[]> {
    return this.storage.keys(pattern);
  }

  async size(): Promise<number> {
    return this.storage.size();
  }

  async cleanup(): Promise<number> {
    return this.storage.cleanup();
  }

  protected async beforeGet?(key: string): Promise<void>;
  protected async afterGet?(key: string, value: unknown): Promise<void>;
  protected async beforeSet?(key: string, value: unknown): Promise<void>;
  protected async afterSet?(key: string, value: unknown): Promise<void>;
}
