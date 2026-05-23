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
    return result.positions || [];
  }

  /**
   * 获取单个持仓
   */
  async get(symbol: string, accountId: string = 'default'): Promise<Position | null> {
    try {
      return await this.executeCommand('position', 'get', { symbol, accountId });
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
    return await this.executeCommand('position', 'summary', { accountId });
  }
}
