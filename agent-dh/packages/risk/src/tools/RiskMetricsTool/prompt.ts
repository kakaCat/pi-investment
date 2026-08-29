/**
 * RiskMetricsTool - 风险指标工具类型和提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 风险指标参数
 */
export interface RiskMetricsParams {
  /** 账户名称 */
  account_name?: string;
  /** 计算窗口（天） */
  days?: number;
}

/**
 * 风险指标结果
 */
export interface RiskMetricsResult {
  /** 年化波动率（%） */
  volatility: number;
  /** 最大回撤（%） */
  max_drawdown: number;
  /** 夏普比率 */
  sharpe_ratio: number;
  /** Beta系数（相对大盘） */
  beta: number;
  /** Alpha超额收益（%） */
  alpha: number;
  /** VaR 95%（最大日亏损） */
  var_95: number;
  /** 索提诺比率 */
  sortino_ratio: number;
  [key: string]: any;
}

/**
 * 风险指标工具提示词定义
 */
export const riskMetricsPrompt: ToolPrompt<RiskMetricsParams, RiskMetricsResult> = {
  description: '计算投资组合的风险收益指标：年化波动率、最大回撤、夏普/索提诺比率、Beta、Alpha、VaR(95%)。适用于：定期（如每周）评估组合风险收益特征、判断是否需要降仓。需要因子层面的风险来源分解时用 risk_barra_decomposition。',

  useCases: [
    '定期（如每周）评估组合风险收益特征',
    '判断是否需要降仓',
    '分析组合历史表现',
    '监控风险指标变化趋势',
  ],

  examples: [
    {
      title: '查询默认账户的风险指标',
      params: {
        account_name: 'agent_virtual',
        days: 60,
      },
      expectedResult: '返回包含波动率、回撤、夏普比率等风险指标',
    },
  ],

  notes: [
    '计算窗口越短对近期变化越敏感，越长越稳定',
    '默认计算窗口为 60 天',
    '需要因子层面的风险来源分解时使用 risk_barra_decomposition',
  ],

  relatedTools: ['risk_barra_decomposition', 'risk_controller', 'regime_position_limit'],

  parameters: {
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      default: 'agent_virtual',
    },
    days: {
      type: 'integer',
      description: '计算窗口（天），默认 60。窗口越短对近期变化越敏感，越长越稳定',
      default: 60,
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        volatility: { type: 'number', description: '年化波动率（%）' },
        max_drawdown: { type: 'number', description: '最大回撤（%）' },
        sharpe_ratio: { type: 'number', description: '夏普比率' },
        beta: { type: 'number', description: 'Beta系数（相对大盘）' },
        alpha: { type: 'number', description: 'Alpha超额收益（%）' },
        var_95: { type: 'number', description: 'VaR 95%（最大日亏损）' },
        sortino_ratio: { type: 'number', description: '索提诺比率' },
      },
      additionalProperties: true,
    },
    render: (_args: RiskMetricsParams, data: RiskMetricsResult) => [{
      type: 'text',
      text: JSON.stringify(data, null, 2),
    }],
  },
};
