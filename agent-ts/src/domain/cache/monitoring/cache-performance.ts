import type { PerformanceStats, SlowQuery } from '../core/types.js';

export class CachePerformance {
  private timings: Map<string, number[]>;
  private slowQueries: SlowQuery[];

  constructor() {
    this.timings = new Map();
    this.slowQueries = [];
  }

  recordTiming(operation: string, duration: number, key?: string): void {
    if (!this.timings.has(operation)) {
      this.timings.set(operation, []);
    }
    this.timings.get(operation)!.push(duration);

    if (key) {
      this.slowQueries.push({
        operation,
        duration,
        timestamp: Date.now(),
        key
      });

      if (this.slowQueries.length > 1000) {
        this.slowQueries = this.slowQueries.slice(-1000);
      }
    }
  }

  getStats(operation: string): PerformanceStats {
    const durations = this.timings.get(operation);

    if (!durations || durations.length === 0) {
      return {
        count: 0,
        avg: 0,
        p50: 0,
        p95: 0,
        p99: 0,
        max: 0
      };
    }

    const sorted = [...durations].sort((a, b) => a - b);
    const count = sorted.length;
    const sum = sorted.reduce((a, b) => a + b, 0);

    return {
      count,
      avg: sum / count,
      p50: this.percentile(sorted, 0.5),
      p95: this.percentile(sorted, 0.95),
      p99: this.percentile(sorted, 0.99),
      max: sorted[sorted.length - 1]
    };
  }

  private percentile(sorted: number[], p: number): number {
    const index = Math.ceil(sorted.length * p) - 1;
    return sorted[Math.max(0, index)];
  }

  getSlowQueries(threshold: number): SlowQuery[] {
    return this.slowQueries
      .filter(q => q.duration >= threshold)
      .sort((a, b) => b.duration - a.duration);
  }

  reset(): void {
    this.timings.clear();
    this.slowQueries = [];
  }
}

export const cachePerformance = new CachePerformance();
