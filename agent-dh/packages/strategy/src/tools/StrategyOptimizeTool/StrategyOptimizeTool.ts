/**
 * StrategyOptimizeTool - 策略参数优化工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { strategyOptimizePrompt, StrategyOptimizeParams, StrategyOptimizeResult } from './prompt';

export class StrategyOptimizeTool extends BaseTool<StrategyOptimizeParams, StrategyOptimizeResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'strategy_optimize',
    category: 'strategy',
    version: '2.0.0',
    timeoutMs: 60000,
  };

  protected readonly prompt = strategyOptimizePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: StrategyOptimizeParams): ValidationResult {
    if (!args.strategy_id || !Number.isInteger(args.strategy_id)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'strategy_id',
        issue: 'strategy_id 必须是整数',
        received: args.strategy_id,
        expected: '整数策略ID',
      };
    }

    if (!args.param_ranges || typeof args.param_ranges !== 'object') {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'param_ranges',
        issue: 'param_ranges 必须是对象',
        received: args.param_ranges,
        expected: '{ param_name: [min, max] }',
      };
    }

    for (const [key, range] of Object.entries(args.param_ranges)) {
      if (!Array.isArray(range) || range.length !== 2) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: `param_ranges.${key}`,
          issue: '参数范围必须是长度为2的数组',
          received: range,
          expected: '[min, max]',
        };
      }
    }

    if (args.optimization_target) {
      const validTargets = ['sharpe', 'return', 'win_rate'];
      if (!validTargets.includes(args.optimization_target)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'optimization_target',
          issue: 'optimization_target 必须是 sharpe/return/win_rate',
          received: args.optimization_target,
          expected: 'sharpe | return | win_rate',
        };
      }
    }

    return { success: true };
  }

  protected async execute(
    args: StrategyOptimizeParams,
    _context: ToolContext
  ): Promise<StrategyOptimizeResult> {
    return this.qv2.optimizeStrategy({
      strategy_id: args.strategy_id,
      param_ranges: args.param_ranges,
      symbol: args.symbols?.[0] || '',
      symbols: args.symbols,
      start_date: args.start_date || '',
      end_date: args.end_date || '',
      optimization_target: args.optimization_target || 'sharpe',
    } as any) as any;
  }

  protected wrap(data: StrategyOptimizeResult): ToolResponse<StrategyOptimizeResult> {
    return { success: true, data };
  }
}
