/**
 * Competition Analysis Tool Prompt
 *
 * 竞争分析工具 - 分析股票所在行业的竞争格局
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface CompetitionAnalysisParams {
  symbol: string;
  include_financial?: boolean;
}

export interface CompetitionAnalysisResult {
  symbol: string;
  company_name: string;
  industry: {
    level1: string;
    level2: string;
    level3?: string;
  };
  market_size?: {
    total_market_cap: number;
    industry_rank: number;
    market_share: number;
  };
  competitors: Array<{
    symbol: string;
    name: string;
    market_cap: number;
    market_share: number;
    competitive_position: string;
  }>;
  financial_comparison?: {
    metrics: string[];
    data: Array<{
      symbol: string;
      name: string;
      [key: string]: any;
    }>;
  };
  competitive_advantages: string[];
  competitive_disadvantages: string[];
  summary: string;
}

export const competitionAnalysisPrompt: ToolPrompt<CompetitionAnalysisParams, CompetitionAnalysisResult> = {
  description: '分析股票所在行业的竞争格局和对手情况。评估公司竞争地位、对比行业龙头、识别竞争优势/劣势。',

  useCases: [
    '评估公司竞争地位',
    '对比行业龙头',
    '识别竞争优势/劣势',
  ],

  examples: [
    {
      title: '分析贵州茅台的行业竞争格局',
      params: { symbol: '600519', include_financial: true },
      expectedResult: '返回白酒行业竞争格局，包含五粮液等竞争对手的对比分析',
    },
  ],

  notes: [
    '💡 包含行业分类和市场规模',
    '💡 对比主要竞争对手',
  ],

  relatedTools: [],

  parameters: {
    symbol: {
      type: 'string',
      description: '股票代码（6位数字）',
      example: '600519',
    },
    include_financial: {
      type: 'boolean',
      description: '是否包含财务对比',
      default: true,
    },
  },

  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        symbol: { type: 'string' },
        company_name: { type: 'string' },
        industry: {
          type: 'object',
          additionalProperties: false,
          properties: {
            level1: { type: 'string' },
            level2: { type: 'string' },
            level3: { type: 'string' }
          }
        },
        market_size: {
          type: 'object',
          additionalProperties: false,
          properties: {
            total_market_cap: { type: 'number' },
            industry_rank: { type: 'number' },
            market_share: { type: 'number' }
          }
        },
        competitors: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            properties: {
              symbol: { type: 'string' },
              name: { type: 'string' },
              market_cap: { type: 'number' },
              market_share: { type: 'number' },
              competitive_position: { type: 'string' }
            }
          }
        },
        financial_comparison: {
          type: 'object',
          additionalProperties: false,
          properties: {
            metrics: { type: 'array', items: { type: 'string' } },
            data: { type: 'array', items: { type: 'object', additionalProperties: true } }
          }
        },
        competitive_advantages: { type: 'array', items: { type: 'string' } },
        competitive_disadvantages: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' },
      },
    },
    render: (_args: CompetitionAnalysisParams, data: CompetitionAnalysisResult) => [{
      type: 'text',
      text: `## ${data.company_name} (${data.symbol}) 竞争分析\n\n${data.summary}`,
    }],
  },
};
