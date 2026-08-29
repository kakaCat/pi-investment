/**
 * StrategyOptimizeTool - 策略参数优化工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface StrategyOptimizeParams {
  strategy_id: number;
  param_ranges: Record<string, [number, number]>;
  symbols?: string[];
  start_date?: string;
  end_date?: string;
  optimization_target?: 'sharpe' | 'return' | 'win_rate';
}

export interface StrategyOptimizeResult {
  best_params: Record<string, number>;
  best_score: number;
  all_results: Array<{
    params: Record<string, number>;
    score: number;
    metrics: Record<string, number>;
  }>;
}

export const strategyOptimizePrompt: ToolPrompt<StrategyOptimizeParams, StrategyOptimizeResult> = {
  description: '优化策略参数，通过网格搜索或贝叶斯优化找到最佳参数组合',
  useCases: [
    '提升策略表现',
    '参数敏感性分析',
    '寻找最优持仓周期',
    '优化止损止盈阈值',
  ],
  parameters: {
    strategy_id: {
      type: 'number',
      required: true,
      description: '策略ID',
      example: 1,
    },
    param_ranges: {
      type: 'object', additionalProperties: true,
      required: true,
      description: '参数搜索范围，key为参数名，value为[min, max]',
      example: { hold_days: [3, 10], stop_loss: [-0.05, -0.02] },
    },
    symbols: {
      type: 'array',
      description: '测试股票池',
      example: ['000001', '600519'],
    },
    start_date: {
      type: 'string',
      description: '回测开始日期 YYYY-MM-DD',
      example: '2024-01-01',
    },
    end_date: {
      type: 'string',
      description: '回测结束日期 YYYY-MM-DD',
      example: '2025-12-31',
    },
    optimization_target: {
      type: 'string',
      description: '优化目标：sharpe/return/win_rate',
      example: 'sharpe',
    },
  },
  examples: [],

  notes: [],

  relatedTools: [],


  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        best_params: { type: 'object', additionalProperties: true, description: '最优参数组合' },
        best_score: { type: 'number', description: '最优得分' },
        all_results: { type: 'array', description: '所有测试结果' },
      },
    },
    render: (args, data) => [
      { type: 'text', text: `✅ 策略 ${args.strategy_id} 参数优化完成` },
      { type: 'text', text: `` },
      { type: 'text', text: `🎯 最优参数: ${JSON.stringify(data.best_params)}` },
      { type: 'text', text: `📊 最优得分: ${data.best_score.toFixed(4)}` },
      { type: 'text', text: `` },
      { type: 'text', text: `共测试 ${data.all_results.length} 组参数` },
    ],
  },
};
