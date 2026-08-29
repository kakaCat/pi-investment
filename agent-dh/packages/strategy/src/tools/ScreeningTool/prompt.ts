/**
 * ScreeningTool - 股票筛选工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface ScreeningParams {
  criteria: Record<string, any>;
  sort_by?: string;
  limit?: number;
}

export interface ScreeningResult {
  stocks: Array<{
    symbol: string;
    name: string;
    metrics: Record<string, number>;
    score: number;
  }>;
  total_matched: number;
  criteria_used: Record<string, any>;
}

export const screeningPrompt: ToolPrompt<ScreeningParams, ScreeningResult> = {
  description: '根据多维度条件筛选股票',
  useCases: [
    '筛选低估值高ROE股票',
    '寻找高股息率标的',
    '发现技术面强势股',
    '构建自定义股票池',
  ],
  parameters: {
    criteria: {
      type: 'object', additionalProperties: true,
      required: true,
      description: '筛选条件，如 {pe: [0, 20], roe: [15, null], market_cap: [50, null]}',
      example: { pe: [0, 20], roe: [15, null] },
    },
    sort_by: {
      type: 'string',
      description: '排序字段',
      example: 'roe',
    },
    limit: {
      type: 'number',
      description: '返回数量限制',
      example: 50,
    },
  },
  examples: [],

  notes: [],

  relatedTools: [],


  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        stocks: { type: 'array', description: '筛选结果' },
        total_matched: { type: 'number', description: '符合条件总数' },
        criteria_used: { type: 'object', additionalProperties: true, description: '使用的筛选条件' },
      },
    },
    render: (_args, data) => [
      { type: 'text', text: `🔎 股票筛选完成` },
      { type: 'text', text: `` },
      { type: 'text', text: `📊 符合条件: ${data.total_matched} 只` },
      { type: 'text', text: `📄 返回结果: ${data.stocks.length} 只` },
      { type: 'text', text: `` },
      ...data.stocks.slice(0, 10).map(s => ({
        type: 'text' as const,
        text: `• ${s.symbol} ${s.name} (得分: ${s.score})`
      })),
    ],
  },
};
