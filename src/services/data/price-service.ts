/**
 * PriceService - 价格获取服务
 *
 * 策略：数据库缓存优先，接口兜底
 * 1. 先从数据库获取最新K线的收盘价（当日或最近一个交易日）
 * 2. 数据库没有或过期（>1天）则从接口批量获取
 * 3. 支持批量获取以提升性能
 */

import { StockDBService } from './stock-db-service.js';
import { callPython } from '../../infrastructure/akshare-ts/index.js';

export interface PriceResult {
  symbol: string;
  price: number | null;
  source: 'cache' | 'api' | 'fallback';
  asOf?: string;
}

export class PriceService {
  constructor(private db: StockDBService) {}

  /**
   * 批量获取股票价格（优化版）
   *
   * @param symbols 股票代码列表
   * @returns 价格映射 { symbol: price }
   */
  async getBatchPrices(symbols: string[]): Promise<Map<string, number>> {
    if (symbols.length === 0) {
      return new Map();
    }

    const result = new Map<string, number>();
    const needFetch: string[] = [];

    // 1. 先从数据库缓存获取
    for (const symbol of symbols) {
      const cached = this.getPriceFromCache(symbol);
      if (cached !== null) {
        result.set(symbol, cached);
      } else {
        needFetch.push(symbol);
      }
    }

    console.log(`[PriceService] 缓存命中: ${result.size}/${symbols.length}, 需要拉取: ${needFetch.length}`);

    // 2. 批量从接口获取缺失的价格
    if (needFetch.length > 0) {
      const apiPrices = await this.fetchBatchPricesFromAPI(needFetch);
      for (const [symbol, price] of apiPrices) {
        result.set(symbol, price);
      }
    }

    return result;
  }

  /**
   * 获取单个股票价格
   */
  async getPrice(symbol: string): Promise<number | null> {
    const prices = await this.getBatchPrices([symbol]);
    return prices.get(symbol) ?? null;
  }

  /**
   * 从数据库缓存获取价格（最新K线的收盘价）
   */
  private getPriceFromCache(symbol: string): number | null {
    try {
      // 获取最近3天的K线（考虑周末和节假日）
      const endDate = new Date().toISOString().split('T')[0];
      const startDate = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

      const klines = this.db.getKlines(symbol, startDate, endDate);

      if (klines.length === 0) {
        return null;
      }

      // 取最新一条K线的收盘价
      const latest = klines[klines.length - 1];
      const price = latest.close;

      // 检查数据是否过期（超过1天）
      const latestDate = new Date(latest.date);
      const now = new Date();
      const daysDiff = (now.getTime() - latestDate.getTime()) / (1000 * 60 * 60 * 24);

      if (daysDiff > 1) {
        // 数据过期，返回null触发API拉取
        return null;
      }

      return price > 0 ? price : null;
    } catch (err) {
      console.error(`[PriceService] 从缓存获取 ${symbol} 价格失败:`, err);
      return null;
    }
  }

  /**
   * 从API批量获取价格
   */
  private async fetchBatchPricesFromAPI(symbols: string[]): Promise<Map<string, number>> {
    const result = new Map<string, number>();

    try {
      const raw = await callPython('get_batch_realtime_prices', { symbols });
      const data = JSON.parse(raw);

      if (data.prices && typeof data.prices === 'object') {
        for (const [symbol, price] of Object.entries(data.prices)) {
          if (typeof price === 'number' && price > 0) {
            result.set(symbol, price);
          }
        }
      }

      if (data.errors && Array.isArray(data.errors) && data.errors.length > 0) {
        console.warn(`[PriceService] 部分股票获取失败:`, data.errors);
      }

      console.log(`[PriceService] API获取成功: ${result.size}/${symbols.length}`);
    } catch (err) {
      console.error(`[PriceService] 批量获取价格失败:`, err);

      // 降级：逐个获取
      console.log(`[PriceService] 降级为逐个获取...`);
      for (const symbol of symbols) {
        try {
          const price = await this.fetchSinglePriceFromAPI(symbol);
          if (price !== null) {
            result.set(symbol, price);
          }
        } catch (e) {
          console.error(`[PriceService] 获取 ${symbol} 失败:`, e);
        }
      }
    }

    return result;
  }

  /**
   * 从API获取单个价格（降级方案）
   */
  private async fetchSinglePriceFromAPI(symbol: string): Promise<number | null> {
    try {
      const raw = await callPython('get_stock_realtime_price', { symbol });
      const data = JSON.parse(raw);

      if (data.price && typeof data.price === 'number' && data.price > 0) {
        return data.price;
      }

      return null;
    } catch (err) {
      console.error(`[PriceService] 获取 ${symbol} 价格失败:`, err);
      return null;
    }
  }

  /**
   * 获取详细的价格结果（包含来源信息）
   */
  async getBatchPricesDetailed(symbols: string[]): Promise<PriceResult[]> {
    const results: PriceResult[] = [];
    const needFetch: string[] = [];

    // 1. 先从缓存获取
    for (const symbol of symbols) {
      const cached = this.getPriceFromCache(symbol);
      if (cached !== null) {
        results.push({
          symbol,
          price: cached,
          source: 'cache',
        });
      } else {
        needFetch.push(symbol);
      }
    }

    // 2. 从API获取
    if (needFetch.length > 0) {
      const apiPrices = await this.fetchBatchPricesFromAPI(needFetch);
      for (const symbol of needFetch) {
        const price = apiPrices.get(symbol);
        results.push({
          symbol,
          price: price ?? null,
          source: price !== undefined ? 'api' : 'fallback',
        });
      }
    }

    return results;
  }
}
