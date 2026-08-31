/**
 * Opponent Behavior Tool Prompt
 *
 * 对手行为分析 - 分析市场参与者（散户/机构/游资）行为，识别博弈机会（M7-1）
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface OpponentBehaviorParams {
  focus?: 'retail' | 'institution' | 'hot_money';
}

export interface OpponentBehaviorResult {
  retail: {
    behavior: string;
    net_flow: number | null;
    emotion_index: number | null;
    common_mistakes: string[];
    degraded: boolean;
    description: string;
  };
  institution: {
    behavior: string;
    net_flow: number | null;
    target_sectors: string[];
    position_change: string;
    degraded: boolean;
    description: string;
  };
  hot_money: {
    behavior: string;
    target_stocks: string[];
    stage: string | null;
    activity_level: string;
    estimated: boolean;
    description: string;
  };
  market_phase: string;
  risk_appetite: string;
  opportunity_map: Record<string, any>;
  degraded: boolean;
  timestamp: string;
}

export const opponentBehaviorPrompt: ToolPrompt<OpponentBehaviorParams, OpponentBehaviorResult> = {
  description: '分析市场对手行为（散户/机构/游资三方博弈），识别谁在犯错、机会在哪。用于判断博弈格局、挖掘对手错误下注机会。',

  useCases: [
    '判断当前市场博弈格局',
    '识别对手盘错误',
    '入场前评估对手盘',
  ],

  examples: [
    {
      title: '分析当前市场对手行为',
      params: {},
      expectedResult: '返回散户/机构/游资行为与市场阶段、博弈机会',
    },
  ],

  notes: [
    '💡 数据来自资金流聚合（小单=散户、主力=机构）',
    '💡 游资为估算值（龙虎榜未接入时）',
  ],

  relatedTools: [],

  parameters: {
    focus: {
      type: 'string',
      description: '聚焦维度：retail=散户 / institution=机构 / hot_money=游资，不传则全量分析',
      example: 'institution',
    },
  },

  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        retail: {
          type: 'object',
          additionalProperties: false,
          properties: {
            behavior: { type: 'string' },
            net_flow: { type: 'number' },
            emotion_index: { type: 'number' },
            common_mistakes: { type: 'array', items: { type: 'string' } },
            degraded: { type: 'boolean' },
            description: { type: 'string' },
          },
        },
        institution: {
          type: 'object',
          additionalProperties: false,
          properties: {
            behavior: { type: 'string' },
            net_flow: { type: 'number' },
            target_sectors: { type: 'array', items: { type: 'string' } },
            position_change: { type: 'string' },
            degraded: { type: 'boolean' },
            description: { type: 'string' },
          },
        },
        hot_money: {
          type: 'object',
          additionalProperties: false,
          properties: {
            behavior: { type: 'string' },
            target_stocks: { type: 'array', items: { type: 'string' } },
            stage: { type: 'string' },
            activity_level: { type: 'string' },
            estimated: { type: 'boolean' },
            description: { type: 'string' },
          },
        },
        market_phase: { type: 'string' },
        risk_appetite: { type: 'string' },
        opportunity_map: { type: 'object', additionalProperties: true },
        degraded: { type: 'boolean' },
        timestamp: { type: 'string' },
      },
    },
    render: (_args: OpponentBehaviorParams, data: OpponentBehaviorResult) => [{
      type: 'text',
      text: [
        `## 对手行为分析（${data.timestamp?.slice(0, 10) ?? ''}）`,
        '',
        `**市场阶段**: ${data.market_phase} | **风险偏好**: ${data.risk_appetite} | **数据降级**: ${data.degraded}`,
        '',
        `**散户**: ${data.retail?.behavior}（净流入 ${data.retail?.net_flow != null ? (data.retail.net_flow / 1e8).toFixed(1) + ' 亿' : 'N/A'}，情绪 ${data.retail?.emotion_index ?? 'N/A'}）`,
        data.retail?.description ? `  - ${data.retail.description}` : '',
        `**机构**: ${data.institution?.behavior}（净流入 ${data.institution?.net_flow != null ? (data.institution.net_flow / 1e8).toFixed(1) + ' 亿' : 'N/A'}）`,
        data.institution?.target_sectors?.length ? `  - 目标板块: ${data.institution.target_sectors.join(' / ')}` : '',
        data.institution?.description ? `  - ${data.institution.description}` : '',
        `**游资**: ${data.hot_money?.behavior}（活跃度 ${data.hot_money?.activity_level ?? 'N/A'}${data.hot_money?.estimated ? '，估算' : ''}）`,
        data.hot_money?.description ? `  - ${data.hot_money.description}` : '',
        '',
        `**博弈机会**: ${Object.keys(data.opportunity_map ?? {}).length} 个`,
      ].filter(Boolean).join('\n'),
    }],
  },
};
