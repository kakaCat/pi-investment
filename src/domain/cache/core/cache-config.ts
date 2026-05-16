import type { CacheNamespace, CacheConfig } from './types.js';

/**
 * 命名空间配置
 */
export const NAMESPACE_CONFIGS: Record<CacheNamespace, CacheConfig> = {
  intraday: {
    namespace: 'intraday',
    ttl: 2 * 60 * 1000,        // 2分钟
    storageType: 'memory',
    maxSize: 500,
    autoCleanup: true
  },
  daily: {
    namespace: 'daily',
    ttl: 24 * 60 * 60 * 1000,  // 24小时
    storageType: 'sqlite',
    autoCleanup: true
  },
  quarterly: {
    namespace: 'quarterly',
    ttl: 7 * 24 * 60 * 60 * 1000,  // 7天
    storageType: 'sqlite',
    autoCleanup: true
  },
  static: {
    namespace: 'static',
    ttl: 30 * 24 * 60 * 60 * 1000,  // 30天
    storageType: 'file',
    autoCleanup: false
  }
};

/**
 * 获取命名空间配置
 */
export function getNamespaceConfig(namespace: CacheNamespace): CacheConfig {
  return NAMESPACE_CONFIGS[namespace];
}

/**
 * 验证命名空间是否有效
 */
export function isValidNamespace(namespace: string): namespace is CacheNamespace {
  return namespace in NAMESPACE_CONFIGS;
}
