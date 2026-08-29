/**
 * ChipAnalysisTool - 筹码分析工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

// 参数类型
export interface ChipAnalysisParams {
  symbol: string; // A股6位数字股票代码
}

// 返回结果类型
export interface ChipAnalysisResult {
  symbol: string; // 股票代码
  avg_cost: number; // 平均成本（元）
  profit_ratio: number; // 获利盘比例（%）
  concentration: number; // 筹码集中度（%）
  support_levels: number[]; // 支撑位列表
  resistance_levels: number[]; // 压力位列表
  chip_distribution: any[]; // 筹码分布数据
  [key: string]: any;
}

/**
 * ToolPrompt 定义
 */
export const chipAnalysisPrompt: ToolPrompt<ChipAnalysisParams, ChipAnalysisResult> = {
  description: '分析个股筹码分布与成本结构：平均成本、获利盘比例、筹码集中度、支撑/压力位。适用于：判断支撑压力位、识别主力成本区、评估突破有效性。解读参考：获利盘比例过高（如>90%）说明浮盈兑现压力大，过低说明套牢盘沉重、反弹阻力大。',

  useCases: [
    '判断支撑压力位',
    '识别主力成本区',
    '评估突破有效性',
    '获利盘比例分析：>90% 兑现压力大，<10% 套牢盘沉重',
  ],

  examples: [],
  notes: [
    '获利盘比例过高（>90%）说明浮盈兑现压力大',
    '获利盘比例过低说明套牢盘沉重、反弹阻力大',
  ],
  relatedTools: [],

  parameters: {
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码，如 600519',
      required: true,
      example: '600519',
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        symbol: { type: 'string', description: '股票代码' },
        avg_cost: { type: 'number', description: '平均成本（元）' },
        profit_ratio: { type: 'number', description: '获利盘比例（%）' },
        concentration: { type: 'number', description: '筹码集中度（%）' },
        support_levels: { type: 'array', description: '支撑位列表' },
        resistance_levels: { type: 'array', description: '压力位列表' },
        chip_distribution: { type: 'array', description: '筹码分布数据' },
      },
      additionalProperties: true,
    },
    render: (_args: ChipAnalysisParams, data: ChipAnalysisResult) => [{
      type: 'text',
      text: JSON.stringify(data, null, 2),
    }],
  },
};
