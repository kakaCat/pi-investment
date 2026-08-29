import type { ToolPrompt } from '@pi-investment/core-tool';

export interface DataFetchNorthFlowParams {
  days?: number;
}

export interface DataFetchNorthFlowResult {
  dates: string[];
  net_inflows: number[];
  sh_net_inflows: number[];
  sz_net_inflows: number[];
  cumulative: number;
  daily: Array<Record<string, any>>;
  [key: string]: any;
}

export const dataFetchNorthFlowPrompt: ToolPrompt<DataFetchNorthFlowParams, DataFetchNorthFlowResult> = {
  description: '获取北向资金（沪股通+深股通）流向：每日净流入、累计净流入、沪/深分项。适用于：判断外资对A股的态度，持续净流入通常视为利好信号。注意：上游数据源较慢，调用可能需要约1分钟。',

  useCases: ['判断外资态度', '分析资金流向'],

  parameters: {
    days: {
      type: 'number',
      description: '返回最近 N 个交易日的数据，默认 5。看趋势建议取 20 以上',
      default: 5,
      example: 20,
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        dates: { type: 'array' },
        net_inflows: { type: 'array' },
        sh_net_inflows: { type: 'array' },
        sz_net_inflows: { type: 'array' },
        cumulative: { type: 'number' },
        daily: { type: 'array' },
      },
    },
    render: (args, data) => [{ type: 'text', text: JSON.stringify(data, null, 2) }],
  },
};
