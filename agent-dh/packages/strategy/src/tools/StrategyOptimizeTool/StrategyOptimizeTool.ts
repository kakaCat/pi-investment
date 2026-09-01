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
    const raw: any = await this.qv2.optimizeStrategy({
      strategy_id: args.strategy_id,
      param_ranges: args.param_ranges,
      symbol: args.symbols?.[0] || '',
      start_date: args.start_date || '',
      end_date: args.end_date || '',
      sort_by: args.optimization_target === 'return' ? 'total_return' : args.optimization_target === 'win_rate' ? 'win_rate' : 'sharpe_ratio',
    });

    // 2026-09-01 G-1 修复：后端实际返回 {success, results[], totalCombinations,
    // successfulCombinations}（results 每项 {params, sharpeRatio, totalReturn,
    // maxDrawdown, winRate}），与工具 output 契约的 best_params/best_score/
    // all_results 不符——原代码直接透传导致 render 层 best_score.toFixed 崩溃
    // （toFixed on undefined）。这里做字段适配，契约保持不变。
    const results: any[] = Array.isArray(raw?.results) ? raw.results : [];
    const targetKey =
      args.optimization_target === 'return' ? 'totalReturn'
      : args.optimization_target === 'win_rate' ? 'winRate'
      : 'sharpeRatio';
    const valid = results.filter((r) => r && typeof r[targetKey] === 'number');
    const best = valid.reduce(
      (acc, r) => (acc == null || r[targetKey] > acc[targetKey] ? r : acc),
      null as any
    );

    return {
      best_params: best?.params ?? {},
      best_score: best?.[targetKey] ?? 0,
      all_results: results,
      total_combinations: raw?.totalCombinations ?? results.length,
      successful_combinations: raw?.successfulCombinations ?? valid.length,
    } as any;
  }

  protected wrap(data: StrategyOptimizeResult): ToolResponse<StrategyOptimizeResult> {
    return { success: true, data };
  }
}
