/**
 * DataFetchQuoteTool - 获取股票实时行情
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 输入参数
 */
export interface DataFetchQuoteParams {
  symbol: string;
  source?: 'auto' | 'realtime' | 'db';
}

/**
 * 输出结果
 */
export interface DataFetchQuoteResult {
  symbol: string;
  name: string;
  price: number;
  open: number;
  high: number;
  low: number;
  prevClose: number;
  change: number;
  changePct: number;
  volume: number;
  amount: number;
  source: string;
  timestamp: string;
  [key: string]: any;
}

/**
 * 工具提示词
 */
export const dataFetchQuotePrompt: ToolPrompt<DataFetchQuoteParams, DataFetchQuoteResult> = {
  description: '获取股票实时行情快照：最新价、开高低、昨收、涨跌额/涨跌幅、成交量、成交额。适用于：盘中查看个股即时表现、下单前确认当前价格。非交易时段返回最近一个交易日的收盘数据。需要历史走势用 data_fetch_kline；需要估值与基本面用 data_fetch_financial。',

  useCases: [
    '盘中查看个股即时表现',
    '下单前确认当前价格',
    '快速获取股票最新价',
  ],

  examples: [
    {
      title: '获取贵州茅台实时行情',
      params: { symbol: '600519' },
      expectedResult: '当前价: 1650元, 涨跌幅: +2.5%',
    },
  ],

  notes: [
    '💡 非交易时段返回最近一个交易日收盘数据',
    '💡 需要历史走势用 data_fetch_kline',
  ],

  relatedTools: ['data_fetch_kline', 'data_fetch_financial'],

  parameters: {
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码，不带交易所前缀。如 600519（贵州茅台）、000001（平安银行）、300750（宁德时代）',
      required: true,
      example: '600519',
    },
    source: {
      type: 'string',
      description: '数据源。auto（默认）：优先实时行情，不可用时回退数据库缓存；realtime：强制实时，获取失败即报错，下单前建议用；db：只读数据库缓存，速度快但可能不是最新，批量查询或复盘时建议用',
      enum: ['auto', 'realtime', 'db'],
      default: 'auto',
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        symbol: { type: 'string', description: '股票代码' },
        name: { type: 'string', description: '股票名称' },
        price: { type: 'number', description: '当前价格（元）' },
        open: { type: 'number', description: '开盘价（元）' },
        high: { type: 'number', description: '最高价（元）' },
        low: { type: 'number', description: '最低价（元）' },
        prevClose: { type: 'number', description: '昨收价（元）' },
        change: { type: 'number', description: '涨跌额（元）' },
        changePct: { type: 'number', description: '涨跌幅（%）' },
        volume: { type: 'number', description: '成交量（股）' },
        amount: { type: 'number', description: '成交额（元）' },
        source: { type: 'string', description: '数据来源' },
        timestamp: { type: 'string', description: '行情时间戳' },
      },
      additionalProperties: true,
    },
    render: (args: DataFetchQuoteParams, data: DataFetchQuoteResult) => {
      const changeIcon = data.changePct >= 0 ? '📈' : '📉';
      const changeSign = data.changePct >= 0 ? '+' : '';

      let output = `## ${data.name} (${data.symbol})\n\n`;
      output += `### ${changeIcon} 实时行情\n`;
      output += `- **当前价**: ${data.price.toFixed(2)} 元\n`;
      output += `- **涨跌幅**: ${changeSign}${data.changePct.toFixed(2)}% (${changeSign}${data.change.toFixed(2)} 元)\n`;
      output += `- **开盘**: ${data.open.toFixed(2)} 元\n`;
      output += `- **最高**: ${data.high.toFixed(2)} 元\n`;
      output += `- **最低**: ${data.low.toFixed(2)} 元\n`;
      output += `- **昨收**: ${data.prevClose.toFixed(2)} 元\n`;
      output += `- **成交量**: ${(data.volume / 10000).toFixed(2)} 万股\n`;
      output += `- **成交额**: ${(data.amount / 100000000).toFixed(2)} 亿元\n\n`;
      output += `**数据来源**: ${data.source} | **时间**: ${data.timestamp}\n`;

      return [{ type: 'text', text: output }];
    },
  },
};
