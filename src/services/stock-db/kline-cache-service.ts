/**
 * KlineCacheService - K线数据缓存
 *
 * 智能缓存策略：
 * 1. 优先从本地读取
 * 2. 缺失则从API拉取并存储
 * 3. 支持增量更新
 */

import { StockDBService } from './stock-db-service.js';
import { callPython } from '../../infrastructure/tools/invest-tools.js';

export class KlineCacheService {
  constructor(private db: StockDBService) {}

  /** 获取K线（智能缓存） */
  async getHistory(symbol: string, startDate: string, endDate: string): Promise<any[]> {
    // 1. 尝试从本地读取
    const local = this.db.getKlines(symbol, startDate, endDate);

    // 2. 检查是否完整
    const expectedDays = this.calcTradingDays(startDate, endDate);
    if (local.length >= expectedDays * 0.9) {
      return local; // 数据完整，直接返回
    }

    // 3. 数据缺失，从API拉取
    console.log(`[KlineCache] ${symbol} 本地数据不足，从API拉取并存入数据库...`);
    const args = {
      symbol,
      start_date: startDate,
      end_date: endDate,
      _skip_cache: true,   // 防止 TS 路径再次进入 KlineCache 造成死循环
    };

    try {
      // 通过 callPython 获取数据，akshare_bridge 会处理具体的 API 逻辑
      const raw = await callPython('get_stock_history', args);
      const data = JSON.parse(raw);

      if (Array.isArray(data.data)) {
        this.db.saveKlines(symbol, data.data);
        return data.data;
      }
    } catch (err) {
      console.error(`[KlineCache] ${symbol} 数据拉取失败:`, err);
    }

    return local; // 失败则返回已有的部分本地数据
  }

  /** 增量更新（只拉取缺失部分） */
  async updateSymbol(symbol: string, days: number = 730): Promise<number> {
    const latest = this.db.getLatestKlineDate(symbol);
    const endDate = new Date().toISOString().split('T')[0];

    let startDate: string;
    if (latest) {
      // 从最新日期后一天开始
      const d = new Date(latest);
      d.setDate(d.getDate() + 1);
      startDate = d.toISOString().split('T')[0];
    } else {
      // 首次拉取，默认2年
      const d = new Date();
      d.setDate(d.getDate() - days);
      startDate = d.toISOString().split('T')[0];
    }

    if (startDate >= endDate) return 0; // 已是最新

    try {
      const raw = await callPython('get_stock_history', {
        symbol,
        start_date: startDate,
        end_date: endDate,
        _skip_cache: true,   // 防止死循环
      });
      const data = JSON.parse(raw);

      if (Array.isArray(data.data)) {
        return this.db.saveKlines(symbol, data.data);
      }
    } catch (err) {
      console.error(`[KlineCache] ${symbol} 增量更新失败:`, err);
    }
    return 0;
  }

  private calcTradingDays(start: string, end: string): number {
    const startTs = new Date(start).getTime();
    const endTs = new Date(end).getTime();
    if (isNaN(startTs) || isNaN(endTs)) return 0;
    const days = Math.floor((endTs - startTs) / 86400000);
    return Math.floor(days * 0.7); // 粗略估算交易日
  }
}
