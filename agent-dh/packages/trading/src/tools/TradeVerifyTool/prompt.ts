/**
 * TradeVerifyTool - 交易对账工具提示词和类型定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 参数类型
 */
export interface TradeVerifyParams {
  account_name?: string;
  date?: string;
}

/**
 * 返回值类型
 */
export interface TradeVerifyResult {
  date: string;
  total_orders: number;
  matched: number;
  mismatched: number;
  anomalies: Array<{
    order_id: string;
    issue: string;
    expected?: any;
    actual?: any;
    [key: string]: any;
  }>;
  [key: string]: any;
}

/**
 * 工具提示词
 */
export const tradeVerifyPrompt: ToolPrompt<TradeVerifyParams, TradeVerifyResult> = {
  description: '交易对账：核对当日成交记录与预期，输出异常列表。适用于：每日收盘后例行核对，发现漏单、错单、重复成交等问题；发现交易异常后排查。只读操作。',

  useCases: [
    '每日收盘后例行对账',
    '发现漏单、错单、重复成交',
    '交易异常排查',
  ],

  examples: [
    {
      title: '对账当日交易',
      params: {
        account_name: 'agent_virtual',
      },
      expectedResult: '返回当日对账结果，包含异常列表',
    },
    {
      title: '对账指定日期',
      params: {
        account_name: 'agent_virtual',
        date: '2026-08-28',
      },
      expectedResult: '返回该日期对账结果',
    },
  ],

  notes: [
    '建议每日收盘后执行一次全量核对',
    '发现差异时需人工介入排查根因',
    '只读操作，不会修改任何数据',
    'date 参数必须是 YYYY-MM-DD 格式',
  ],

  relatedTools: [
    'trade_monitor',
    'account_info',
    'portfolio_trade',
  ],

  parameters: {
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      default: 'agent_virtual',
    },
    date: {
      type: 'string',
      description: '对账日期，格式 YYYY-MM-DD。不传则对账当日',
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        date: { type: 'string', description: '对账日期' },
        total_orders: { type: 'integer', description: '总订单数' },
        matched: { type: 'integer', description: '匹配数' },
        mismatched: { type: 'integer', description: '异常数' },
        anomalies: { type: 'array', description: '异常列表' },
      },
      additionalProperties: true,
    },
    render: (args, value) => [{
      type: 'text',
      text: JSON.stringify(value, null, 2),
    }],
  },
};
