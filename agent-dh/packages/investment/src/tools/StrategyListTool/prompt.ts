import type { ToolPrompt } from '@pi-investment/core-tool';

export interface StrategyListParams {
  source?: 'builtin' | 'user';
  code_type?: string;
}

export interface StrategyItem {
  id: string;
  name: string;
  strategyType: string;
  type: string;
  status: string;
  description: string;
  code: string;
  params: any[];
  [key: string]: any;
}

export interface StrategyListResult {
  total: number;
  page: number;
  pageSize: number;
  items: StrategyItem[];
  [key: string]: any;
}

export const strategyListPrompt: ToolPrompt<StrategyListParams, StrategyListResult> = {
  description: '获取交易策略列表：名称、类型、状态、参数配置。策略是具体的交易规则（如均线突破、MACD金叉）。适用于：查看可用策略、执行策略前确认 strategy_id。',

  useCases: ['查看可用策略', '执行策略前确认ID'],

  parameters: {
    source: {
      type: 'string',
      description: '按来源过滤。builtin：系统内置策略；user：用户自定义策略。不传则返回全部',
      enum: ['builtin', 'user'],
      example: 'builtin',
    },
    code_type: {
      type: 'string',
      description: '按策略类型过滤：indicator（技术指标类）、trend_following（趋势跟踪）、mean_reversion（均值回归）、breakout（突破）',
      example: 'trend_following',
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        total: { type: 'number' },
        page: { type: 'number' },
        pageSize: { type: 'number' },
        items: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              id: { type: 'string' },
              name: { type: 'string' },
              strategyType: { type: 'string' },
              type: { type: 'string' },
              status: { type: 'string' },
              description: { type: 'string' },
            },
          },
        },
      },
    },
    render: (args, data) => [{ type: 'text', text: `共找到 ${data.total} 个策略:\n${JSON.stringify(data, null, 2)}` }],
  },
};
