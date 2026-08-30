/**
 * RegimePositionLimitTool - 市场状态仓位限制工具类型和提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 市场状态仓位限制参数
 */
export interface RegimePositionLimitParams {
  /** 账户名称 */
  account_name?: string;
}

/**
 * 市场状态仓位限制结果
 */
export interface RegimePositionLimitResult {
  /** 市场状态 */
  regime: string;
  /** regime 日期 */
  regime_date: string;
  /** 数据质量 */
  data_quality: string;
  /** regime 映射的权益仓位上限（%） */
  max_position_pct: number;
  /** 当前实际仓位（%） */
  current_position_pct: number;
  /** 剩余可加仓空间（%），负数=超限 */
  headroom_pct: number;
  /** 合规判定 */
  verdict: 'compliant' | 'reduce_required' | 'circuit_breaker';
  /** 熔断信息 */
  circuit_breaker: any;
  [key: string]: any;
}

/**
 * 市场状态仓位限制工具提示词定义
 */
export const regimePositionLimitPrompt: ToolPrompt<RegimePositionLimitParams, RegimePositionLimitResult> = {
  description: 'M4 仓位映射：读取最新落库的 regime（market:regime），返回权益仓位上限（恐慌≤100%/偏多≤80%/震荡≤60%/偏空≤40%/狂热≤30%）、当前实际仓位、余量与合规判定（可加仓/须减仓及额度）；同时检查组合回撤熔断（60日最大回撤超8%触发，要求减仓一半）。数据降级（degraded/指标矛盾）时上限自动收紧到震荡档（保守原则）。买入前必须调用（R-001 配套）。',

  useCases: [
    '买入前检查仓位限制（R-001 配套）',
    '判断是否可以加仓',
    '检查组合回撤熔断',
    '获取当前仓位余量',
  ],

  examples: [
    {
      title: '检查当前仓位限制',
      params: {
        account_name: 'agent_virtual',
      },
      expectedResult: '返回 regime 映射的仓位上限、当前仓位、可加仓空间和合规判定',
    },
  ],

  notes: [
    'regime 映射规则：恐慌≤100% / 偏多≤80% / 震荡≤60% / 偏空≤40% / 狂热≤30%',
    '数据降级时自动收紧到震荡档（60%）',
    '回撤熔断：60日最大回撤超8%触发，要求减仓一半',
    '买入前必须调用（R-001 配套）',
  ],

  relatedTools: ['regime_daily', 'portfolio_trade', 'risk_metrics'],

  parameters: {
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      default: 'agent_virtual',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        regime: { type: 'string', description: '市场状态' },
        regime_date: { type: 'string', description: 'regime 日期' },
        data_quality: { type: 'string', description: '数据质量' },
        max_position_pct: { type: 'number', description: 'regime 映射的权益仓位上限（%）' },
        current_position_pct: { type: 'number', description: '当前实际仓位（%）' },
        headroom_pct: { type: 'number', description: '剩余可加仓空间（%），负数=超限' },
        verdict: { type: 'string', description: 'compliant / reduce_required / circuit_breaker' },
        circuit_breaker: { type: 'object', additionalProperties: true, description: '熔断信息' },
      },
    },
    render: (_args: RegimePositionLimitParams, data: RegimePositionLimitResult) => [{
      type: 'text',
      text: JSON.stringify(data, null, 2),
    }],
  },
};
