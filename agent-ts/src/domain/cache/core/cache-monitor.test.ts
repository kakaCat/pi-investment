import { describe, it, expect, beforeEach } from '@jest/globals';
import { CacheMonitor } from './cache-monitor.js';
import type { CacheNamespace } from './types.js';

describe('CacheMonitor', () => {
  let monitor: CacheMonitor;

  beforeEach(() => {
    monitor = CacheMonitor.getInstance();
    monitor.reset();
  });

  it('should be a singleton', () => {
    const instance1 = CacheMonitor.getInstance();
    const instance2 = CacheMonitor.getInstance();
    expect(instance1).toBe(instance2);
  });

  it('should record cache hits', () => {
    monitor.recordHit('intraday', 'test-key');
    monitor.recordHit('intraday', 'test-key');
    monitor.recordHit('daily', 'other-key');

    const metrics = monitor.getMetrics();
    expect(metrics.hits).toBe(3);
    expect(metrics.misses).toBe(0);
    expect(metrics.hitRate).toBe(1);
  });

  it('should record cache misses', () => {
    monitor.recordMiss('intraday', 'test-key');
    monitor.recordMiss('daily', 'other-key');

    const metrics = monitor.getMetrics();
    expect(metrics.hits).toBe(0);
    expect(metrics.misses).toBe(2);
    expect(metrics.hitRate).toBe(0);
  });

  it('should calculate hit rate correctly', () => {
    monitor.recordHit('intraday', 'key1');
    monitor.recordHit('intraday', 'key2');
    monitor.recordHit('intraday', 'key3');
    monitor.recordMiss('intraday', 'key4');

    const metrics = monitor.getMetrics();
    expect(metrics.hits).toBe(3);
    expect(metrics.misses).toBe(1);
    expect(metrics.hitRate).toBe(0.75);
  });

  it('should track namespace-specific stats', () => {
    monitor.recordHit('intraday', 'key1');
    monitor.recordHit('intraday', 'key2');
    monitor.recordMiss('intraday', 'key3');
    monitor.recordHit('daily', 'key4');

    const metrics = monitor.getMetrics();
    expect(metrics.namespaceStats.intraday.hits).toBe(2);
    expect(metrics.namespaceStats.intraday.misses).toBe(1);
    expect(metrics.namespaceStats.intraday.hitRate).toBeCloseTo(0.667, 2);
    expect(metrics.namespaceStats.daily.hits).toBe(1);
    expect(metrics.namespaceStats.daily.misses).toBe(0);
    expect(metrics.namespaceStats.daily.hitRate).toBe(1);
  });

  it('should track hot keys', () => {
    monitor.recordHit('intraday', 'hot-key');
    monitor.recordHit('intraday', 'hot-key');
    monitor.recordHit('intraday', 'hot-key');
    monitor.recordHit('intraday', 'cold-key');

    const metrics = monitor.getMetrics();
    expect(metrics.hotKeys).toHaveLength(2);
    expect(metrics.hotKeys[0].key).toBe('hot-key');
    expect(metrics.hotKeys[0].accessCount).toBe(3);
    expect(metrics.hotKeys[1].key).toBe('cold-key');
    expect(metrics.hotKeys[1].accessCount).toBe(1);
  });

  it('should limit hot keys to top 10', () => {
    for (let i = 0; i < 20; i++) {
      monitor.recordHit('intraday', `key-${i}`);
    }

    const metrics = monitor.getMetrics();
    expect(metrics.hotKeys).toHaveLength(10);
  });

  it('should record operation latency', () => {
    monitor.recordLatency('get', 10);
    monitor.recordLatency('get', 20);
    monitor.recordLatency('get', 30);
    monitor.recordLatency('set', 5);

    const stats = monitor.getLatencyStats('get');
    expect(stats.count).toBe(3);
    expect(stats.avg).toBe(20);
    expect(stats.min).toBe(10);
    expect(stats.max).toBe(30);
  });

  it('should track slow queries', () => {
    monitor.recordLatency('get', 150, 'slow-key');
    monitor.recordLatency('get', 200, 'very-slow-key');
    monitor.recordLatency('get', 50, 'fast-key');

    const slowQueries = monitor.getSlowQueries();
    expect(slowQueries).toHaveLength(2);
    expect(slowQueries[0].key).toBe('very-slow-key');
    expect(slowQueries[0].duration).toBe(200);
    expect(slowQueries[1].key).toBe('slow-key');
    expect(slowQueries[1].duration).toBe(150);
  });

  it('should reset metrics', () => {
    monitor.recordHit('intraday', 'key1');
    monitor.recordMiss('intraday', 'key2');
    monitor.recordLatency('get', 100);

    monitor.reset();

    const metrics = monitor.getMetrics();
    expect(metrics.hits).toBe(0);
    expect(metrics.misses).toBe(0);
    expect(metrics.hotKeys).toHaveLength(0);
  });

  it('should get namespace-specific metrics', () => {
    monitor.recordHit('intraday', 'key1');
    monitor.recordHit('intraday', 'key2');
    monitor.recordMiss('daily', 'key3');

    const intradayMetrics = monitor.getNamespaceMetrics('intraday');
    expect(intradayMetrics.hits).toBe(2);
    expect(intradayMetrics.misses).toBe(0);
    expect(intradayMetrics.hitRate).toBe(1);

    const dailyMetrics = monitor.getNamespaceMetrics('daily');
    expect(dailyMetrics.hits).toBe(0);
    expect(dailyMetrics.misses).toBe(1);
    expect(dailyMetrics.hitRate).toBe(0);
  });
});
