/**
 * End-to-End Integration Tests for Cache Domain
 *
 * Tests the complete cache system including:
 * - All four namespaces (intraday, daily, quarterly, static)
 * - All three adapters (kline, fx-rate, python-caller)
 * - Cross-namespace operations
 * - Real-world workflows
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { CacheManager } from '../../core/cache-manager.js';
import { KlineCacheAdapter } from '../../../../services/data/kline-cache-adapter.js';
import { FxRateServiceAdapter } from '../../../../services/fx-rate-service-adapter.js';
import { callPythonResilient, clearAllCaches } from '../../../../infrastructure/tools/shared/python-caller-resilient-adapter.js';
import { StockDBService } from '../../../../services/data/stock-db-service.js';
import { mkdirSync, rmSync, existsSync } from 'fs';
import { join } from 'path';

const TEST_DIR = '/tmp/cache-e2e-test';
const TEST_DB_PATH = join(TEST_DIR, 'test-stocks.db');

describe('Cache System E2E Integration Tests', () => {
  let cacheManager: CacheManager;
  let testDb: StockDBService;

  beforeEach(async () => {
    // Clean up test directory
    if (existsSync(TEST_DIR)) {
      rmSync(TEST_DIR, { recursive: true, force: true });
    }
    mkdirSync(TEST_DIR, { recursive: true });

    // Initialize cache manager
    cacheManager = CacheManager.getInstance();

    // Clear all namespaces
    await Promise.all([
      cacheManager.clear('intraday'),
      cacheManager.clear('daily'),
      cacheManager.clear('quarterly'),
      cacheManager.clear('static'),
    ]);

    // Initialize test database
    testDb = new StockDBService(TEST_DB_PATH);
  });

  afterEach(() => {
    // Clean up
    if (existsSync(TEST_DIR)) {
      rmSync(TEST_DIR, { recursive: true, force: true });
    }
  });

  describe('Multi-Namespace Operations', () => {
    it('should handle concurrent operations across all namespaces', async () => {
      // Set data in all namespaces concurrently
      await Promise.all([
        cacheManager.set('intraday', 'test-intraday', { value: 'intraday-data' }),
        cacheManager.set('daily', 'test-daily', { value: 'daily-data' }),
        cacheManager.set('quarterly', 'test-quarterly', { value: 'quarterly-data' }),
        cacheManager.set('static', 'test-static', { value: 'static-data' }),
      ]);

      // Verify all data is accessible
      const [intradayData, dailyData, quarterlyData, staticData] = await Promise.all([
        cacheManager.get('intraday', 'test-intraday'),
        cacheManager.get('daily', 'test-daily'),
        cacheManager.get('quarterly', 'test-quarterly'),
        cacheManager.get('static', 'test-static'),
      ]);

      expect(intradayData).toEqual({ value: 'intraday-data' });
      expect(dailyData).toEqual({ value: 'daily-data' });
      expect(quarterlyData).toEqual({ value: 'quarterly-data' });
      expect(staticData).toEqual({ value: 'static-data' });
    });

    it('should maintain namespace isolation', async () => {
      await cacheManager.set('intraday', 'shared-key', { namespace: 'intraday' });
      await cacheManager.set('daily', 'shared-key', { namespace: 'daily' });

      const intradayData = await cacheManager.get('intraday', 'shared-key');
      const dailyData = await cacheManager.get('daily', 'shared-key');

      expect(intradayData).toEqual({ namespace: 'intraday' });
      expect(dailyData).toEqual({ namespace: 'daily' });
    });

    it('should clear only the specified namespace', async () => {
      // Set data in multiple namespaces
      await cacheManager.set('intraday', 'test', { ns: 'intraday' });
      await cacheManager.set('daily', 'test', { ns: 'daily' });
      await cacheManager.set('static', 'test', { ns: 'static' });

      // Clear only intraday
      await cacheManager.clear('intraday');

      // Verify only intraday is cleared
      expect(await cacheManager.get('intraday', 'test')).toBeNull();
      expect(await cacheManager.get('daily', 'test')).toEqual({ ns: 'daily' });
      expect(await cacheManager.get('static', 'test')).toEqual({ ns: 'static' });
    });
  });

  describe('Adapter Integration', () => {
    it('should work with KlineCacheAdapter for daily K-line data', async () => {
      const adapter = new KlineCacheAdapter(testDb);

      // Mock some data in the database first
      const klineData = [
        { date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 1000000 },
        { date: '2024-01-02', open: 105, high: 115, low: 100, close: 110, volume: 1200000 },
      ];
      testDb.saveKlines('000001', klineData);

      // Get K-line data through adapter (should use cache)
      const retrieved = await adapter.getHistory('000001', '2024-01-01', '2024-01-02');
      expect(retrieved).toHaveLength(2);
      expect(retrieved[0]).toMatchObject({ date: '2024-01-01', close: 105 });

      // Verify it's cached in the daily namespace
      const cacheKey = 'kline:000001:2024-01-01:2024-01-02';
      const cached = await cacheManager.get('daily', cacheKey);
      expect(cached).toBeDefined();
      expect(cached).toHaveLength(2);
    });

    it('should work with FxRateServiceAdapter for FX rates', async () => {
      const adapter = new FxRateServiceAdapter(TEST_DIR);

      // Pre-populate cache with fresh test data (today's date to avoid staleness check)
      const today = new Date().toISOString().split('T')[0];
      await cacheManager.set('daily', 'fx:HKDCNY', {
        rate: 0.92,
        date: today,
        updated_at: `${today} 10:00:00`,
        source: 'test'
      });

      // Get FX rate (should use cache)
      const rate = await adapter.getRate('HKDCNY');
      expect(rate).toBe(0.92);
    });

    it('should work with callPythonResilient for Python calls', async () => {
      // Clear all caches first
      await clearAllCaches();

      // Call a Python function (will likely fail but should return structured response)
      const result = await callPythonResilient('get_stock_realtime_price', { symbol: '000001' });

      // Should return a result (either success or structured error)
      expect(result).toBeDefined();
      expect(typeof result).toBe('string');

      // If it's an error, it should have alternatives
      try {
        const parsed = JSON.parse(result);
        if (parsed.error) {
          expect(parsed._alternatives).toBeDefined();
          expect(Array.isArray(parsed._alternatives)).toBe(true);
        }
      } catch {
        // If not JSON, it's a successful result (unlikely in test environment)
      }
    });
  });

  describe('Real-World Workflow Simulation', () => {
    it('should handle a complete trading day workflow', async () => {
      const klineAdapter = new KlineCacheAdapter(testDb);
      const fxAdapter = new FxRateServiceAdapter(TEST_DIR);

      // 1. Morning: Set up FX rates in cache (use today's date to avoid staleness)
      const today = new Date().toISOString().split('T')[0];
      await cacheManager.set('daily', 'fx:HKDCNY', {
        rate: 0.92,
        date: today,
        updated_at: `${today} 09:00:00`,
        source: 'test'
      });

      // 2. Market open: Cache some intraday data
      await cacheManager.set('intraday', 'python:get_stock_realtime_price:{"symbol":"000001"}',
        JSON.stringify({ data: { price: 100, volume: 1000000 }, timestamp: Date.now() })
      );

      // 3. During trading: Access cached data multiple times
      const quote1 = await cacheManager.get('intraday', 'python:get_stock_realtime_price:{"symbol":"000001"}');
      const quote2 = await cacheManager.get('intraday', 'python:get_stock_realtime_price:{"symbol":"000001"}');
      expect(quote1).toEqual(quote2);
      expect(quote1).toBeDefined();

      // 4. Market close: Save daily K-line data
      const klineData = [
        { date: '2024-01-01', open: 100, high: 110, low: 95, close: 105, volume: 5000000 },
      ];
      testDb.saveKlines('000001', klineData);

      // 5. Market close: Clear intraday cache (simulating event-driven invalidation)
      await cacheManager.clear('intraday');

      // 6. Verify intraday cache is cleared but daily remains
      const clearedQuote = await cacheManager.get('intraday', 'python:get_stock_realtime_price:{"symbol":"000001"}');
      expect(clearedQuote).toBeNull();

      const fxRate = await fxAdapter.getRate('HKDCNY');
      expect(fxRate).toBe(0.92);
    });

    it('should handle quarterly earnings update workflow', async () => {
      // 1. Cache old earnings data
      await cacheManager.set('quarterly', 'earnings:000001', {
        quarter: 'Q4-2023',
        revenue: 1000000,
        profit: 100000,
      });

      // 2. Verify cached data
      const oldEarnings = await cacheManager.get('quarterly', 'earnings:000001');
      expect(oldEarnings).toHaveProperty('quarter', 'Q4-2023');

      // 3. Simulate earnings release: clear quarterly cache
      await cacheManager.clear('quarterly');

      // 4. Verify cache is invalidated
      const clearedEarnings = await cacheManager.get('quarterly', 'earnings:000001');
      expect(clearedEarnings).toBeNull();

      // 5. Cache new earnings data
      await cacheManager.set('quarterly', 'earnings:000001', {
        quarter: 'Q1-2024',
        revenue: 1200000,
        profit: 150000,
      });

      // 6. Verify new data
      const newEarnings = await cacheManager.get('quarterly', 'earnings:000001');
      expect(newEarnings).toHaveProperty('quarter', 'Q1-2024');
      expect(newEarnings).toHaveProperty('revenue', 1200000);
    });

    it('should handle pattern-based invalidation', async () => {
      // Cache multiple K-line entries for the same symbol
      await cacheManager.set('daily', 'kline:000001:2024-01-01:2024-01-31', []);
      await cacheManager.set('daily', 'kline:000001:2024-02-01:2024-02-29', []);
      await cacheManager.set('daily', 'kline:000002:2024-01-01:2024-01-31', []);

      // Invalidate all 000001 K-line data
      const count = await cacheManager.invalidateByPattern('daily', 'kline:000001:*');
      expect(count).toBe(2);

      // Verify 000001 data is cleared but 000002 remains
      expect(await cacheManager.get('daily', 'kline:000001:2024-01-01:2024-01-31')).toBeNull();
      expect(await cacheManager.get('daily', 'kline:000001:2024-02-01:2024-02-29')).toBeNull();
      expect(await cacheManager.get('daily', 'kline:000002:2024-01-01:2024-01-31')).toEqual([]);
    });
  });

  describe('Error Handling and Edge Cases', () => {
    it('should handle missing cache keys gracefully', async () => {
      const result = await cacheManager.get('daily', 'non-existent-key');
      expect(result).toBeNull();
    });

    it('should handle concurrent writes to the same key', async () => {
      // Write to the same key concurrently
      await Promise.all([
        cacheManager.set('daily', 'concurrent-key', { version: 1 }),
        cacheManager.set('daily', 'concurrent-key', { version: 2 }),
        cacheManager.set('daily', 'concurrent-key', { version: 3 }),
      ]);

      // Should have one of the values (last write wins)
      const result = await cacheManager.get('daily', 'concurrent-key');
      expect(result).toBeDefined();
      expect(result).toHaveProperty('version');
      expect([1, 2, 3]).toContain((result as any).version);
    });

    it('should handle various data types', async () => {
      // Cache various data types
      await cacheManager.set('daily', 'string', 'test-string');
      await cacheManager.set('daily', 'number', 12345);
      await cacheManager.set('daily', 'boolean', true);
      await cacheManager.set('daily', 'array', [1, 2, 3]);
      await cacheManager.set('daily', 'object', { nested: { value: 'deep' } });

      // Verify all types are retrieved correctly
      expect(await cacheManager.get('daily', 'string')).toBe('test-string');
      expect(await cacheManager.get('daily', 'number')).toBe(12345);
      expect(await cacheManager.get('daily', 'boolean')).toBe(true);
      expect(await cacheManager.get('daily', 'array')).toEqual([1, 2, 3]);
      expect(await cacheManager.get('daily', 'object')).toEqual({ nested: { value: 'deep' } });
    });

    it('should handle cache deletion', async () => {
      await cacheManager.set('daily', 'to-delete', { value: 'will-be-deleted' });
      expect(await cacheManager.get('daily', 'to-delete')).toEqual({ value: 'will-be-deleted' });

      await cacheManager.delete('daily', 'to-delete');
      expect(await cacheManager.get('daily', 'to-delete')).toBeNull();
    });

    it('should handle namespace clearing', async () => {
      // Set multiple keys
      await cacheManager.set('daily', 'key1', { value: 1 });
      await cacheManager.set('daily', 'key2', { value: 2 });
      await cacheManager.set('daily', 'key3', { value: 3 });

      // Clear namespace
      await cacheManager.clear('daily');

      // Verify all keys are cleared
      expect(await cacheManager.get('daily', 'key1')).toBeNull();
      expect(await cacheManager.get('daily', 'key2')).toBeNull();
      expect(await cacheManager.get('daily', 'key3')).toBeNull();
    });
  });

  describe('Performance and Scalability', () => {
    it('should handle high-frequency cache operations', async () => {
      const operations = 100; // Reduced for faster tests
      const startTime = Date.now();

      // Perform set operations
      const setPromises = Array.from({ length: operations }, (_, i) =>
        cacheManager.set('intraday', `key-${i}`, { value: i })
      );
      await Promise.all(setPromises);

      // Perform get operations
      const getPromises = Array.from({ length: operations }, (_, i) =>
        cacheManager.get('intraday', `key-${i}`)
      );
      const results = await Promise.all(getPromises);

      const totalTime = Date.now() - startTime;

      // Verify all operations completed
      expect(results).toHaveLength(operations);
      expect(results.every((r: any, i: number) => r?.value === i)).toBe(true);

      // Should complete within reasonable time (2 seconds for 200 operations)
      expect(totalTime).toBeLessThan(2000);
    });

    it('should handle mixed read/write workload', async () => {
      // Pre-populate some data
      await Promise.all(
        Array.from({ length: 20 }, (_, i) =>
          cacheManager.set('daily', `key-${i}`, { value: i })
        )
      );

      // Simulate mixed workload: 70% reads, 30% writes
      const operations = 100;
      const promises = Array.from({ length: operations }, (_, i) => {
        if (i % 10 < 7) {
          // 70% reads
          return cacheManager.get('daily', `key-${i % 20}`);
        } else {
          // 30% writes
          return cacheManager.set('daily', `key-${i % 20}`, { value: i });
        }
      });

      const startTime = Date.now();
      await Promise.all(promises);
      const totalTime = Date.now() - startTime;

      // Should complete within reasonable time
      expect(totalTime).toBeLessThan(1000);
    });

    it('should handle batch operations efficiently', async () => {
      // Test mset (batch set)
      const entries = new Map<string, any>();
      for (let i = 0; i < 50; i++) {
        entries.set(`batch-key-${i}`, { value: i });
      }

      const setStartTime = Date.now();
      await cacheManager.mset('daily', entries);
      const setTime = Date.now() - setStartTime;

      // Test mget (batch get)
      const keys = Array.from({ length: 50 }, (_, i) => `batch-key-${i}`);
      const getStartTime = Date.now();
      const results = await cacheManager.mget('daily', keys);
      const getTime = Date.now() - getStartTime;

      // Verify results
      expect(results.size).toBe(50);
      expect(results.get('batch-key-0')).toEqual({ value: 0 });
      expect(results.get('batch-key-49')).toEqual({ value: 49 });

      // Should be reasonably fast
      expect(setTime).toBeLessThan(1000);
      expect(getTime).toBeLessThan(500);
    });
  });
});
