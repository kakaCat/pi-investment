/**
 * SectorAnalysisTool - 行业分析工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

// 参数类型
export interface SectorAnalysisParams {
  sector?: string; // 行业名称或代码，如 白酒、半导体、银行
  days?: number; // 分析周期（交易日），默认 5
}

// 返回结果类型
export interface SectorAnalysisResult {
  sectors: any[]; // 行业列表，按涨幅排序
  top_performers: any[]; // 表现最好的行业
  worst_performers: any[]; // 表现最差的行业
  rotation_signal: string; // 轮动信号
  [key: string]: any;
}

/**
 * ToolPrompt 定义
 */
export const sectorAnalysisPrompt: ToolPrompt<SectorAnalysisParams, SectorAnalysisResult> = {
  description: '分析行业板块表现、资金流向与轮动信号。适用于：发现强势板块、判断行业轮动节奏、选择配置方向。与 market_style_detect 的分工：后者看市场整体风格，本工具看行业细节。确认轮动方向后可用 rotation_proposal 生成调仓提案。',

  useCases: [
    '发现强势板块和弱势板块',
    '判断行业轮动节奏',
    '选择配置方向',
    '与 market_style_detect 配合：后者看整体，本工具看细节',
  ],

  examples: [],
  notes: [
    '短线轮动看 5-10 天',
    '中线趋势看 20-60 天',
  ],
  relatedTools: ['market_style_detect', 'rotation_proposal'],

  parameters: {
    sector: {
      type: 'string',
      description: '行业名称或代码，如 白酒、半导体、银行。传入则返回该行业详情；不传则返回全部行业排名',
    },
    days: {
      type: 'integer',
      description: '分析周期（交易日），默认 5。短线轮动看 5-10 天，中线趋势看 20-60 天',
      default: 5,
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        sectors: { type: 'array', description: '行业列表，按涨幅排序' },
        top_performers: { type: 'array', description: '表现最好的行业' },
        worst_performers: { type: 'array', description: '表现最差的行业' },
        rotation_signal: { type: 'string', description: '轮动信号' },
      },
      additionalProperties: true,
    },
    render: (_args: SectorAnalysisParams, data: SectorAnalysisResult) => [{
      type: 'text',
      text: JSON.stringify(data, null, 2),
    }],
  },
};
