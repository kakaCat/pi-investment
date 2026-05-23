import { BaseCliAdapter } from './base-cli-adapter.js';
import { Position, PositionSummary } from './types.js';
import { CliExecutionError } from './types.js';

export class PositionCliAdapter extends BaseCliAdapter {
  /**
   * 列出持仓
   */
  async list(params: {
    accountId?: string;
    status?: string;
  } = {}): Promise<Position[]> {
    const result = await this.executeCommand('position', 'list', params);
    const positions = result.positions || [];

    // Map snake_case from CLI to camelCase for TypeScript
    return positions.map((p: any) => ({
      symbol: p.symbol,
      name: p.name,
      quantity: p.quantity,
      costBasis: p.cost_basis,
      currentPrice: p.current_price,
      entryDate: p.entry_date,
      stopLoss: p.stop_loss,
      takeProfit: p.take_profit,
      status: p.status,
      accountId: p.account_id,
      notes: p.notes
    }));
  }

  /**
   * 获取单个持仓
   */
  async get(symbol: string, accountId: string = 'default'): Promise<Position | null> {
    try {
      const result = await this.executeCommand('position', 'get', { symbol, accountId });

      // Map snake_case from CLI to camelCase for TypeScript
      return {
        symbol: result.symbol,
        name: result.name,
        quantity: result.quantity,
        costBasis: result.cost_basis,
        currentPrice: result.current_price,
        entryDate: result.entry_date,
        stopLoss: result.stop_loss,
        takeProfit: result.take_profit,
        status: result.status,
        accountId: result.account_id,
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
   * 更新持仓
   */
  async update(
    symbol: string,
    data: {
      quantity?: number;
      price?: number;
      stopLoss?: number;
      takeProfit?: number;
      notes?: string;
    },
    accountId: string = 'default'
  ): Promise<boolean> {
    const result = await this.executeCommand('position', 'update', {
      symbol,
      accountId,
      ...data
    });
    return result.updated_rows > 0;
  }

  /**
   * 关闭持仓
   */
  async close(
    symbol: string,
    reason?: string,
    accountId: string = 'default'
  ): Promise<boolean> {
    const params: Record<string, string | number | boolean> = {
      symbol,
      accountId
    };
    if (reason !== undefined) {
      params.reason = reason;
    }
    const result = await this.executeCommand('position', 'close', params);
    return result.closed === true;
  }

  /**
   * 获取持仓汇总
   */
  async getSummary(accountId: string = 'default'): Promise<PositionSummary> {
    const result = await this.executeCommand('position', 'summary', { accountId });

    // Map snake_case from CLI to camelCase for TypeScript
    return {
      totalPositions: result.total_positions,
      totalQuantity: result.total_quantity,
      totalCost: result.total_cost,
      totalMarketValue: result.total_market_value,
      totalPnl: result.total_pnl,
      totalPnlPct: result.total_pnl_pct
    };
  }
}
