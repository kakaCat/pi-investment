import type { CacheNamespace } from './types.js';

interface NamespaceStats {
  hits: number;
  misses: number;
  hitRate: number;
}

interface HotKey {
  key: string;
  namespace: CacheNamespace;
  accessCount: number;
  lastAccess: number;
}

interface LatencyStats {
  count: number;
  avg: number;
  min: number;
  max: number;
  total: number;
}

interface SlowQuery {
  operation: string;
  duration: number;
  timestamp: number;
  key: string;
}

interface CacheMetrics {
  hits: number;
  misses: number;
  hitRate: number;
  namespaceStats: Record<CacheNamespace, NamespaceStats>;
  hotKeys: HotKey[];
}

export class CacheMonitor {
  private static instance: CacheMonitor | null = null;
  private hits: number = 0;
  private misses: number = 0;
  private namespaceHits: Map<CacheNamespace, number> = new Map();
  private namespaceMisses: Map<CacheNamespace, number> = new Map();
  private keyAccess: Map<string, { count: number; namespace: CacheNamespace; lastAccess: number }> = new Map();
  private latencies: Map<string, number[]> = new Map();
  private slowQueries: SlowQuery[] = [];
  private readonly SLOW_QUERY_THRESHOLD = 100; // ms
  private readonly MAX_SLOW_QUERIES = 100;

  private constructor() {}

  static getInstance(): CacheMonitor {
    if (!CacheMonitor.instance) {
      CacheMonitor.instance = new CacheMonitor();
    }
    return CacheMonitor.instance;
  }

  recordHit(namespace: CacheNamespace, key: string): void {
    this.hits++;
    this.namespaceHits.set(namespace, (this.namespaceHits.get(namespace) || 0) + 1);
    this.recordKeyAccess(namespace, key);
  }

  recordMiss(namespace: CacheNamespace, key: string): void {
    this.misses++;
    this.namespaceMisses.set(namespace, (this.namespaceMisses.get(namespace) || 0) + 1);
  }

  private recordKeyAccess(namespace: CacheNamespace, key: string): void {
    const fullKey = `${namespace}:${key}`;
    const existing = this.keyAccess.get(fullKey);
    if (existing) {
      existing.count++;
      existing.lastAccess = Date.now();
    } else {
      this.keyAccess.set(fullKey, {
        count: 1,
        namespace,
        lastAccess: Date.now()
      });
    }
  }

  recordLatency(operation: string, duration: number, key?: string): void {
    if (!this.latencies.has(operation)) {
      this.latencies.set(operation, []);
    }
    this.latencies.get(operation)!.push(duration);

    if (duration >= this.SLOW_QUERY_THRESHOLD && key) {
      this.slowQueries.push({
        operation,
        duration,
        timestamp: Date.now(),
        key
      });

      // Keep only the most recent slow queries
      if (this.slowQueries.length > this.MAX_SLOW_QUERIES) {
        this.slowQueries.shift();
      }
    }
  }

  getMetrics(): CacheMetrics {
    const total = this.hits + this.misses;
    const hitRate = total > 0 ? this.hits / total : 0;

    const namespaceStats: Record<CacheNamespace, NamespaceStats> = {
      intraday: this.getNamespaceMetrics('intraday'),
      daily: this.getNamespaceMetrics('daily'),
      quarterly: this.getNamespaceMetrics('quarterly'),
      static: this.getNamespaceMetrics('static')
    };

    const hotKeys = Array.from(this.keyAccess.entries())
      .map(([fullKey, data]) => ({
        key: fullKey.split(':').slice(1).join(':'),
        namespace: data.namespace,
        accessCount: data.count,
        lastAccess: data.lastAccess
      }))
      .sort((a, b) => b.accessCount - a.accessCount)
      .slice(0, 10);

    return {
      hits: this.hits,
      misses: this.misses,
      hitRate,
      namespaceStats,
      hotKeys
    };
  }

  getNamespaceMetrics(namespace: CacheNamespace): NamespaceStats {
    const hits = this.namespaceHits.get(namespace) || 0;
    const misses = this.namespaceMisses.get(namespace) || 0;
    const total = hits + misses;
    const hitRate = total > 0 ? hits / total : 0;

    return { hits, misses, hitRate };
  }

  getLatencyStats(operation: string): LatencyStats {
    const latencies = this.latencies.get(operation) || [];
    if (latencies.length === 0) {
      return { count: 0, avg: 0, min: 0, max: 0, total: 0 };
    }

    const total = latencies.reduce((sum, val) => sum + val, 0);
    const avg = total / latencies.length;
    const min = Math.min(...latencies);
    const max = Math.max(...latencies);

    return { count: latencies.length, avg, min, max, total };
  }

  getSlowQueries(): SlowQuery[] {
    return [...this.slowQueries].sort((a, b) => b.duration - a.duration);
  }

  reset(): void {
    this.hits = 0;
    this.misses = 0;
    this.namespaceHits.clear();
    this.namespaceMisses.clear();
    this.keyAccess.clear();
    this.latencies.clear();
    this.slowQueries = [];
  }
}

export const cacheMonitor = CacheMonitor.getInstance();
