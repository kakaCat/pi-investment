/**
 * 缓存领域核心类型定义
 */

// 命名空间类型
export type CacheNamespace = 'intraday' | 'daily' | 'quarterly' | 'static';

// 存储类型
export type StorageType = 'memory' | 'sqlite' | 'file';

// 缓存条目
export interface CacheEntry<T = unknown> {
  key: string;
  value: T;
  namespace: CacheNamespace;
  createdAt: number;
  expiresAt: number;
  metadata?: Record<string, unknown>;
}

// 缓存配置
export interface CacheConfig {
  namespace: CacheNamespace;
  ttl: number;              // 毫秒
  storageType: StorageType;
  maxSize?: number;         // 最大条目数（仅内存存储）
  autoCleanup?: boolean;    // 自动清理过期数据
}

// 缓存事件类型
export enum CacheEventType {
  TRADING_DAY_CHANGE = 'trading_day_change',
  FINANCIAL_REPORT = 'financial_report',
  MANUAL_INVALIDATE = 'manual_invalidate',
  ANNOUNCEMENT = 'announcement',
  HOLDER_CHANGE = 'holder_change'
}

// 缓存事件
export interface CacheEvent {
  type: CacheEventType;
  timestamp: number;
  payload?: {
    symbol?: string;
    namespace?: CacheNamespace;
    pattern?: string;
  };
}

// 缓存指标
export interface CacheMetrics {
  hits: number;
  misses: number;
  hitRate: number;
  totalEntries: number;
  totalSize: number;
  namespaceStats: Record<CacheNamespace, {
    entries: number;
    size: number;
    hitRate: number;
  }>;
  hotKeys: Array<{
    key: string;
    namespace: CacheNamespace;
    accessCount: number;
    lastAccess: number;
  }>;
  ttlDistribution: {
    expired: number;
    expiringSoon: number;
    fresh: number;
  };
}

// 性能统计
export interface PerformanceStats {
  count: number;
  avg: number;
  p50: number;
  p95: number;
  p99: number;
  max: number;
}

// 慢查询记录
export interface SlowQuery {
  operation: string;
  duration: number;
  timestamp: number;
  key: string;
}
