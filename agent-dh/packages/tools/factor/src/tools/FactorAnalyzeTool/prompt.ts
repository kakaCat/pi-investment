import type { ToolPrompt } from '@pi-investment/core-tool';

export interface FactorAnalyzeParams {
  factor_name: string;
  start_date?: string;
  end_date?: string;
}

export interface FactorAnalyzeResult {
  factor_name: string;
  ic_mean: number;
  ic_std: number;
  ir: number;
  coverage: number;
  monotonicity: number;
  turnover: number;
  conclusion: string;
}

export const factorAnalyzePrompt: ToolPrompt<FactorAnalyzeParams, FactorAnalyzeResult> = {
  description: '分析因子的历史有效性：IC、IR、覆盖率、单调性、换手率，并给出有效性结论',
  useCases: [
    '构建策略前筛选有效因子',
    '定期检查因子是否失效',
    '评估因子预测能力',
    '比较不同因子的有效性',
  ],
  examples: [
    {
      title: '分析 ROE 因子有效性',
      params: {
        factor_name: 'roe',
        start_date: '2023-01-01',
        end_date: '2024-12-31',
      },
      expectedResult: 'IR=0.67>0.5 有效，覆盖率85.5%，单调性良好',
    },
    {
      title: '分析 RSI 因子有效性',
      params: {
        factor_name: 'rsi',
        start_date: '2023-06-01',
        end_date: '2024-06-30',
      },
      expectedResult: 'IR=0.20<0.5 弱有效，预测能力较弱',
    },
  ],
  notes: [
    '💡 IR > 0.5 表示因子有效',
    '💡 覆盖率 > 80% 表示因子数据充足',
    '💡 单调性越高，分层效果越好',
    '⚠️ 分析时间跨度建议至少 1 年',
  ],
  relatedTools: ['factor_calculate', 'screening'],
  parameters: {
    factor_name: {
      type: 'string',
      description: '因子名称（如 rsi、macd、pe、roe）',
      required: true,
      example: 'roe',
    },
    start_date: {
      type: 'string',
      description: '开始日期（YYYY-MM-DD），默认 1 年前',
      example: '2023-01-01',
    },
    end_date: {
      type: 'string',
      description: '结束日期（YYYY-MM-DD），默认今天',
      example: '2024-12-31',
    },
  },
  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        factor_name: { type: 'string', description: '因子名称' },
        ic_mean: { type: 'number', description: 'IC 均值（预测能力）' },
        ic_std: { type: 'number', description: 'IC 标准差（稳定性）' },
        ir: { type: 'number', description: 'IR 信息比率（IC均值/IC标准差）' },
        coverage: { type: 'number', description: '覆盖率（%）' },
        monotonicity: { type: 'number', description: '单调性（分层效果）' },
        turnover: { type: 'number', description: '换手率（%）' },
        conclusion: { type: 'string', description: '有效性结论' },
      },
      additionalProperties: true,
    },
  },
};
