import type { ToolPrompt } from '@pi-investment/core-tool';

export interface DataFetchMacroParams {
  indicator: 'pmi' | 'cpi' | 'gdp';
}

export interface DataFetchMacroResult {
  indicator: string;
  data: Array<Record<string, any>>;
  latest: Record<string, any>;
  trend: string;
  update_time: string;
  [key: string]: any;
}

export const dataFetchMacroPrompt: ToolPrompt<DataFetchMacroParams, DataFetchMacroResult> = {
  description: '获取宏观经济指标（GDP/CPI/PMI）的时间序列及趋势判断。适用于：判断经济周期位置、评估市场大环境、指导大类资产配置方向。宏观指标按月/季发布，适合中长期决策，不适合短线择时。',

  useCases: ['判断经济周期', '评估市场大环境', '指导资产配置'],

  parameters: {
    indicator: {
      type: 'string',
      description: '指标名称。pmi：制造业景气度（50为荣枯线）；cpi：通胀水平；gdp：经济增速',
      enum: ['pmi', 'cpi', 'gdp'],
      required: true,
      example: 'pmi',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        indicator: { type: 'string' },
        data: { type: 'array' },
        latest: { type: 'object', additionalProperties: true},
        trend: { type: 'string' },
        update_time: { type: 'string' },
      },
    },
    render: (args, data) => [{ type: 'text', text: JSON.stringify(data, null, 2) }],
  },
};
