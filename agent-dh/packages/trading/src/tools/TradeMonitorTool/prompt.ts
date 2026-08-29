/**
 * TradeMonitorTool - 交易监控工具提示词和类型定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 参数类型
 */
export interface TradeMonitorParams {
  account_name?: string;
  order_id?: string;
}

/**
 * 返回值类型
 */
export interface TradeMonitorResult {
  orders: Array<{
    order_id: string;
    action: string;
    symbol: string;
    quantity: number;
    price: number;
    status: string;
    timestamp: string;
    [key: string]: any;
  }>;
  pending_count: number;
  filled_count: number;
  [key: string]: any;
}

/**
 * 工具提示词
 */
export const tradeMonitorPrompt: ToolPrompt<TradeMonitorParams, TradeMonitorResult> = {
  description: '查询订单执行状态与成交明细。适用于：portfolio_trade 或 algo_execute 之后确认成交结果、检查未成交订单。只读操作。每日收盘后核对全部成交用 trade_verify。',

  useCases: [
    '交易执行后确认订单状态',
    '检查未成交订单',
    '查询历史订单记录',
  ],

  examples: [
    {
      title: '查询所有订单',
      params: {
        account_name: 'agent_virtual',
      },
      expectedResult: '返回近期全部订单列表',
    },
    {
      title: '查询特定订单',
      params: {
        account_name: 'agent_virtual',
        order_id: 'ORD-20260828-001',
      },
      expectedResult: '返回该订单的详细信息',
    },
  ],

  notes: [
    '只读操作，不会修改任何数据',
    '返回近期订单，不包含历史全量数据',
    '每日收盘后核对全部成交请使用 trade_verify',
  ],

  relatedTools: [
    'portfolio_trade',
    'algo_execute',
    'trade_verify',
  ],

  parameters: {
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      default: 'agent_virtual',
    },
    order_id: {
      type: 'string',
      description: '订单ID。传入则只查该订单；不传则返回近期全部订单',
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        orders: { type: 'array', description: '订单列表' },
        pending_count: { type: 'integer', description: '未成交订单数' },
        filled_count: { type: 'integer', description: '已成交订单数' },
      },
      additionalProperties: true,
    },
    render: (args, value) => [{
      type: 'text',
      text: JSON.stringify(value, null, 2),
    }],
  },
};
