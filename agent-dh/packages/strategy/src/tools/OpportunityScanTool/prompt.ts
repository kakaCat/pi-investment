/**
 * OpportunityScanTool - 机会扫描工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface OpportunityScanParams {
  scan_type?: 'technical' | 'fundamental' | 'hybrid';
  pool_id?: number;
  symbols?: string[];
  min_score?: number;
}

export interface OpportunityScanResult {
  opportunities: Array<{
    symbol: string;
    name: string;
    score: number;
    reasons: string[];
    signals: Record<string, any>;
  }>;
  scan_summary: {
    total_scanned: number;
    opportunities_found: number;
    scan_time: string;
  };
}

export const opportunityScanPrompt: ToolPrompt<OpportunityScanParams, OpportunityScanResult> = {
  description: '扫描市场机会，识别潜在买入或卖出信号',
  useCases: [
    '盘前扫描今日机会',
    '发现超跌反弹标的',
    '识别突破形态',
    '寻找基本面改善股票',
  ],
  parameters: {
    scan_type: {
      type: 'string',
      description: '扫描类型：technical/fundamental/hybrid',
      example: 'hybrid',
    },
    pool_id: {
      type: 'number',
      description: '扫描指定股票池',
      example: 1,
    },
    symbols: {
      type: 'array',
      description: '扫描指定股票列表',
      example: ['000001', '600519'],
    },
    min_score: {
      type: 'number',
      description: '最低得分阈值',
      example: 70,
    },
  },
  examples: [],

  notes: [],

  relatedTools: [],


  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        opportunities: { type: 'array', description: '机会列表' },
        scan_summary: { type: 'object', additionalProperties: true, description: '扫描摘要' },
      },
    },
    render: (_args, data) => [
      { type: 'text', text: `🔍 机会扫描完成` },
      { type: 'text', text: `` },
      { type: 'text', text: `📊 扫描范围: ${data.scan_summary.total_scanned} 只股票` },
      { type: 'text', text: `✨ 发现机会: ${data.scan_summary.opportunities_found} 个` },
      { type: 'text', text: `` },
      ...data.opportunities.slice(0, 5).map(opp => ({
        type: 'text' as const,
        text: `• ${opp.symbol} ${opp.name} (得分: ${opp.score}) - ${opp.reasons.join(', ')}`
      })),
    ],
  },
};
