/**
 * RotationProposalTool - 轮动方案建议工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface RotationProposalParams {
  account_name?: string;
  mode?: 'conservative' | 'balanced' | 'aggressive';
  max_positions?: number;
}

export interface RotationProposalResult {
  proposals: Array<{
    action: 'buy' | 'sell' | 'hold';
    symbol: string;
    name: string;
    reason: string;
    priority: number;
    suggested_weight?: number;
  }>;
  summary: {
    total_buy: number;
    total_sell: number;
    expected_turnover: number;
  };
}

export const rotationProposalPrompt: ToolPrompt<RotationProposalParams, RotationProposalResult> = {
  description: '生成持仓轮动建议，基于市场环境和个股表现提出调仓方案',
  useCases: [
    '定期调仓建议',
    '板块轮动切换',
    '弱势股替换',
    '仓位再平衡',
  ],
  parameters: {
    account_name: {
      type: 'string',
      description: '账户名称',
      example: 'default',
    },
    mode: {
      type: 'string',
      description: '轮动模式：conservative/balanced/aggressive',
      example: 'balanced',
    },
    max_positions: {
      type: 'number',
      description: '最大持仓数量',
      example: 10,
    },
  },
  examples: [],

  notes: [],

  relatedTools: [],


  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        proposals: { type: 'array', description: '调仓建议列表' },
        summary: { type: 'object', additionalProperties: true, description: '建议摘要' },
      },
    },
    render: (_args, data) => [
      { type: 'text', text: `🔄 轮动方案生成完成` },
      { type: 'text', text: `` },
      { type: 'text', text: `📊 建议买入: ${data.summary?.total_buy ?? 0} 只` },
      { type: 'text', text: `📊 建议卖出: ${data.summary?.total_sell ?? 0} 只` },
      { type: 'text', text: `📊 预计换手: ${((data.summary?.expected_turnover ?? 0) * 100).toFixed(1)}%` },
      { type: 'text', text: `` },
      ...data.proposals.slice(0, 8).map(p => ({
        type: 'text' as const,
        text: `${p.action === 'buy' ? '🟢' : p.action === 'sell' ? '🔴' : '⚪'} ${p.symbol} ${p.name} - ${p.reason}`
      })),
    ],
  },
};
