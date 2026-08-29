/**
 * RegimeDailyTool - 市场 Regime 每日落库工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

// 参数类型
export interface RegimeDailyParams {
  // 无参数
}

// 返回结果类型
export interface RegimeDailyResult {
  date: string; // 日期
  regime: string; // panic / euphoria / risk_on / risk_off / sideways
  evidence: Record<string, any>; // 证据数据
  skipped?: boolean; // true=今日已落库，未重复写入
  [key: string]: any;
}

/**
 * ToolPrompt 定义
 */
export const regimeDailyPrompt: ToolPrompt<RegimeDailyParams, RegimeDailyResult> = {
  description: '计算并落库当日市场 regime（趋势/震荡/恐慌/狂热）与情绪时间序列。判定依据：恐慌贪婪指数 + 涨跌家数比 + 量能比（指数K线趋势维度待 M0 数据地基补齐后接入）。每日盘后例程调用一次，幂等（同日重复调用跳过）。供：M4 仓位映射、验证门裁决的 regime 对齐、复盘统计 regime 判定准确率。',

  useCases: [
    '每日盘后例程调用一次',
    '幂等：同日重复调用跳过',
    '供 M4 仓位映射使用',
    '供验证门裁决的 regime 对齐',
    '复盘统计 regime 判定准确率',
  ],

  examples: [],
  notes: [
    'Regime 类型：panic（恐慌）/ euphoria（狂热）/ risk_on（偏多）/ risk_off（偏空）/ sideways（震荡）',
    '判定依据：恐慌贪婪指数 + 涨跌家数比 + 量能比',
    '指数K线趋势维度待 M0 数据地基补齐后接入',
  ],
  relatedTools: [],

  parameters: {},

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        date: { type: 'string', description: '日期（YYYY-MM-DD）' },
        regime: { type: 'string', description: 'panic / euphoria / risk_on / risk_off / sideways' },
        evidence: { type: 'object', additionalProperties: true, description: '证据数据' },
        skipped: { type: 'boolean', description: 'true=今日已落库，未重复写入' },
      },
      additionalProperties: true,
    },
    render: (_args: RegimeDailyParams, data: RegimeDailyResult) => [{
      type: 'text',
      text: JSON.stringify(data, null, 2),
    }],
  },
};
