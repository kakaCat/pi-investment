/**
 * Retail Panic Index Tool Prompt
 *
 * 散户恐慌代理指标（M7-2）- 连续 0-100 恐慌指数，识别散户恐慌/贪婪周期
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface RetailPanicIndexParams {
  trade_date?: string;
  days?: number;
}

export interface RetailPanicIndexResult {
  trade_date: string;
  panic_index: number | null;
  level: string;
  degraded: boolean;
  dimensions: {
    retail_flow_score: number | null;
    ad_ratio_score: number | null;
    volume_score: number | null;
    fear_greed_score: number | null;
    volatility_score: number | null;
  };
  raw: {
    retail_flow_yi: number | null;
    ad_ratio: number | null;
    volume_ratio: number | null;
    fear_greed_index: number | null;
    volatility: number | null;
  };
  reason?: string;
}

export const retailPanicIndexPrompt: ToolPrompt<RetailPanicIndexParams, RetailPanicIndexResult> = {
  description: '查询散户恐慌代理指标（连续0-100恐慌指数）。合成散户资金流/涨跌家数/恐慌贪婪指数/量能/波动率五维度。用于识别散户恐慌(≥70)与贪婪(<30)周期、判断收割机会。',

  useCases: [
    '判断散户恐慌程度（恐慌市收割机会）',
    '识别散户贪婪（追高风险区）',
    '观察恐慌-贪婪周期',
  ],

  examples: [
    {
      title: '查询当前散户恐慌指数',
      params: {},
      expectedResult: '返回恐慌指数与等级、五维分数',
    },
    {
      title: '查询最近10日恐慌指数序列',
      params: { days: 10 },
      expectedResult: '返回10日恐慌指数序列',
    },
  ],

  notes: [
    '💡 等级：≥70 恐慌 / 50-70 偏恐慌 / 30-50 偏贪婪 / <30 贪婪',
    '💡 恐慌指数高=散户在卖=关注优质标的收割机会',
  ],

  relatedTools: [],

  parameters: {
    trade_date: {
      type: 'string',
      description: '查询日期（YYYY-MM-DD），不传取最近一日',
      example: '2026-08-28',
    },
    days: {
      type: 'number',
      description: '传入则查询最近 N 日序列（1-60）',
      example: 10,
    },
  },

  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        trade_date: { type: 'string' },
        panic_index: { type: 'number' },
        level: { type: 'string' },
        degraded: { type: 'boolean' },
        dimensions: {
          type: 'object',
          additionalProperties: false,
          properties: {
            retail_flow_score: { type: 'number' },
            ad_ratio_score: { type: 'number' },
            volume_score: { type: 'number' },
            fear_greed_score: { type: 'number' },
            volatility_score: { type: 'number' },
          },
        },
        raw: {
          type: 'object',
          additionalProperties: false,
          properties: {
            retail_flow_yi: { type: 'number' },
            ad_ratio: { type: 'number' },
            volume_ratio: { type: 'number' },
            fear_greed_index: { type: 'number' },
            volatility: { type: 'number' },
          },
        },
        reason: { type: 'string' },
      },
    },
    render: (_args: RetailPanicIndexParams, data: RetailPanicIndexResult) => {
      if (data.degraded) {
        return [{
          type: 'text',
          text: `## 散户恐慌指数（${data.trade_date}）\n\n**数据不可用**: ${data.reason ?? '无数据'}`,
        }];
      }
      const levelMap: Record<string, string> = {
        panic: '🔴 恐慌（散户在割肉，关注优质标的）',
        leaning_panic: '🟠 偏恐慌',
        leaning_greed: '🟡 偏贪婪',
        greed: '🟢 贪婪（散户在追高，注意风险）',
      };
      return [{
        type: 'text',
        text: [
          `## 散户恐慌指数（${data.trade_date}）`,
          '',
          `**恐慌指数**: ${data.panic_index} / 100 — ${levelMap[data.level] ?? data.level}`,
          '',
          '**维度分解**（0=贪婪 / 100=恐慌）:',
          `- 散户资金流: ${data.dimensions?.retail_flow_score ?? 'N/A'}（净流入 ${data.raw?.retail_flow_yi ?? 'N/A'} 亿）`,
          `- 涨跌家数比: ${data.dimensions?.ad_ratio_score ?? 'N/A'}（ad_ratio=${data.raw?.ad_ratio ?? 'N/A'}）`,
          `- 恐慌贪婪指数: ${data.dimensions?.fear_greed_score ?? 'N/A'}（fg=${data.raw?.fear_greed_index ?? 'N/A'}）`,
          `- 量能: ${data.dimensions?.volume_score ?? 'N/A'}（vol_ratio=${data.raw?.volume_ratio ?? 'N/A'}）`,
          `- 波动率: ${data.dimensions?.volatility_score ?? 'N/A'}（${data.raw?.volatility ?? 'N/A'}%）`,
        ].join('\n'),
      }];
    },
  },
};
