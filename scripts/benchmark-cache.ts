/**
 * Performance Benchmark for Cache Domain
 *
 * Compares performance of new cache system against legacy implementations
 * and measures throughput, latency, and resource usage.
 */

import { CacheManager } from '../src/domain/cache/core/cache-manager.js';
import { performance } from 'perf_hooks';
import { mkdirSync, rmSync, existsSync } from 'fs';
import { join } from 'path';

const BENCHMARK_DIR = '/tmp/cache-benchmark';
const ITERATIONS = 1000;

interface BenchmarkResult {
  name: string;
  operations: number;
  totalTime: number;
  avgTime: number;
  opsPerSecond: number;
  minTime: number;
  maxTime: number;
}

class PerformanceBenchmark {
  private cacheManager: CacheManager;
  private results: BenchmarkResult[] = [];

  constructor() {
    this.cacheManager = CacheManager.getInstance();
  }

  async setup() {
    // Clean up benchmark directory
    if (existsSync(BENCHMARK_DIR)) {
      rmSync(BENCHMARK_DIR, { recursive: true, force: true });
    }
    mkdirSync(BENCHMARK_DIR, { recursive: true });

    // Clear all caches
    await Promise.all([
      this.cacheManager.clear('intraday'),
      this.cacheManager.clear('daily'),
      this.cacheManager.clear('quarterly'),
      this.cacheManager.clear('static'),
    ]);
  }

  async cleanup() {
    if (existsSync(BENCHMARK_DIR)) {
      rmSync(BENCHMARK_DIR, { recursive: true, force: true });
    }
  }

  private recordResult(result: BenchmarkResult) {
    this.results.push(result);
  }

  private async measureOperation(
    name: string,
    operation: () => Promise<void>,
    iterations: number = ITERATIONS
  ): Promise<BenchmarkResult> {
    const times: number[] = [];

    // Warm-up
    for (let i = 0; i < 10; i++) {
      await operation();
    }

    // Actual benchmark
    const startTime = performance.now();

    for (let i = 0; i < iterations; i++) {
      const opStart = performance.now();
      await operation();
      const opEnd = performance.now();
      times.push(opEnd - opStart);
    }

    const endTime = performance.now();
    const totalTime = endTime - startTime;

    const result: BenchmarkResult = {
      name,
      operations: iterations,
      totalTime,
      avgTime: totalTime / iterations,
      opsPerSecond: (iterations / totalTime) * 1000,
      minTime: Math.min(...times),
      maxTime: Math.max(...times),
    };

    this.recordResult(result);
    return result;
  }

  async benchmarkSetOperations() {
    console.log('\n=== Benchmark: Set Operations ===');

    // Small objects
    await this.measureOperation(
      'Set small object (intraday)',
      async () => {
        await this.cacheManager.set('intraday', `key-${Math.random()}`, { value: 123 });
      }
    );

    await this.measureOperation(
      'Set small object (daily)',
      async () => {
        await this.cacheManager.set('daily', `key-${Math.random()}`, { value: 123 });
      }
    );

    // Medium objects (K-line record)
    const klineRecord = {
      date: '2024-01-01',
      open: 100,
      high: 110,
      low: 95,
      close: 105,
      volume: 1000000,
    };

    await this.measureOperation(
      'Set medium object (daily)',
      async () => {
        await this.cacheManager.set('daily', `kline-${Math.random()}`, klineRecord);
      }
    );

    // Large objects (array of 100 K-line records)
    const largeData = Array.from({ length: 100 }, (_, i) => ({
      date: `2024-01-${String(i + 1).padStart(2, '0')}`,
      open: 100 + i,
      high: 110 + i,
      low: 95 + i,
      close: 105 + i,
      volume: 1000000 + i * 1000,
    }));

    await this.measureOperation(
      'Set large object (daily)',
      async () => {
        await this.cacheManager.set('daily', `large-${Math.random()}`, largeData);
      },
      100 // Fewer iterations for large objects
    );
  }

  async benchmarkGetOperations() {
    console.log('\n=== Benchmark: Get Operations ===');

    // Pre-populate cache
    const keys: string[] = [];
    for (let i = 0; i < 1000; i++) {
      const key = `bench-key-${i}`;
      keys.push(key);
      await this.cacheManager.set('daily', key, { value: i });
    }

    // Sequential reads
    let index = 0;
    await this.measureOperation(
      'Get existing key (daily)',
      async () => {
        await this.cacheManager.get('daily', keys[index++ % keys.length]);
      }
    );

    // Cache misses
    await this.measureOperation(
      'Get non-existent key (daily)',
      async () => {
        await this.cacheManager.get('daily', `missing-${Math.random()}`);
      }
    );

    // Memory cache (intraday)
    for (let i = 0; i < 1000; i++) {
      await this.cacheManager.set('intraday', `intraday-${i}`, { value: i });
    }

    index = 0;
    await this.measureOperation(
      'Get existing key (intraday)',
      async () => {
        await this.cacheManager.get('intraday', `intraday-${index++ % 1000}`);
      }
    );
  }

  async benchmarkBatchOperations() {
    console.log('\n=== Benchmark: Batch Operations ===');

    // Batch set (mset)
    await this.measureOperation(
      'Batch set 10 keys (mset)',
      async () => {
        const entries = new Map();
        for (let i = 0; i < 10; i++) {
          entries.set(`batch-${Math.random()}-${i}`, { value: i });
        }
        await this.cacheManager.mset('daily', entries);
      },
      100
    );

    await this.measureOperation(
      'Batch set 50 keys (mset)',
      async () => {
        const entries = new Map();
        for (let i = 0; i < 50; i++) {
          entries.set(`batch-${Math.random()}-${i}`, { value: i });
        }
        await this.cacheManager.mset('daily', entries);
      },
      50
    );

    // Batch get (mget)
    const keys: string[] = [];
    for (let i = 0; i < 100; i++) {
      const key = `mget-key-${i}`;
      keys.push(key);
      await this.cacheManager.set('daily', key, { value: i });
    }

    await this.measureOperation(
      'Batch get 10 keys (mget)',
      async () => {
        await this.cacheManager.mget('daily', keys.slice(0, 10));
      }
    );

    await this.measureOperation(
      'Batch get 50 keys (mget)',
      async () => {
        await this.cacheManager.mget('daily', keys.slice(0, 50));
      }
    );
  }

  async benchmarkDeleteOperations() {
    console.log('\n=== Benchmark: Delete Operations ===');

    // Single delete
    await this.measureOperation(
      'Delete single key',
      async () => {
        const key = `delete-${Math.random()}`;
        await this.cacheManager.set('daily', key, { value: 123 });
        await this.cacheManager.delete('daily', key);
      }
    );

    // Pattern-based invalidation
    await this.measureOperation(
      'Invalidate by pattern (10 matches)',
      async () => {
        const prefix = `pattern-${Math.random()}`;
        for (let i = 0; i < 10; i++) {
          await this.cacheManager.set('daily', `${prefix}-${i}`, { value: i });
        }
        await this.cacheManager.invalidateByPattern('daily', `${prefix}*`);
      },
      100
    );

    // Clear namespace
    await this.measureOperation(
      'Clear namespace (100 keys)',
      async () => {
        for (let i = 0; i < 100; i++) {
          await this.cacheManager.set('intraday', `clear-${i}`, { value: i });
        }
        await this.cacheManager.clear('intraday');
      },
      10
    );
  }

  async benchmarkConcurrency() {
    console.log('\n=== Benchmark: Concurrent Operations ===');

    // Concurrent writes
    await this.measureOperation(
      'Concurrent writes (10 parallel)',
      async () => {
        const promises = Array.from({ length: 10 }, (_, i) =>
          this.cacheManager.set('intraday', `concurrent-${Math.random()}-${i}`, { value: i })
        );
        await Promise.all(promises);
      },
      100
    );

    // Concurrent reads
    const keys: string[] = [];
    for (let i = 0; i < 100; i++) {
      const key = `read-${i}`;
      keys.push(key);
      await this.cacheManager.set('daily', key, { value: i });
    }

    await this.measureOperation(
      'Concurrent reads (10 parallel)',
      async () => {
        const promises = Array.from({ length: 10 }, (_, i) =>
          this.cacheManager.get('daily', keys[i % keys.length])
        );
        await Promise.all(promises);
      }
    );

    // Mixed workload
    await this.measureOperation(
      'Mixed workload (7 reads, 3 writes)',
      async () => {
        const promises = Array.from({ length: 10 }, (_, i) => {
          if (i < 7) {
            return this.cacheManager.get('daily', keys[i % keys.length]);
          } else {
            return this.cacheManager.set('intraday', `mixed-${Math.random()}`, { value: i });
          }
        });
        await Promise.all(promises);
      }
    );
  }

  async benchmarkNamespaceComparison() {
    console.log('\n=== Benchmark: Namespace Comparison ===');

    const testData = { value: 123, timestamp: Date.now() };

    await this.measureOperation(
      'Set/Get intraday (memory)',
      async () => {
        const key = `ns-${Math.random()}`;
        await this.cacheManager.set('intraday', key, testData);
        await this.cacheManager.get('intraday', key);
      }
    );

    await this.measureOperation(
      'Set/Get daily (sqlite)',
      async () => {
        const key = `ns-${Math.random()}`;
        await this.cacheManager.set('daily', key, testData);
        await this.cacheManager.get('daily', key);
      }
    );

    await this.measureOperation(
      'Set/Get static (file)',
      async () => {
        const key = `ns-${Math.random()}`;
        await this.cacheManager.set('static', key, testData);
        await this.cacheManager.get('static', key);
      }
    );
  }

  printResults() {
    console.log('\n' + '='.repeat(80));
    console.log('PERFORMANCE BENCHMARK RESULTS');
    console.log('='.repeat(80));
    console.log();

    console.log('| Operation | Ops | Total (ms) | Avg (ms) | Ops/sec | Min (ms) | Max (ms) |');
    console.log('|-----------|-----|------------|----------|---------|----------|----------|');

    for (const result of this.results) {
      console.log(
        `| ${result.name.padEnd(40)} | ${String(result.operations).padStart(4)} | ` +
        `${result.totalTime.toFixed(2).padStart(10)} | ` +
        `${result.avgTime.toFixed(3).padStart(8)} | ` +
        `${result.opsPerSecond.toFixed(0).padStart(7)} | ` +
        `${result.minTime.toFixed(3).padStart(8)} | ` +
        `${result.maxTime.toFixed(3).padStart(8)} |`
      );
    }

    console.log();
    console.log('='.repeat(80));
  }

  printSummary() {
    console.log('\n=== Performance Summary ===\n');

    // Group by operation type
    const groups: Record<string, BenchmarkResult[]> = {};
    for (const result of this.results) {
      const type = result.name.split('(')[0].trim();
      if (!groups[type]) groups[type] = [];
      groups[type].push(result);
    }

    for (const [type, results] of Object.entries(groups)) {
      const avgOps = results.reduce((sum, r) => sum + r.opsPerSecond, 0) / results.length;
      const avgLatency = results.reduce((sum, r) => sum + r.avgTime, 0) / results.length;

      console.log(`${type}:`);
      console.log(`  Average throughput: ${avgOps.toFixed(0)} ops/sec`);
      console.log(`  Average latency: ${avgLatency.toFixed(3)} ms`);
      console.log();
    }

    // Performance targets
    console.log('=== Performance Targets ===\n');

    const targets = [
      { name: 'Memory cache (intraday) read', target: 10000, unit: 'ops/sec' },
      { name: 'SQLite cache (daily) read', target: 5000, unit: 'ops/sec' },
      { name: 'Memory cache write', target: 5000, unit: 'ops/sec' },
      { name: 'SQLite cache write', target: 2000, unit: 'ops/sec' },
      { name: 'Batch operations (10 keys)', target: 1000, unit: 'ops/sec' },
    ];

    for (const target of targets) {
      const matching = this.results.find(r => r.name.includes(target.name));
      if (matching) {
        const achieved = matching.opsPerSecond;
        const status = achieved >= target.target ? '✓ PASS' : '✗ FAIL';
        console.log(`${status} ${target.name}: ${achieved.toFixed(0)} / ${target.target} ${target.unit}`);
      }
    }
  }

  async run() {
    console.log('Starting Cache Domain Performance Benchmark...\n');
    console.log(`Iterations per test: ${ITERATIONS}`);
    console.log(`Benchmark directory: ${BENCHMARK_DIR}\n`);

    await this.setup();

    try {
      await this.benchmarkSetOperations();
      await this.benchmarkGetOperations();
      await this.benchmarkBatchOperations();
      await this.benchmarkDeleteOperations();
      await this.benchmarkConcurrency();
      await this.benchmarkNamespaceComparison();

      this.printResults();
      this.printSummary();
    } finally {
      await this.cleanup();
    }

    console.log('\nBenchmark completed successfully!');
  }
}

// Run benchmark
const benchmark = new PerformanceBenchmark();
benchmark.run().catch(console.error);
