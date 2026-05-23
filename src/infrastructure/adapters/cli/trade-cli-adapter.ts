import { BaseCliAdapter } from './base-cli-adapter.js';
import { Trade, TradeStats } from './types.js';
import { CliExecutionError } from './types.js';

export class TradeCliAdapter extends BaseCliAdapter {
  /**
   * 列出交易记录
   */
  async list(params: {
    symbol?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
  } = {}): Promise<Trade[]> {
    const result = await this.executeCommand('trade', 'list', params);
    const trades = result.trades || [];

    // Map snake_case from CLI to camelCase for TypeScript
    return trades.map((t: any) => ({
      id: t.id,
      symbol: t.symbol,
      name: t.name,
      action: t.action,
      quantity: t.quantity,
      price: t.price,
      timestamp: t.timestamp,
      realizedPnl: t.realized_pnl ?? 0,
      notes: t.notes ?? ''
    }));
  }

  /**
   * 获取单个交易记录
   */
  async get(tradeId: string): Promise<Trade | null> {
    try {
      const result = await this.executeCommand('trade', 'get', { trade_id: tradeId });

      // Map snake_case from CLI to camelCase for TypeScript
      return {
        id: result.id,
        symbol: result.symbol,
        name: result.name,
        action: result.action,
        quantity: result.quantity,
        price: result.price,
        timestamp: result.timestamp,
        realizedPnl: result.realized_pnl ?? 0,
        notes: result.notes ?? ''
      };
    } catch (error) {
      if (error instanceof CliExecutionError && error.message.includes('not found')) {
        return null;
      }
      throw error;
    }
  }

  /**
   * 获取交易统计
   */
  async getStats(params: {
    symbol?: string;
    period?: 'all' | 'year' | 'month' | 'week';
  } = {}): Promise<TradeStats> {
    const result = await this.executeCommand('trade', 'stats', params);

    // Map snake_case from CLI to camelCase for TypeScript
    return {
      totalTrades: result.total_trades,
      buyCount: result.buy_count,
      sellCount: result.sell_count,
      totalPnl: result.total_pnl,
      avgPnl: result.avg_pnl,
      winCount: result.win_count,
      lossCount: result.loss_count,
      winRate: result.win_rate
    };
  }
}
