import { BaseCliAdapter } from './base-cli-adapter.js';
import { Account } from './types.js';
import { CliExecutionError } from './types.js';

export class AccountCliAdapter extends BaseCliAdapter {
  /**
   * 获取账户信息
   */
  async get(name: string = 'Default Account'): Promise<Account | null> {
    try {
      const result = await this.executeCommand('account', 'get', { name });

      // Map snake_case from CLI to camelCase for TypeScript
      return {
        name: result.name,
        currentCapital: result.current_capital,
        currency: result.currency,
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
   * 更新账户信息
   */
  async update(
    name: string,
    data: {
      capital?: number;
      currency?: string;
      notes?: string;
    }
  ): Promise<boolean> {
    const result = await this.executeCommand('account', 'update', {
      name,
      ...data
    });
    return result.updated_rows > 0;
  }
}
