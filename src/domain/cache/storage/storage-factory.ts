import type { IStorage } from './storage-interface.js';
import type { CacheConfig } from '../core/types.js';
import { MemoryStorage } from './memory-storage.js';
import { SQLiteStorage } from './sqlite-storage.js';
import { FileStorage } from './file-storage.js';

export class StorageFactory {
  static create(config: CacheConfig): IStorage {
    switch (config.storageType) {
      case 'memory':
        return new MemoryStorage(config.maxSize);
      case 'sqlite':
        return new SQLiteStorage('.pi-invest/cache.db', config.namespace);
      case 'file':
        return new FileStorage(`.pi-invest/cache/${config.namespace}.json`);
      default:
        throw new Error(`Unknown storage type: ${config.storageType}`);
    }
  }
}
