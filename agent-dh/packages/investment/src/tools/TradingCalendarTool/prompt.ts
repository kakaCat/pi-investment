import type { ToolPrompt } from '@pi-investment/core-tool';

export interface TradingCalendarParams {
  /** 查询日期 YYYY-MM-DD（默认今天） */
  date?: string;
}

export interface TradingCalendarResult {
  date: string;
  is_trading_day: boolean;
  is_weekend: boolean;
  source: string;
  note?: string;
  [key: string]: any;
}

export const tradingCalendarPrompt: ToolPrompt<TradingCalendarParams, TradingCalendarResult> = {
  description: '交易日判断：查指定日期是否 A 股交易日。适用于：下单前确认当日是否开市、回测/任务日期合法性校验。后端数据源（akshare）不可用时自动降级为周末排除法（周六日=非交易日），法定节假日须以交易所公告为准。交易时段与下单规则以交易宪法为准。',

  useCases: ['下单前确认开市', '任务日期校验', '回测日期合法性'],

  parameters: {
    date: {
      type: 'string',
      description: '查询日期 YYYY-MM-DD（默认今天）',
      example: '2026-09-01',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        date: { type: 'string' },
        is_trading_day: { type: 'boolean' },
        is_weekend: { type: 'boolean' },
        source: { type: 'string' },
        note: { type: 'string' },
      },
    },
    render: (args, data) => {
      const mark = data.is_trading_day ? '✅ 交易日' : '❌ 非交易日';
      const lines = [`## ${data.date} ${mark}`, `来源：${data.source}${data.is_weekend ? '（周末）' : ''}`];
      if (data.note) lines.push(`> ${data.note}`);
      return [{ type: 'text', text: lines.join('\n') }];
    },
  },
};
