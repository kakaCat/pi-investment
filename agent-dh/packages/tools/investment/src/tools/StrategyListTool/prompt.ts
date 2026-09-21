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
  /** 仅由 structure_status 派生（valid→stopped / invalid→error），**不代表业绩** */
  status: string;
  /** 结构状态：代码/参数能否跑通（valid/invalid/pending/unknown） */
  structure_status?: string;
  /** 业绩状态：相对同池等权基准是否有超额（passing/underperform/failing/unmeasured） */
  performance_status?: string;
  /** 业绩判定证据（年化/夏普/回撤/基准/来源/窗口/规则） */
  performance_evidence?: any;
  description: string | null;
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
  description: '获取交易策略列表：名称、类型、状态、参数配置。策略是具体的交易规则（如均线突破、MACD金叉）。适用于：查看可用策略、执行策略前确认 strategy_id。⚠️ 两条独立的状态轴，别混读：【structure_status】代码/参数能否跑通（valid/invalid/pending/unknown）；【performance_status】相对同池等权基准有没有超额（passing/underperform/failing/unmeasured，unmeasured=无证据）。字段 status 只由结构轴派生（valid→stopped / invalid→error），**它不代表业绩**——实测 14 条 active+valid 策略 OOS 年化中位约 -1%，同期同池等权基准 +23.3%，没有一条跑赢。判断"能不能用"只看 performance_status。',

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
      type: 'object', additionalProperties: true,
      properties: {
        total: { type: 'number' },
        page: { type: 'number' },
        pageSize: { type: 'number' },
        items: {
          type: 'array',
          items: {
            type: 'object', additionalProperties: true,
            properties: {
              id: { type: 'string' },
              name: { type: 'string' },
              strategyType: { type: 'string' },
              type: { type: 'string' },
              status: { type: 'string' },
              structure_status: { type: 'string' },
              performance_status: { type: 'string' },
              description: { type: 'string' },
            },
          },
        },
      },
    },
    render: (args, data) => [{ type: 'text', text: `共找到 ${data.total} 个策略:\n${JSON.stringify(data, null, 2)}` }],
  },
};
