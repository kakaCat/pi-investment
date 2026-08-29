/**
 * BarraDecompositionTool - Barra风险分解工具类型和提示词定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * Barra风险分解参数
 */
export interface BarraDecompositionParams {
  /** 账户名称 */
  account_name?: string;
}

/**
 * Barra风险分解结果
 */
export interface BarraDecompositionResult {
  /** 总风险（%） */
  total_risk: number;
  /** 各因子风险贡献 */
  factor_risks: any[];
  /** 特质风险（%） */
  idiosyncratic_risk: number;
  /** 行业集中度 */
  industry_concentration: number;
  /** 风格暴露 */
  style_exposure: any;
  [key: string]: any;
}

/**
 * Barra风险分解工具提示词定义
 */
export const barraDecompositionPrompt: ToolPrompt<BarraDecompositionParams, BarraDecompositionResult> = {
  description: '用 Barra 模型将组合风险分解到因子层面（市值、行业、风格），给出各因子风险贡献与特质风险。适用于：组合回撤异常时定位风险来源、检查行业/风格暴露是否过度集中。整体风险指标用 risk_metrics。',

  useCases: [
    '组合回撤异常时定位风险来源',
    '检查行业/风格暴露是否过度集中',
    '分析组合风险结构',
    '识别主要风险因子',
  ],

  examples: [
    {
      title: '查询组合的 Barra 风险分解',
      params: {
        account_name: 'agent_virtual',
      },
      expectedResult: '返回因子风险贡献、特质风险、行业集中度等',
    },
  ],

  notes: [
    '用于定位风险来源，分析到因子层面',
    '整体风险指标使用 risk_metrics',
    '帮助识别行业或风格的过度集中',
  ],

  relatedTools: ['risk_metrics', 'risk_controller'],

  parameters: {
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      default: 'agent_virtual',
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        total_risk: { type: 'number', description: '总风险（%）' },
        factor_risks: { type: 'array', description: '各因子风险贡献' },
        idiosyncratic_risk: { type: 'number', description: '特质风险（%）' },
        industry_concentration: { type: 'number', description: '行业集中度' },
        style_exposure: { type: 'object', description: '风格暴露', additionalProperties: true },
      },
      additionalProperties: true,
    },
    render: (_args: BarraDecompositionParams, data: BarraDecompositionResult) => [{
      type: 'text',
      text: JSON.stringify(data, null, 2),
    }],
  },
};
