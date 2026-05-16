import { readFileSync, writeFileSync, existsSync } from "fs";
import { join } from "path";
import { fetchSinaFxRate } from "../infrastructure/data-sources/sina-fx.js";
import { chinaDate, chinaDateTime } from "../utils/china-time.js";

export interface FxRatesFile {
  rates: {
    [pair: string]: {
      rate: number;
      date: string;
      updated_at: string;
      source: string;
    };
  };
  last_updated: string;
}

export class FxRateService {
  private static readonly CACHE_FRESH_HOURS = 24;
  private static readonly DEFAULT_HKDCNY_RATE = 0.88; // Historical average fallback

  private cachePath: string;

  constructor(piDir: string) {
    this.cachePath = join(piDir, "fx-rates.json");
    this.ensureCache();
  }

  private ensureCache(): void {
    if (!existsSync(this.cachePath)) {
      const empty: FxRatesFile = {
        rates: {},
        last_updated: ""
      };
      writeFileSync(this.cachePath, JSON.stringify(empty, null, 2), "utf-8");
    }
  }

  private loadCache(): FxRatesFile {
    try {
      const content = readFileSync(this.cachePath, "utf-8");
      return JSON.parse(content) as FxRatesFile;
    } catch (error) {
      return { rates: {}, last_updated: "" };
    }
  }

  private saveCache(data: FxRatesFile): void {
    writeFileSync(this.cachePath, JSON.stringify(data, null, 2), "utf-8");
  }

  async fetchRateFromSina(pair: "HKDCNY"): Promise<number> {
    return fetchSinaFxRate(pair);
  }

  private isCacheStale(date: string): boolean {
    const cacheDate = new Date(date);
    const now = new Date();
    const diffHours = (now.getTime() - cacheDate.getTime()) / (1000 * 60 * 60);
    return diffHours > FxRateService.CACHE_FRESH_HOURS;
  }

  async getRate(pair: "HKDCNY"): Promise<number> {
    try {
      // 1. Try cache (if fresh)
      const cache = this.loadCache();
      const cached = cache.rates[pair];

      if (cached && !this.isCacheStale(cached.date)) {
        return cached.rate;
      }

      // 2. Fetch new rate
      const rate = await this.fetchRateFromSina(pair);

      // Save to cache
      cache.rates[pair] = {
        rate,
        date: chinaDate(),
        updated_at: chinaDateTime(),
        source: "sina"
      };
      cache.last_updated = chinaDateTime();
      this.saveCache(cache);

      return rate;

    } catch (error) {
      // 3. Use stale cache if available
      const cache = this.loadCache();
      if (cache.rates[pair]) {
        console.warn(`⚠️ 汇率获取失败，使用缓存值: ${cache.rates[pair].rate} (${cache.rates[pair].date})`);
        return cache.rates[pair].rate;
      }

      // 4. Use default fallback
      console.error(`❌ 汇率获取失败且无缓存，使用默认值 ${FxRateService.DEFAULT_HKDCNY_RATE}`);
      return FxRateService.DEFAULT_HKDCNY_RATE;
    }
  }

  async updateCache(): Promise<void> {
    try {
      const rate = await this.fetchRateFromSina("HKDCNY");
      const cache = this.loadCache();

      cache.rates["HKDCNY"] = {
        rate,
        date: chinaDate(),
        updated_at: chinaDateTime(),
        source: "sina"
      };
      cache.last_updated = chinaDateTime();

      this.saveCache(cache);
    } catch (error) {
      console.error("❌ 更新汇率缓存失败:", error);
      // Don't throw - let cron job continue
    }
  }
}
