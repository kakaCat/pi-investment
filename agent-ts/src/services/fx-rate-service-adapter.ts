/**
 * FxRateServiceAdapter - 使用新缓存系统的汇率服务适配器
 *
 * 保持与旧 FxRateService 相同的接口,但使用新的缓存领域实现
 */

import { readFileSync, writeFileSync, existsSync } from "fs";
import { join } from "path";
import { fetchSinaFxRate } from "../infrastructure/providers/market/sina-fx.js";
import { chinaDate, chinaDateTime } from "../utils/china-time.js";
import { CacheManager } from "../domain/cache/core/cache-manager.js";

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

export class FxRateServiceAdapter {
  private static readonly CACHE_FRESH_HOURS = 24;
  private static readonly DEFAULT_HKDCNY_RATE = 0.88;

  private cachePath: string;
  private cacheManager: CacheManager;

  constructor(piDir: string) {
    this.cachePath = join(piDir, "fx-rates.json");
    this.cacheManager = CacheManager.getInstance();
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
    return diffHours > FxRateServiceAdapter.CACHE_FRESH_HOURS;
  }

  async getRate(pair: "HKDCNY"): Promise<number> {
    try {
      // 1. 尝试从新缓存系统读取
      const cacheKey = `fx:${pair}`;
      const cached = await this.cacheManager.get<{
        rate: number;
        date: string;
        updated_at: string;
        source: string;
      }>('daily', cacheKey);

      if (cached && !this.isCacheStale(cached.date)) {
        return cached.rate;
      }

      // 2. 尝试从旧 JSON 文件读取（向后兼容）
      const oldCache = this.loadCache();
      const oldCached = oldCache.rates[pair];

      if (oldCached && !this.isCacheStale(oldCached.date)) {
        // 迁移到新缓存
        await this.cacheManager.set('daily', cacheKey, oldCached);
        return oldCached.rate;
      }

      // 3. 从网络获取新汇率
      const rate = await this.fetchRateFromSina(pair);

      const rateData = {
        rate,
        date: chinaDate(),
        updated_at: chinaDateTime(),
        source: "sina"
      };

      // 同时写入新缓存和旧文件（过渡期）
      await this.cacheManager.set('daily', cacheKey, rateData);

      oldCache.rates[pair] = rateData;
      oldCache.last_updated = chinaDateTime();
      this.saveCache(oldCache);

      return rate;

    } catch (error) {
      // 4. 尝试从新缓存读取过期数据
      const cacheKey = `fx:${pair}`;
      const staleCache = await this.cacheManager.get<{
        rate: number;
        date: string;
      }>('daily', cacheKey);

      if (staleCache) {
        console.warn(`⚠️ 汇率获取失败，使用缓存值: ${staleCache.rate} (${staleCache.date})`);
        return staleCache.rate;
      }

      // 5. 尝试从旧文件读取过期数据
      const oldCache = this.loadCache();
      if (oldCache.rates[pair]) {
        console.warn(`⚠️ 汇率获取失败，使用旧缓存值: ${oldCache.rates[pair].rate} (${oldCache.rates[pair].date})`);
        return oldCache.rates[pair].rate;
      }

      // 6. 使用默认值
      console.error(`❌ 汇率获取失败且无缓存，使用默认值 ${FxRateServiceAdapter.DEFAULT_HKDCNY_RATE}`);
      return FxRateServiceAdapter.DEFAULT_HKDCNY_RATE;
    }
  }

  async updateCache(): Promise<void> {
    try {
      const rate = await this.fetchRateFromSina("HKDCNY");
      const rateData = {
        rate,
        date: chinaDate(),
        updated_at: chinaDateTime(),
        source: "sina"
      };

      // 写入新缓存
      await this.cacheManager.set('daily', `fx:HKDCNY`, rateData);

      // 写入旧文件（过渡期）
      const oldCache = this.loadCache();
      oldCache.rates["HKDCNY"] = rateData;
      oldCache.last_updated = chinaDateTime();
      this.saveCache(oldCache);

    } catch (error) {
      console.error("❌ 更新汇率缓存失败:", error);
    }
  }
}
