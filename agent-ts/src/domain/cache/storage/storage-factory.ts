import type { IStorage } from './storage-interface.js';
import type { CacheConfig } from '../core/types.js';
import { MemoryStorage } from './memory-storage.js';
import { SQLiteStorage } from './sqlite-storage.js';
import { FileStorage } from './file-storage.js';

export class StorageFactory {
  private static dbPath = '.pi-invest/cache.db';
  private static cacheDir = '.pi-invest/cache';

  /**
   * Set custom paths for testing
   */
  static setTestPaths(dbPath: string, cacheDir: string): void {
    this.dbPath = dbPath;
    this.cacheDir = cacheDir;
  }

  /**
   * Reset to default production paths
   */
  static resetPaths(): void {
    this.dbPath = '.pi-invest/cache.db';
    this.cacheDir = '.pi-invest/cache';
  }

  static create(config: CacheConfig): IStorage {
    switch (config.storageType) {
      case 'memory':
        return new MemoryStorage(config.maxSize);
      case 'sqlite':
        return new SQLiteStorage(this.dbPath, config.namespace);
      case 'file':
        return new FileStorage(`${this.cacheDir}/${config.namespace}.json`);
      default:
        throw new Error(`Unknown storage type: ${config.storageType}`);
    }
  }
}
