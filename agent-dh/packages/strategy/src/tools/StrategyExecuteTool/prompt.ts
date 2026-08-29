/**
 * StrategyExecuteTool - 执行策略
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface StrategyExecuteParams {
  strategy_id: number;
  symbols?: string[];
  mode?: 'backtest' | 'signal';
  start_date?: string;
  end_date?: string;
  initial_capital?: number;
}

export interface StrategyExecuteResult {
  strategy_id: number;
  mode: string;
  signals?: any[];
  backtest_result?: any;
  [key: string]: any;
}

export const strategyExecutePrompt: ToolPrompt<StrategyExecuteParams, StrategyExecuteResult> = {
  description: '执行策略：基于最新数据生成买卖信号，或在历史数据上回测验证。适用于：盘前获取交易信号（signal 模式）、验证策略历史表现（backtest 模式）。先用 strategy_list 确认策略ID；优化策略参数用 evolution_run。',

  useCases: [
    '盘前获取交易信号',
    '验证策略历史表现',
    '回测策略收益',
  ],

  examples: [
    {
      title: '生成交易信号',
      params: { strategy_id: 1, mode: 'signal' },
      expectedResult: '返回买卖信号列表',
    },
    {
      title: '回测策略',
      params: { strategy_id: 1, mode: 'backtest', start_date: '2025-01-01', end_date: '2026-01-01' },
      expectedResult: '返回回测结果和收益指标',
    },
  ],

  notes: [
    '💡 signal 模式生成当前买卖信号',
    '💡 backtest 模式需要提供日期范围',
  ],

  relatedTools: ['strategy_list', 'strategy_optimize'],

  parameters: {
    strategy_id: {
      type: 'number',
      description: '策略ID，通过 strategy_list 获取',
      required: true,
      example: 1,
    },
    symbols: {
      type: 'array',
      description: '股票代码列表，如 ["600519", "000001"]。不传则由后端按策略默认范围执行',
      items: { type: 'string' },
      example: ['600519', '000001'],
    },
    mode: {
      type: 'string',
      description: '执行模式。signal（默认）：基于最新数据生成当前买卖信号；backtest：在历史数据上回测',
      enum: ['backtest', 'signal'],
      default: 'signal',
    },
    start_date: {
      type: 'string',
      description: '回测开始日期（mode=backtest时必填），格式 YYYY-MM-DD',
      example: '2025-01-02',
    },
    end_date: {
      type: 'string',
      description: '回测结束日期（mode=backtest时必填），格式 YYYY-MM-DD',
      example: '2026-08-21',
    },
    initial_capital: {
      type: 'number',
      description: '回测初始资金（mode=backtest时可选），默认 100000',
      default: 100000,
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        strategy_id: { type: 'number' },
        mode: { type: 'string' },
        signals: { type: 'array' },
        backtest_result: { type: 'object' },
      },
    },
    render: (_args, data) => [{ type: 'text', text: JSON.stringify(data, null, 2) }],
  },
};
