/**
 * PePercentileTool - PE 历史分位工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface PePercentileParams {
  symbol: string;
}

export const pePercentilePrompt: ToolPrompt<PePercentileParams> = {
  description: '查询个股 PE(TTM) 历史分位：当前 PE 处于自身历史（近3年）的百分位、历史区间（min/max/均值/中位数）与高估/低估判定。适用于：估值贵贱判断（分位<40%=好价格候选，>80%=只做波段不做长持）、买卖点前估值校验。',

  useCases: [
    '估值贵贱判断：PE 分位 <40% 低估候选，>80% 历史偏高位',
    '策略性质判定：分位高的标的"只做波段、不做长持"',
    '买卖点分析前的估值校验维度',
  ],

  examples: [
    'pe_percentile({ symbol: "601857" }) // 中石油 PE 分位',
    'pe_percentile({ symbol: "600519" }) // 茅台 PE 分位',
  ],

  notes: [
    '分位基于近 3 年（约 715 个交易日）自身 PE 历史，是相对估值不是绝对估值',
    '亏损股（PE 为负/无意义）结果可能不可用，结合 data_fetch_financial 判断',
    '好价格标准参考：PE 分位 <40% + ≥2 个买入信号共振',
  ],

  relatedTools: ['data_fetch_financial', 'swing_points'],

  parameters: {
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码，如 601857',
      required: true,
      example: '601857',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        symbol: { type: 'string', description: '股票代码' },
        current_pe: { type: 'number', description: '当前 PE(TTM)' },
        percentile: { type: 'number', description: '历史分位（%）' },
        interpretation: { type: 'string', description: '高估/低估判定' },
      },
      additionalProperties: true,
    },
    render: (_args: PePercentileParams, data: any) => [{
      type: 'text',
      text: JSON.stringify(data, null, 2),
    }],
  },
};
