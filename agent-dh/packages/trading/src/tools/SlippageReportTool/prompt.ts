/**
 * SlippageReportTool - 滑点报告工具提示词和类型定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 参数类型
 */
export interface SlippageReportParams {
  symbol?: string;
}

/**
 * 返回值类型
 */
export interface SlippageReportResult {
  total_fills: number;
  avg_slippage_pct: number;
  max_slippage_pct: number;
  by_symbol: Array<{
    symbol: string;
    fills: number;
    avg_slippage_pct: number;
    max_slippage_pct: number;
    [key: string]: any;
  }>;
  [key: string]: any;
}

/**
 * 工具提示词
 */
export const slippageReportPrompt: ToolPrompt<SlippageReportParams, SlippageReportResult> = {
  description: '滑点追踪报告：汇总 trade:slippage 落库记录——成交笔数、平均滑点、最大滑点、按标的分布。滑点=成交价 vs 决策时价（方向归一：正值=买贵/卖便宜）。供：评估模拟盘与真实成交的差距（P6 接真金前必看）、执行质量复盘。',

  useCases: [
    '评估模拟盘与真实成交的差距',
    '执行质量复盘',
    '分析不同标的的滑点表现',
  ],

  examples: [
    {
      title: '查看全部标的滑点',
      params: {},
      expectedResult: '返回全部成交记录的滑点统计',
    },
    {
      title: '查看单个标的滑点',
      params: {
        symbol: '600519',
      },
      expectedResult: '返回该标的的滑点统计',
    },
  ],

  notes: [
    '滑点 = 成交价 vs 决策时价（正值 = 买贵/卖便宜）',
    '数据来源：trade:slippage 落库记录',
    '接入真实账户前必看的执行质量指标',
    '只读操作，不会修改任何数据',
  ],

  relatedTools: [
    'trade_monitor',
    'algo_execute',
    'trade_verify',
  ],

  parameters: {
    symbol: {
      type: 'string',
      description: '可选：只看某只标的',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        total_fills: { type: 'number', description: '总成交笔数' },
        avg_slippage_pct: { type: 'number', description: '平均滑点（%）' },
        max_slippage_pct: { type: 'number', description: '最大滑点（%）' },
        by_symbol: {
          type: 'array',
          description: '按标的分组统计',
          items: { type: 'object', additionalProperties: true },
        },
      },
      additionalProperties: true,
    },
    render: (args, value) => [{
      type: 'text',
      text: JSON.stringify(value, null, 2),
    }],
  },
};
