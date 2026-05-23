import { BaseCliAdapter } from './base-cli-adapter.js';
import { WatchlistItem } from './types.js';
import { CliExecutionError } from './types.js';

export class WatchlistCliAdapter extends BaseCliAdapter {
  /**
   * 列出观察列表
   */
  async list(params: {
    market?: string;
    pool?: string;
    status?: string;
  } = {}): Promise<WatchlistItem[]> {
    const result = await this.executeCommand('watchlist', 'list', params);
    const items = result.items || [];

    // Map snake_case from CLI to camelCase for TypeScript
    return items.map((item: any) => ({
      symbol: item.symbol,
      name: item.name,
      market: item.market,
      priority: item.priority,
      pool: item.pool,
      status: item.status,
      buyRangeLow: item.buy_range_low,
      buyRangeHigh: item.buy_range_high,
      targetPrice: item.target_price,
      stopLoss: item.stop_loss,
      reason: item.reason,
      notes: item.notes
    }));
  }

  /**
   * 获取单个观察列表项
   */
  async get(symbol: string): Promise<WatchlistItem | null> {
    try {
      const result = await this.executeCommand('watchlist', 'get', { symbol });

      // Map snake_case from CLI to camelCase for TypeScript
      return {
        symbol: result.symbol,
        name: result.name,
        market: result.market,
        priority: result.priority,
        pool: result.pool,
        status: result.status,
        buyRangeLow: result.buy_range_low,
        buyRangeHigh: result.buy_range_high,
        targetPrice: result.target_price,
        stopLoss: result.stop_loss,
        reason: result.reason,
        notes: result.notes
      };
    } catch (error) {
      if (error instanceof CliExecutionError && error.message.includes('not found')) {
        return null;
      }
      throw error;
    }
  }

  /**
   * 添加观察列表项
   */
  async add(data: {
    symbol: string;
    name: string;
    market?: string;
    priority?: number;
    pool?: string;
    status?: string;
    buyRangeLow?: number;
    buyRangeHigh?: number;
    targetPrice?: number;
    stopLoss?: number;
    reason?: string;
    notes?: string;
  }): Promise<WatchlistItem> {
    const result = await this.executeCommand('watchlist', 'add', data);

    // Map snake_case from CLI to camelCase for TypeScript
    return {
      symbol: result.symbol,
      name: result.name,
      market: result.market,
      priority: result.priority,
      pool: result.pool,
      status: result.status,
      buyRangeLow: result.buy_range_low,
      buyRangeHigh: result.buy_range_high,
      targetPrice: result.target_price,
      stopLoss: result.stop_loss,
      reason: result.reason,
      notes: result.notes
    };
  }

  /**
   * 更新观察列表项
   */
  async update(
    symbol: string,
    data: {
      priority?: number;
      pool?: string;
      status?: string;
      buyRangeLow?: number;
      buyRangeHigh?: number;
      targetPrice?: number;
      stopLoss?: number;
      reason?: string;
      notes?: string;
    }
  ): Promise<boolean> {
    const result = await this.executeCommand('watchlist', 'update', {
      symbol,
      ...data
    });
    return result.updated_rows > 0;
  }

  /**
   * 移除观察列表项
   */
  async remove(symbol: string): Promise<boolean> {
    const result = await this.executeCommand('watchlist', 'remove', { symbol });
    return result.removed === true;
  }
}
