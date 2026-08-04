import { describe, test, expect, beforeEach, afterEach, jest } from "@jest/globals";
import type { FxRatesFile } from "./fx-rate-service-adapter.js";
import { mkdirSync, rmSync, existsSync, writeFileSync } from "fs";
import { join } from "path";
import { chinaDate, chinaDateTime } from "../utils/china-time.js";

// Mock CacheManager to avoid real cache operations in tests
// ESM 下 jest.mock 不提升，必须用 unstable_mockModule + 动态 import；
// 否则真实 CacheManager 的持久缓存会跨测试/跨运行污染（读到 live 汇率）
jest.unstable_mockModule("../domain/cache/core/cache-manager.js", () => ({
  CacheManager: {
    getInstance: () => ({
      get: jest.fn(async () => null),
      set: jest.fn(async () => undefined),
    }),
  },
}));

const { FxRateServiceAdapter } = await import("./fx-rate-service-adapter.js");

const TEST_DIR = join(process.cwd(), ".test-fx-rates");

describe("FxRateServiceAdapter", () => {
  beforeEach(() => {
    if (existsSync(TEST_DIR)) rmSync(TEST_DIR, { recursive: true });
    mkdirSync(TEST_DIR, { recursive: true });
  });

  afterEach(() => {
    if (existsSync(TEST_DIR)) rmSync(TEST_DIR, { recursive: true });
  });

  test("initializes with empty cache file", () => {
    const service = new FxRateServiceAdapter(TEST_DIR);
    const cachePath = join(TEST_DIR, "fx-rates.json");
    expect(existsSync(cachePath)).toBe(true);
  });

  test("fetches FX rate from Sina", async () => {
    const service = new FxRateServiceAdapter(TEST_DIR);
    const rate = await service.fetchRateFromSina("HKDCNY");
    expect(rate).toBeGreaterThan(0);
    expect(rate).toBeLessThan(2);
  }, 15000);

  test("getRate returns cached rate if fresh", async () => {
    const service = new FxRateServiceAdapter(TEST_DIR);

    // Manually write a fresh cache
    const cache: FxRatesFile = {
      rates: {
        HKDCNY: {
          rate: 0.8850,
          date: chinaDate(),
          updated_at: chinaDateTime(),
          source: "sina"
        }
      },
      last_updated: chinaDateTime()
    };
    writeFileSync(join(TEST_DIR, "fx-rates.json"), JSON.stringify(cache, null, 2));

    const rate = await service.getRate("HKDCNY");
    expect(rate).toBeCloseTo(0.8850, 2); // 允许 2 位小数精度
  });

  test("getRate fetches new rate if cache stale", async () => {
    const service = new FxRateServiceAdapter(TEST_DIR);

    // Write a stale cache (2 days ago)
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 2);
    const staleDate = yesterday.toISOString().split("T")[0];

    const cache: FxRatesFile = {
      rates: {
        HKDCNY: {
          rate: 0.8850,
          date: staleDate,
          updated_at: staleDate,
          source: "sina"
        }
      },
      last_updated: staleDate
    };
    writeFileSync(join(TEST_DIR, "fx-rates.json"), JSON.stringify(cache, null, 2));

    const rate = await service.getRate("HKDCNY");
    expect(rate).toBeGreaterThan(0);
    expect(rate).not.toBe(0.8850); // Should fetch new rate
  }, 15000);

  test("getRate uses stale cache if fetch fails", async () => {
    const service = new FxRateServiceAdapter(TEST_DIR);

    // Write a stale cache
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 2);
    const staleDate = yesterday.toISOString().split("T")[0];

    const cache: FxRatesFile = {
      rates: {
        HKDCNY: {
          rate: 0.8850,
          date: staleDate,
          updated_at: staleDate,
          source: "sina"
        }
      },
      last_updated: staleDate
    };
    writeFileSync(join(TEST_DIR, "fx-rates.json"), JSON.stringify(cache, null, 2));

    // Mock fetchRateFromSina to fail
    service.fetchRateFromSina = async () => {
      throw new Error("Network error");
    };

    const rate = await service.getRate("HKDCNY");
    expect(rate).toBeCloseTo(0.8850, 2); // 允许 2 位小数精度 // Should use stale cache
  });

  test("getRate uses default if no cache and fetch fails", async () => {
    const service = new FxRateServiceAdapter(TEST_DIR);

    // Mock fetchRateFromSina to fail
    service.fetchRateFromSina = async () => {
      throw new Error("Network error");
    };

    const rate = await service.getRate("HKDCNY");
    expect(rate).toBe(0.88); // Default fallback
  });

  test("updateCache fetches and saves new rate", async () => {
    const service = new FxRateServiceAdapter(TEST_DIR);

    await service.updateCache();

    const rate = await service.getRate("HKDCNY");
    expect(rate).toBeGreaterThan(0);
    expect(rate).toBeLessThan(2);
  }, 15000);
});
