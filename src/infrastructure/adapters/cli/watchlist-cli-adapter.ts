import { BaseCliAdapter } from './base-cli-adapter.js';
import { WatchlistItem } from './types.js';
import { CliExecutionError } from './types.js';

export class WatchlistCliAdapter extends BaseCliAdapter {
  /**
   * 列出观察列表
   */
  async list(params: {
    pool?: string;
    priority?: number;
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
    market: 'A' | 'HK';
    reason: string;
    buyRangeLow: number;
    buyRangeHigh?: number;
    targetPrice?: number;
    stopLoss?: number;
    priority?: number;
    pool?: 'A' | 'B' | 'C';
    notes?: string;
  }): Promise<string> {
    // Convert camelCase to snake_case for CLI
    const params: Record<string, string | number | boolean> = {
      symbol: data.symbol,
      name: data.name,
      market: data.market,
      reason: data.reason,
      buy_range_low: data.buyRangeLow,
    };
    if (data.buyRangeHigh !== undefined) params.buy_range_high = data.buyRangeHigh;
    if (data.targetPrice !== undefined) params.target_price = data.targetPrice;
    if (data.stopLoss !== undefined) params.stop_loss = data.stopLoss;
    if (data.priority !== undefined) params.priority = data.priority;
    if (data.pool !== undefined) params.pool = data.pool;
    if (data.notes !== undefined) params.notes = data.notes;

    const result = await this.executeCommand('watchlist', 'add', params);
    return result.id;
  }

  /**
   * 更新观察列表项
   */
  async update(symbol: string, data: Partial<WatchlistItem>): Promise<boolean> {
    // Convert camelCase to snake_case for CLI
    const params: Record<string, string | number | boolean> = { symbol };

    if (data.name !== undefined) params.name = data.name;
    if (data.market !== undefined) params.market = data.market;
    if (data.priority !== undefined) params.priority = data.priority;
    if (data.pool !== undefined) params.pool = data.pool;
    if (data.status !== undefined) params.status = data.status;
    if (data.buyRangeLow !== undefined) params.buy_range_low = data.buyRangeLow;
    if (data.buyRangeHigh !== undefined) params.buy_range_high = data.buyRangeHigh;
    if (data.targetPrice !== undefined) params.target_price = data.targetPrice;
    if (data.stopLoss !== undefined) params.stop_loss = data.stopLoss;
    if (data.reason !== undefined) params.reason = data.reason;
    if (data.notes !== undefined) params.notes = data.notes;

    const result = await this.executeCommand('watchlist', 'update', params);
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
