/**
 * StrategyExecuteTool - 执行策略工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { strategyExecutePrompt, StrategyExecuteParams, StrategyExecuteResult } from './prompt';

export class StrategyExecuteTool extends BaseTool<StrategyExecuteParams, StrategyExecuteResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'strategy_execute',
    category: 'strategy',
    version: '2.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = strategyExecutePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: StrategyExecuteParams): ValidationResult {
    // 1. strategy_id 必填
    if (!args.strategy_id || !Number.isInteger(args.strategy_id)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'strategy_id',
        issue: 'strategy_id 必须是整数',
        received: args.strategy_id,
        expected: '整数策略ID',
        example: '1',
      };
    }

    // 2. mode 校验
    if (args.mode !== undefined) {
      const validModes = ['backtest', 'signal'];
      if (!validModes.includes(args.mode)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'mode',
          issue: 'mode 必须是 backtest 或 signal',
          received: args.mode,
          expected: 'backtest | signal',
        };
      }
    }

    // 3. backtest 模式需要日期
    if (args.mode === 'backtest') {
      if (!args.start_date || !/^\d{4}-\d{2}-\d{2}$/.test(args.start_date)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'start_date',
          issue: 'backtest 模式需要提供 start_date (YYYY-MM-DD)',
          received: args.start_date,
          expected: 'YYYY-MM-DD',
          example: '2025-01-01',
        };
      }

      if (!args.end_date || !/^\d{4}-\d{2}-\d{2}$/.test(args.end_date)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'end_date',
          issue: 'backtest 模式需要提供 end_date (YYYY-MM-DD)',
          received: args.end_date,
          expected: 'YYYY-MM-DD',
          example: '2026-01-01',
        };
      }
    }

    return { success: true };
  }

  protected async execute(
    args: StrategyExecuteParams,
    _context: ToolContext
  ): Promise<StrategyExecuteResult> {
    if (args.mode === 'backtest') {
      return this.qv2.backtestStrategy({
        strategy_id: args.strategy_id,
        symbol: args.symbols?.[0] || '',
        symbols: args.symbols,
        start_date: args.start_date || '',
        end_date: args.end_date || '',
        initial_capital: args.initial_capital || 100000,
      }) as any;
    }

    return this.qv2.generateSignals({
      strategy_id: args.strategy_id,
      symbols: args.symbols,
    }) as any;
  }

  protected wrap(data: StrategyExecuteResult): ToolResponse<StrategyExecuteResult> {
    return { success: true, data };
  }
}
