/**
 * RiskControllerTool - 风险控制工具类型和提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 风险控制参数
 */
export interface RiskControllerParams {
  /** 操作类型 */
  command: 'position_size' | 'stop_loss' | 'portfolio_risk';
  /** 股票代码（position_size/stop_loss 时必填） */
  symbol?: string;
  /** 账户名称 */
  account_name?: string;
  /** 风险分级（stop_loss 时可选） */
  risk_level?: 'large_cap' | 'growth' | 'small_cap_theme';
}

/**
 * 风险控制结果
 */
export interface RiskControllerResult {
  /** 执行的操作 */
  command: string;
  /** 股票代码 */
  symbol?: string;
  /** 计算结果 */
  result: any;
  /** 风险提示 */
  warning?: string;
  [key: string]: any;
}

/**
 * 风险控制工具提示词定义
 */
export const riskControllerPrompt: ToolPrompt<RiskControllerParams, RiskControllerResult> = {
  description: '风险控制计算：建议仓位、止损价、组合风险评估。适用于：买入前用 position_size 计算合理仓位、开仓后用 stop_loss 设置止损、定期用 portfolio_risk 检查组合风险是否超标。只读计算，不改变持仓；执行交易用 portfolio_trade。',

  useCases: [
    '买入前计算合理仓位（position_size）',
    '开仓后设置止损价格（stop_loss）',
    '定期检查组合风险是否超标（portfolio_risk）',
  ],

  examples: [
    {
      title: '计算建议买入仓位',
      params: {
        command: 'position_size',
        symbol: '600519',
        account_name: 'agent_virtual',
      },
      expectedResult: '返回建议买入仓位比例和金额',
    },
    {
      title: '计算止损价格',
      params: {
        command: 'stop_loss',
        symbol: '600519',
        risk_level: 'large_cap',
        account_name: 'agent_virtual',
      },
      expectedResult: '返回建议止损价格',
    },
    {
      title: '评估组合风险',
      params: {
        command: 'portfolio_risk',
        account_name: 'agent_virtual',
      },
      expectedResult: '返回组合整体风险评估',
    },
  ],

  notes: [
    'position_size 和 stop_loss 命令需要传入 symbol 参数',
    'risk_level 分为三档：large_cap（大盘蓝筹-8%）/ growth（成长股-10%）/ small_cap_theme（小盘题材-12%）',
    '只读计算，不改变持仓',
  ],

  relatedTools: ['portfolio_trade', 'risk_metrics', 'regime_position_limit'],

  parameters: {
    command: {
      type: 'string',
      description: '操作类型。position_size：根据账户资金与标的风险计算建议买入仓位（需传 symbol）；stop_loss：计算止损价格（需传 symbol + 可选 risk_level）；portfolio_risk：评估组合整体风险是否超标',
      required: true,
    },
    symbol: {
      type: 'string',
      description: '股票代码，position_size / stop_loss 时必填，如 600519',
    },
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      default: 'agent_virtual',
    },
    risk_level: {
      type: 'string',
      description: '风险分级（stop_loss 时可选）：large_cap（大盘蓝筹-8%）/ growth（成长股-10%）/ small_cap_theme（小盘题材-12%），默认 large_cap',
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        command: { type: 'string', description: '执行的操作' },
        symbol: { type: 'string', description: '股票代码' },
        result: { type: 'object', description: '计算结果', additionalProperties: true },
        warning: { type: 'string', description: '风险提示' },
      },
      additionalProperties: true,
    },
    render: (_args: RiskControllerParams, data: RiskControllerResult) => [{
      type: 'text',
      text: JSON.stringify(data, null, 2),
    }],
  },
};
