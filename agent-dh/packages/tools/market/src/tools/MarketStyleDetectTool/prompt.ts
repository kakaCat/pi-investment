/**
 * MarketStyleDetectTool - 市场风格检测工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

// 参数类型
export interface MarketStyleDetectParams {
  // 无参数
}

// 返回结果类型
export interface MarketStyleDetectResult {
  style: string; // 主导风格：value（价值）/growth（成长）/cycle（周期）
  confidence: number; // 置信度（0-1）
  scores: Record<string, number>; // 各风格得分，如 {value, growth, cycle}
  indicators: Record<string, any>; // 观测指标
  recommendedFactors: string[]; // 推荐因子
  detectionDate: string; // 检测日期（YYYY-MM-DD）
}

/**
 * ToolPrompt 定义
 */
export const marketStyleDetectPrompt: ToolPrompt<MarketStyleDetectParams, MarketStyleDetectResult> = {
  description: '检测当前市场主导风格（价值/成长/周期）及置信度，返回各风格得分、观测指标和推荐因子。适用于：定期（如每周）判断市场偏好、指导配置方向——风格偏价值时增配低估值蓝筹，偏成长时关注科技成长。行业层面的细节分析用 sector_analysis。',

  useCases: [
    '定期（如每周）判断市场主导风格',
    '指导配置方向：价值时增配低估值蓝筹，成长时关注科技成长',
    '与 sector_analysis 配合：本工具看整体风格，sector_analysis 看行业细节',
  ],

  examples: [
    'market_style_detect() // 检测当前市场主导风格',
  ],
  notes: [
    '风格类型：value（价值）/growth（成长）/cycle（周期）',
    '置信度 >0.7 表示风格较为明确，<0.5 表示风格混杂',
    '推荐因子根据风格动态调整，如价值风格推荐 PE、PB，成长风格推荐 ROE、营收增速',
  ],
  relatedTools: ['sector_analysis'],

  parameters: {},

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        style: { type: 'string', description: '主导风格：value（价值）/growth（成长）/cycle（周期）' },
        confidence: { type: 'number', description: '置信度（0-1）' },
        scores: { type: 'object', additionalProperties: true, description: '各风格得分，如 {value, growth, cycle}' },
        indicators: { type: 'object', additionalProperties: true, description: '观测指标（银行/科技/周期板块表现、成交量变化、波动率等）' },
        recommendedFactors: { type: 'array', description: '当前风格下的推荐因子，如 roe/momentum' },
        detectionDate: { type: 'string', description: '检测日期（YYYY-MM-DD）' },
      },
      additionalProperties: true,
    },
    render: (_args: MarketStyleDetectParams, data: MarketStyleDetectResult) => [{
      type: 'text',
      text: JSON.stringify(data, null, 2),
    }],
  },
};
