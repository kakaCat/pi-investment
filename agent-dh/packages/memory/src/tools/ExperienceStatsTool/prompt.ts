/**
 * ExperienceStatsTool - 经验库胜率统计
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface ExperienceStatsParams {
  symbol?: string;
  days?: number;
  limit?: number;
}

export const experienceStatsPrompt: ToolPrompt<ExperienceStatsParams> = {
  name: 'experience_stats',
  description: '经验库结构化统计（只读）：聚合 experience 命名空间的历史经验，输出总样本/胜率/平均盈亏/按标的分布/按结果分布。适用于：决策前看"这类场景历史胜率多少"、定期复盘经验质量、识别哪些场景是稳定亏损源。与 memory_search 的分工：search 找具体案例，stats 看整体胜率。',

  parameters: {
    symbol: {
      type: 'string',
      description: '按标的过滤（可选），如 601857',
    },
    days: {
      type: 'integer',
      description: '只看最近 N 天写入的经验（可选，默认全部）',
    },
    limit: {
      type: 'integer',
      description: '拉取经验条数上限（默认 200）',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        total: { type: 'integer', description: '样本总数' },
        win_rate: { type: 'number', description: '胜率（%）' },
        avg_pnl_pct: { type: 'number', description: '平均盈亏（%）' },
      },
      additionalProperties: true,
    },
    render: (_args: ExperienceStatsParams, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },

  examples: [
    { scenario: '看全部经验的整体胜率', params: {}, expectedBehavior: '返回 total/win_rate/avg_pnl_pct/by_outcome/by_symbol' },
    { scenario: '看某标的的经验统计', params: { symbol: '601857' }, expectedBehavior: '只统计该标的的经验' },
  ],

  useCases: [
    { title: '决策前置信参考', description: '同类场景历史胜率低 → 降仓或放弃', example: 'experience_stats({})' },
    { title: '经验质量复盘', description: 'loss 占比高的场景是稳定亏损源，应沉淀新教训', example: '每周盘后跑' },
  ],

  notes: [
    '2026-09-01 上线（对标 agent-ts query_experience 的胜率统计维度；衰减/自动弃用机制待后端支持后补齐）',
    '统计口径：experience_write 写入的结构化经验（结果：profit/loss/neutral，盈亏：X%）',
    '样本 < 10 时胜率参考价值低，输出会标注 low_confidence',
  ],

  relatedTools: [
    { name: 'experience_write', relationship: '写入经验', useCase: '交易复盘后写入，stats 才能统计' },
    { name: 'memory_search', relationship: '案例检索', useCase: 'stats 发现高亏损场景后 search 找具体案例' },
  ],
};
