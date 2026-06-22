import { describe, it, expect, beforeEach } from '@jest/globals';
import { CachePerformance } from './cache-performance.js';

describe('CachePerformance', () => {
  let perf: CachePerformance;

  beforeEach(() => {
    perf = new CachePerformance();
  });

  it('should record timing', () => {
    perf.recordTiming('get', 10);
    perf.recordTiming('get', 20);
    perf.recordTiming('get', 30);

    const stats = perf.getStats('get');
    expect(stats.count).toBe(3);
    expect(stats.avg).toBe(20);
    expect(stats.p50).toBe(20);
  });

  it('should calculate percentiles correctly', () => {
    for (let i = 1; i <= 100; i++) {
      perf.recordTiming('test', i);
    }

    const stats = perf.getStats('test');
    expect(stats.p50).toBe(50);
    expect(stats.p95).toBe(95);
    expect(stats.p99).toBe(99);
    expect(stats.max).toBe(100);
  });

  it('should track slow queries', () => {
    perf.recordTiming('slow-op', 150, 'key1');
    perf.recordTiming('fast-op', 5, 'key2');
    perf.recordTiming('slow-op', 200, 'key3');

    const slowQueries = perf.getSlowQueries(100);
    expect(slowQueries).toHaveLength(2);
    expect(slowQueries[0].operation).toBe('slow-op');
    expect(slowQueries[0].duration).toBeGreaterThanOrEqual(100);
  });

  it('should return empty stats for unknown operation', () => {
    const stats = perf.getStats('unknown');
    expect(stats.count).toBe(0);
    expect(stats.avg).toBe(0);
  });
});
