/**
 * KlineCacheAdapter - 使用新缓存系统的 K线数据缓存适配器
 *
 * 保持与旧 KlineCacheService 相同的接口,但使用新的缓存领域实现
 */

import { CacheManager } from '../../domain/cache/core/cache-manager.js';
import { StockDBService } from './stock-db-service.js';
import { callPython } from '../../infrastructure/akshare-ts/index.js';

export class KlineCacheAdapter {
  private cacheManager: CacheManager;

  constructor(private db: StockDBService) {
    this.cacheManager = CacheManager.getInstance();
  }

  /** 获取K线（智能缓存） */
  async getHistory(symbol: string, startDate: string, endDate: string): Promise<any[]> {
    // 1. 尝试从新缓存系统读取
    const cacheKey = `kline:${symbol}:${startDate}:${endDate}`;
    const cached = await this.cacheManager.get<any[]>('daily', cacheKey);

    if (cached && cached.length > 0) {
      // 检查数据完整性
      const expectedDays = this.calcTradingDays(startDate, endDate);
      if (cached.length >= expectedDays * 0.9) {
        return cached;
      }
    }

    // 2. 尝试从旧 SQLite 数据库读取（向后兼容）
    const local = this.db.getKlines(symbol, startDate, endDate);
    const expectedDays = this.calcTradingDays(startDate, endDate);

    if (local.length >= expectedDays * 0.9) {
      // 数据完整，写入新缓存并返回
      await this.cacheManager.set('daily', cacheKey, local);
      return local;
    }

    // 3. 数据缺失，从API拉取
    console.log(`[KlineCacheAdapter] ${symbol} 本地数据不足，从API拉取...`);
    const args = {
      symbol,
      start_date: startDate,
      end_date: endDate,
      _skip_cache: true,
    };

    try {
      const raw = await callPython('get_stock_history', args);
      const data = JSON.parse(raw);

      if (Array.isArray(data.data)) {
        // 同时写入旧数据库和新缓存（过渡期）
        this.db.saveKlines(symbol, data.data);
        await this.cacheManager.set('daily', cacheKey, data.data);
        return data.data;
      }
    } catch (err) {
      console.error(`[KlineCacheAdapter] ${symbol} 数据拉取失败:`, err);
    }

    return local;
  }

  /** 增量更新（只拉取缺失部分） */
  async updateSymbol(symbol: string, days: number = 730): Promise<number> {
    const latest = this.db.getLatestKlineDate(symbol);
    const endDate = new Date().toISOString().split('T')[0];

    let startDate: string;
    if (latest) {
      const d = new Date(latest);
      d.setDate(d.getDate() + 1);
      startDate = d.toISOString().split('T')[0];
    } else {
      const d = new Date();
      d.setDate(d.getDate() - days);
      startDate = d.toISOString().split('T')[0];
    }

    if (startDate >= endDate) return 0;

    try {
      const raw = await callPython('get_stock_history', {
        symbol,
        start_date: startDate,
        end_date: endDate,
        _skip_cache: true,
      });
      const data = JSON.parse(raw);

      if (Array.isArray(data.data)) {
        // 写入旧数据库
        const count = this.db.saveKlines(symbol, data.data);

        // 清除新缓存中的相关数据（因为数据已更新）
        await this.cacheManager.invalidateByPattern('daily', `kline:${symbol}:*`);

        return count;
      }
    } catch (err) {
      console.error(`[KlineCacheAdapter] ${symbol} 增量更新失败:`, err);
    }
    return 0;
  }

  private calcTradingDays(start: string, end: string): number {
    const startTs = new Date(start).getTime();
    const endTs = new Date(end).getTime();
    if (isNaN(startTs) || isNaN(endTs)) return 0;
    const days = Math.floor((endTs - startTs) / 86400000);
    return Math.floor(days * 0.7);
  }
}
