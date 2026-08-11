import type { IStorage } from './storage-interface.js';
import type { CacheConfig } from '../core/types.js';
import { MemoryStorage } from './memory-storage.js';
import { FileStorage } from './file-storage.js';

export class StorageFactory {
  private static cacheDir = '.pi-invest/cache';

  /**
   * Set custom paths for testing
   */
  static setTestPaths(cacheDir: string): void {
    this.cacheDir = cacheDir;
  }

  /**
   * Reset to default production paths
   */
  static resetPaths(): void {
    this.cacheDir = '.pi-invest/cache';
  }

  static create(config: CacheConfig): IStorage {
    switch (config.storageType) {
      case 'memory':
        return new MemoryStorage(config.maxSize);
      case 'file':
        return new FileStorage(`${this.cacheDir}/${config.namespace}.json`);
      default:
        throw new Error(`Unknown storage type: ${config.storageType}`);
    }
  }
}
