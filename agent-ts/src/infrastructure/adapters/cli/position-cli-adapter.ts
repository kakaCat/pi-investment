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
  async get(symbol: string, accountId?: string): Promise<Position | null> {
    try {
      const params: Record<string, string | number | boolean> = { symbol };
      if (accountId) params.accountId = accountId;
      const result = await this.executeCommand('position', 'get', params);

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
   * 开仓或加仓
   */
  async open(params: {
    symbol: string;
    quantity: number;
    /** 成本价（人民币） */
    costBasis: number;
    /** 入场日期 YYYY-MM-DD，默认今天 */
    entryDate?: string;
    /** 入场理由 */
    entryReason?: string;
    notes?: string;
    accountId?: string;
  }): Promise<Position> {
    const cmdParams: Record<string, string | number | boolean> = {
      symbol: params.symbol!,
      quantity: params.quantity,
      cost_basis: params.costBasis,
    };
    if (params.entryDate) cmdParams.entry_date = params.entryDate;
    if (params.entryReason) cmdParams.entry_reason = params.entryReason;
    if (params.notes) cmdParams.notes = params.notes;
    if (params.accountId) cmdParams.account_id = params.accountId;

    const result = await this.executeCommand('position', 'open', cmdParams);

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
      notes: result.notes,
    };
  }

  /**
   * 更新持仓
   */
  async update(
    symbol: string,
    data: {
      quantity?: number;
      costBasis?: number;
      price?: number;
      stopLoss?: number;
      takeProfit?: number;
      notes?: string;
    },
    accountId?: string
  ): Promise<boolean> {
    const cmdParams: Record<string, string | number | boolean> = {
      symbol,
      accountId: accountId || 'default',
    };
    // Use snake_case for CLI params
    if (data.quantity !== undefined) cmdParams.quantity = data.quantity;
    if (data.costBasis !== undefined) cmdParams.cost_basis = data.costBasis;
    if (data.price !== undefined) cmdParams.price = data.price;
    if (data.stopLoss !== undefined) cmdParams.stop_loss = data.stopLoss;
    if (data.takeProfit !== undefined) cmdParams.take_profit = data.takeProfit;
    if (data.notes !== undefined) cmdParams.notes = data.notes;

    const result = await this.executeCommand('position', 'update', cmdParams);
    return result.updated_rows > 0;
  }

  /**
   * 关闭持仓
   */
  async close(
    symbol: string,
    reason?: string,
    accountId?: string
  ): Promise<boolean> {
    const params: Record<string, string | number | boolean> = { symbol };
    if (accountId) params.accountId = accountId;
    if (reason !== undefined) params.reason = reason;
    const result = await this.executeCommand('position', 'close', params);
    return result.closed === true;
  }

  /**
   * 获取持仓汇总
   */
  async getSummary(accountId?: string): Promise<PositionSummary> {
    const params: Record<string, string | number | boolean> = {};
    if (accountId) params.accountId = accountId;
    const result = await this.executeCommand('position', 'summary', params);

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
