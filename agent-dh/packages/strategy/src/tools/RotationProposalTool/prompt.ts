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
    // 2026-09-01：与后端 strategy_rotation_engine 对齐（策略级动作，非个股买卖语义）
    action: 'activate' | 'deactivate' | 'adjust_weight';
    strategy_id?: number;
    strategy_name?: string;
    reason: string;
    priority: number;
    suggested_weight?: number;
  }>;
  summary: {
    total_buy: number;
    total_sell: number;
    expected_turnover: number;
  };
  // 2026-09-01：透传后端市场风格与约束上下文（供决策参考）
  meta?: {
    market_style?: string;
    style_confidence?: number;
    style_duration_days?: number;
    needs_rotation?: boolean;
    trigger?: string;
    expected_impact?: any;
    constraints?: any;
    next_steps?: any;
    active_strategies?: any;
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
      description: '轮动模式',
      enum: ['conservative', 'balanced', 'aggressive'],
      default: 'balanced',
      example: 'balanced',
    },
    max_positions: {
      type: 'number',
      description: '最大持仓数量（1-30），默认 10',
      default: 10,
      minimum: 1,
      maximum: 30,
      example: 10,
    },
  },
  examples: [
    {
      title: '生成保守轮动方案',
      params: { account_name: 'agent_virtual', mode: 'conservative', max_positions: 8 },
      expectedResult: '建议卖出 2 只弱势股，买入 1 只优质股',
    },
    {
      title: '生成激进轮动方案',
      params: { account_name: 'agent_virtual', mode: 'aggressive', max_positions: 15 },
      expectedResult: '建议大幅调仓，卖出 5 只、买入 8 只',
    },
  ],

  notes: [
    '💡 conservative: 小幅调整，换手率 <20%',
    '💡 balanced: 适度调整，换手率 20-40%（默认）',
    '💡 aggressive: 大幅调整，换手率 >40%',
    '⚠️ 方案仅供参考，实际执行前建议用 rotation_simulate 预览',
  ],

  relatedTools: ['rotation_simulate', 'rotation_execute', 'portfolio_trade'],


  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        proposals: { type: 'array', description: '调仓建议列表' },
        summary: { type: 'object', additionalProperties: true, description: '建议摘要' },
      },
    },
    render: (_args, data) => {
      // 2026-09-01：兼容后端实际结构（proposal.actions 策略级动作；summary 可能是字符串）
      const proposals = Array.isArray(data.proposals)
        ? data.proposals
        : (Array.isArray((data as any).proposal?.actions) ? (data as any).proposal.actions : []);
      const summary: any = typeof data.summary === 'object' ? data.summary : {};
      const actIcon = (a: string) => a === 'activate' ? '🟢' : a === 'deactivate' ? '🔴' : '🟡';
      return [
        { type: 'text', text: `🔄 轮动方案生成完成` },
        { type: 'text', text: `` },
        { type: 'text', text: `📊 建议启用: ${summary.total_buy ?? 0} 只` },
        { type: 'text', text: `📊 建议停用: ${summary.total_sell ?? 0} 只` },
        { type: 'text', text: `📊 预计换手: ${((summary.expected_turnover ?? 0) * 100).toFixed(1)}%` },
        { type: 'text', text: `` },
        ...proposals.slice(0, 8).map((p: any) => ({
          type: 'text' as const,
          text: `${actIcon(p.action)} ${p.action} ${p.strategy_name ?? p.symbol ?? ''} - ${p.reason ?? ''}`
        })),
      ];
    },
  },
};
