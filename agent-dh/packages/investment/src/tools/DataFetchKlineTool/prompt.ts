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
 * 输出结果（对象）。
 * 2026-09-11（REQ-733c5e, w-348bf585）：由纯数组改为对象，
 * 携带后端解析元数据，杜绝"指数/股票同码"静默错配
 * （历史事故：000905 厦门港务的K线被当中证500指数回撤）。
 */
export interface DataFetchKlineResult {
  klines: KlineData[];
  symbol: string;
  count: number;
  resolved_kind?: 'index' | 'stock';
  resolved_name?: string;
  resolved_symbol?: string;
  ambiguity_warning?: string;
  ambiguity_note?: string;
  [key: string]: any;
}

/**
 * 工具提示词
 */
export const dataFetchKlinePrompt: ToolPrompt<DataFetchKlineParams, DataFetchKlineResult> = {
  description: '获取股票历史K线数据：每日开高低收、成交量、成交额，按日期升序返回。适用于：技术分析、趋势研判、计算 MA/RSI/MACD 等技术指标、回测取数。时间段越长返回数据越多，应按需限定日期范围；只要最新价格时用 data_fetch_quote 更轻量。注意：返回带 resolved_kind/resolved_name/ambiguity_warning——当 symbol 是指数与股票同码的歧义代码（如 000905/000852/000001/000016）时，务必先看 ambiguity_warning 确认本次解析为指数还是股票，勿把同名个股当指数。',

  useCases: [
    '技术分析和趋势研判',
    '计算技术指标（MA/RSI/MACD）',
    '回测取数',
  ],

  examples: [
    {
      title: '获取贵州茅台日线数据',
      params: { symbol: '600519', start_date: '2024-01-01', end_date: '2024-12-31' },
      expectedResult: '返回 {klines: 240+ 条日线, resolved_kind: "stock", ...}',
    },
  ],

  notes: [
    '💡 时间段越长返回数据越多',
    '💡 只要最新价格用 data_fetch_quote',
    '⚠️ 歧义代码（指数/股票同码）先看 ambiguity_warning，resolved_kind=stock 且 resolved_name 是具体公司名时说明返回的是个股而非指数',
  ],

  relatedTools: ['data_fetch_quote'],

  parameters: {
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码（如 600519），或指数代码（如 000300；歧义代码建议带市场后缀如 000905.SH 指中证500指数）',
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
      type: 'object', additionalProperties: true,
      properties: {
        klines: {
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
        symbol: { type: 'string' },
        count: { type: 'number' },
        resolved_kind: { type: 'string', description: 'index=指数 / stock=个股（歧义代码据此判断）' },
        resolved_name: { type: 'string', description: '解析出的名称（如 厦门港务 / 中证500）' },
        resolved_symbol: { type: 'string', description: '最终取数用的代码（指数带市场后缀）' },
        ambiguity_warning: { type: 'string', description: '歧义告警：存在且非空=本次解析可能与你的意图不符，必须先读' },
      },
      additionalProperties: true,
    },
    render: (args: DataFetchKlineParams, data: DataFetchKlineResult) => {
      const rows = (data && Array.isArray(data.klines)) ? data.klines : [];
      const count = rows.length;
      if (count === 0) {
        return [{ type: 'text', text: '未获取到 ' + args.symbol + ' 的K线数据' }];
      }

      const dateOf = (row: any): string => row?.trade_date ?? row?.date ?? '';
      const first = rows[0];
      const last = rows[count - 1];
      const priceChange = ((last.close - first.open) / first.open * 100).toFixed(2);
      const changeIcon = parseFloat(priceChange) >= 0 ? '📈' : '📉';

      let output = '## K线数据 - ' + args.symbol + '\n\n';
      if (data && data.ambiguity_warning) {
        output += '### ⚠️ 歧义告警\n' + data.ambiguity_warning + '\n\n';
      }
      if (data && data.resolved_name) {
        output += '- **解析为**: ' + (data.resolved_kind || '?') + ' - ' + data.resolved_name + '\n';
      }
      output += '### 📊 数据概览\n';
      output += '- **数据条数**: ' + count + ' 条\n';
      output += '- **时间范围**: ' + dateOf(first) + ' ~ ' + dateOf(last) + '\n';
      output += '- **周期**: ' + (args.period || 'daily') + '\n';
      output += '- **期间涨跌**: ' + changeIcon + ' ' + priceChange + '%\n\n';
      output += '### 📈 首尾数据\n';
      output += '**起始** (' + dateOf(first) + '): 开 ' + first.open + ' / 收 ' + first.close + '\n';
      output += '**结束** (' + dateOf(last) + '): 开 ' + last.open + ' / 收 ' + last.close + '\n';
      return [{ type: 'text', text: output }];
    },
  },
};
