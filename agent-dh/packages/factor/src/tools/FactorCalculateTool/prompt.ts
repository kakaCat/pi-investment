import type { ToolPrompt } from '@pi-investment/core-tool';

export interface FactorCalculateParams {
  symbol: string;
  factors?: string[];
}

export interface FactorCalculateResult {
  symbol: string;
  date: string;
  factors: Record<string, any>;
  factor_dates?: Record<string, string>;
  freshness_warnings?: string[];
  degraded?: boolean;
}

export const factorCalculatePrompt: ToolPrompt<FactorCalculateParams, FactorCalculateResult> = {
  description: '计算个股的技术因子和财务因子当前值',
  useCases: [
    '量化选股前获取因子数据',
    '验证个股当前因子状态',
    '为 model_train 挑选特征',
    '评估个股的量化指标',
  ],
  examples: [
    {
      title: '计算指定因子',
      params: {
        symbol: '600519',
        factors: ['rsi', 'macd', 'roe'],
      },
      expectedResult: 'rsi: 65.5, macd: 0.82, roe: 28.5%',
    },
    {
      title: '计算所有因子',
      params: {
        symbol: '000858',
      },
      expectedResult: '7个因子: rsi, macd, pe, pb, roe, turnover, volatility',
    },
  ],
  notes: [
    '💡 factors 不传则计算全部因子（更全但更慢）',
    '💡 财务因子（roe, pe, pb）基于最新财报',
    '⚠️ 数据陈旧时会在 freshness_warnings 中提示',
  ],
  relatedTools: ['factor_analyze', 'screening'],
  parameters: {
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码，如 600519',
      required: true,
      example: '600519',
    },
    factors: {
      type: 'array',
      description: '指定因子列表，如 ["rsi", "macd", "roe"]。可选：rsi、macd、pe、pb、roe、turnover、volatility。不传则计算全部',
      items: { type: 'string' },
      example: ['rsi', 'macd', 'roe'],
    },
  },
  output: {
    schema: {
      type: 'object',
      properties: {
        symbol: { type: 'string', description: '股票代码' },
        date: { type: 'string', description: '计算日期' },
        factors: { type: 'object', description: '因子值', additionalProperties: true },
        factor_dates: { type: 'object', description: '各因子数据日期', additionalProperties: true },
        freshness_warnings: { type: 'array', items: { type: 'string' }, description: '数据陈旧警告' },
        degraded: { type: 'boolean', description: '是否降级模式' },
      },
      additionalProperties: true,
    },
  },
};
