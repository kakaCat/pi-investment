/**
 * DataFetchKlineTool - 获取股票K线数据
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 输入参数
 */
export interface DataFetchKlineParams {
  symbol: string;
  start_date: string;
  end_date: string;
  period?: 'daily' | 'weekly' | 'monthly';
}

/**
 * K线数据项
 */
export interface KlineData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  [key: string]: any;
}

/**
 * 输出结果（数组）
 */
export type DataFetchKlineResult = KlineData[];

/**
 * 工具提示词
 */
export const dataFetchKlinePrompt: ToolPrompt<DataFetchKlineParams, DataFetchKlineResult> = {
  description: '获取股票历史K线数据：每日开高低收、成交量、成交额，按日期升序返回。适用于：技术分析、趋势研判、计算 MA/RSI/MACD 等技术指标、回测取数。时间段越长返回数据越多，应按需限定日期范围；只要最新价格时用 data_fetch_quote 更轻量。',

  useCases: [
    '技术分析和趋势研判',
    '计算技术指标（MA/RSI/MACD）',
    '回测取数',
  ],

  examples: [
    {
      title: '获取贵州茅台日线数据',
      params: { symbol: '600519', start_date: '2024-01-01', end_date: '2024-12-31' },
      expectedResult: '返回 240+ 条日线数据',
    },
  ],

  notes: [
    '💡 时间段越长返回数据越多',
    '💡 只要最新价格用 data_fetch_quote',
  ],

  relatedTools: ['data_fetch_quote'],

  parameters: {
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码，如 600519',
      required: true,
      example: '600519',
    },
    start_date: {
      type: 'string',
      description: '开始日期，格式 YYYY-MM-DD，如 2024-01-01',
      required: true,
      example: '2024-01-01',
    },
    end_date: {
      type: 'string',
      description: '结束日期，格式 YYYY-MM-DD，如 2024-12-31',
      required: true,
      example: '2024-12-31',
    },
    period: {
      type: 'string',
      description: 'K线周期。daily（默认）：日线；weekly：周线；monthly：月线',
      enum: ['daily', 'weekly', 'monthly'],
      default: 'daily',
    },
  },

  output: {
    schema: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: true,
        properties: {
          date: { type: 'string', description: '日期' },
          open: { type: 'number', description: '开盘价' },
          high: { type: 'number', description: '最高价' },
          low: { type: 'number', description: '最低价' },
          close: { type: 'number', description: '收盘价' },
          volume: { type: 'number', description: '成交量（股）' },
          amount: { type: 'number', description: '成交额（元）' },
        },
        additionalProperties: true,
      },
    },
    render: (args: DataFetchKlineParams, data: DataFetchKlineResult) => {
      const count = data.length;
      if (count === 0) {
        return [{ type: 'text', text: `未获取到 ${args.symbol} 的K线数据` }];
      }

      const first = data[0];
      const last = data[count - 1];
      const priceChange = ((last.close - first.open) / first.open * 100).toFixed(2);
      const changeIcon = parseFloat(priceChange) >= 0 ? '📈' : '📉';

      let output = `## K线数据 - ${args.symbol}\n\n`;
      output += `### 📊 数据概览\n`;
      output += `- **数据条数**: ${count} 条\n`;
      output += `- **时间范围**: ${first.date} ~ ${last.date}\n`;
      output += `- **周期**: ${args.period || 'daily'}\n`;
      output += `- **期间涨跌**: ${changeIcon} ${priceChange}%\n\n`;

      output += `### 📈 首尾数据\n`;
      output += `**起始** (${first.date}): 开 ${first.open} / 收 ${first.close}\n`;
      output += `**结束** (${last.date}): 开 ${last.open} / 收 ${last.close}\n`;

      return [{ type: 'text', text: output }];
    },
  },
};
