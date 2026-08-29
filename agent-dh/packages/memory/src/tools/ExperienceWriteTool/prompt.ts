import type { ToolPrompt } from '@pi-investment/core-tool';

export interface ExperienceWriteParams {
  symbol: string;
  scenario: string;
  outcome?: 'profit' | 'loss' | 'neutral';
  lesson?: string;
  pnl_pct?: number;
}

export interface ExperienceWriteResult {
  success: boolean;
  experience_id: string;
}

export const experienceWritePrompt: ToolPrompt<ExperienceWriteParams, ExperienceWriteResult> = {
  description: '记录一笔交易的经验教训（写入 experience 命名空间；亏损记录自动标记更高重要性）',
  useCases: [
    '平仓后沉淀得失原因',
    '阶段复盘形成可复用经验库',
    '记录亏损教训以避免重复错误',
    '记录成功经验供后续参考',
  ],
  examples: [
    {
      title: '记录亏损经验',
      params: {
        symbol: '600519',
        scenario: '突破买入后遭遇大盘回调',
        outcome: 'loss',
        lesson: '突破买入需确认大盘趋势，单边下跌市慎用',
        pnl_pct: -8.2,
      },
      expectedResult: '经验已记录，ID: 123',
    },
    {
      title: '记录盈利经验',
      params: {
        symbol: '000858',
        scenario: '超跌反弹买入，快速止盈',
        outcome: 'profit',
        lesson: '超跌股反弹快速，需及时止盈，不贪心',
        pnl_pct: 12.5,
      },
      expectedResult: '经验已记录，ID: 456',
    },
  ],
  notes: [
    '💡 一般性的分析结论用 memory_write',
    '💡 亏损经验自动提高重要性权重',
    '💡 可通过 memory_search(namespace=experience) 检索',
  ],
  relatedTools: ['memory_search', 'memory_write'],
  parameters: {
    symbol: {
      type: 'string',
      description: '股票代码，如 600519',
      required: true,
      example: '600519',
    },
    scenario: {
      type: 'string',
      description: '当时的市场场景与操作，如 "突破买入后遭遇大盘回调"',
      required: true,
      example: '突破买入后遭遇大盘回调',
    },
    outcome: {
      type: 'string',
      description: '结果。profit：盈利；loss：亏损（自动提高重要性权重）；neutral：持平',
      enum: ['profit', 'loss', 'neutral'],
      example: 'loss',
    },
    lesson: {
      type: 'string',
      description: '提炼的经验教训，如 "突破买入需确认大盘趋势，单边下跌市慎用"',
      example: '突破买入需确认大盘趋势',
    },
    pnl_pct: {
      type: 'number',
      description: '盈亏比例（%），如 15.5 或 -8.2',
      example: -8.2,
    },
  },
  output: {
    schema: {
      type: 'object',
      properties: {
        success: { type: 'boolean', description: '是否成功' },
        experience_id: { type: 'string', description: '经验ID' },
      },
      additionalProperties: true,
    },
  },
};
