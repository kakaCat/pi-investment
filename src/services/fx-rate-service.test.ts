import { describe, test, expect, beforeEach, afterEach } from "@jest/globals";
import { FxRateService, FxRatesFile } from "./fx-rate-service.js";
import { mkdirSync, rmSync, existsSync, writeFileSync } from "fs";
import { join } from "path";
import { chinaDate, chinaDateTime } from "../utils/china-time.js";

const TEST_DIR = join(process.cwd(), ".test-fx-rates");

describe("FxRateService", () => {
  beforeEach(() => {
    if (existsSync(TEST_DIR)) rmSync(TEST_DIR, { recursive: true });
    mkdirSync(TEST_DIR, { recursive: true });
  });

  afterEach(() => {
    if (existsSync(TEST_DIR)) rmSync(TEST_DIR, { recursive: true });
  });

  test("initializes with empty cache file", () => {
    const service = new FxRateService(TEST_DIR);
    const cachePath = join(TEST_DIR, "fx-rates.json");
    expect(existsSync(cachePath)).toBe(true);
  });

  test("fetches FX rate from Sina", async () => {
    const service = new FxRateService(TEST_DIR);
    const rate = await service.fetchRateFromSina("HKDCNY");
    expect(rate).toBeGreaterThan(0);
    expect(rate).toBeLessThan(2);
  }, 15000);

  test("getRate returns cached rate if fresh", async () => {
    const service = new FxRateService(TEST_DIR);

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
    expect(rate).toBe(0.8850);
  });

  test("getRate fetches new rate if cache stale", async () => {
    const service = new FxRateService(TEST_DIR);

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
    const service = new FxRateService(TEST_DIR);

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
    expect(rate).toBe(0.8850); // Should use stale cache
  });

  test("getRate uses default if no cache and fetch fails", async () => {
    const service = new FxRateService(TEST_DIR);

    // Mock fetchRateFromSina to fail
    service.fetchRateFromSina = async () => {
      throw new Error("Network error");
    };

    const rate = await service.getRate("HKDCNY");
    expect(rate).toBe(0.88); // Default fallback
  });

  test("updateCache fetches and saves new rate", async () => {
    const service = new FxRateService(TEST_DIR);

    await service.updateCache();

    const rate = await service.getRate("HKDCNY");
    expect(rate).toBeGreaterThan(0);
    expect(rate).toBeLessThan(2);
  }, 15000);
});
