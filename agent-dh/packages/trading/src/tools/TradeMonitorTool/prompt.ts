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
  /**
   * 是否附带**盘前挂单明细**（execute_at='market_open' 的排队单）。
   *
   * 默认 **false**（用户 2026-09-13 裁定）：默认只给聚合计数 queued_count，
   * 避免明细里很长的 reason 让输出膨胀；需要逐笔核对时再传 true。
   * ⚠️ 两个计数别混读（2026-09-13 实测踩坑）：
   *   · queued_count  = **排队中**的盘前挂单数（真正「还没成交」的单，恒返回）
   *   · pending_count = 历史订单接口里状态为 pending 的笔数（**不含**盘前挂单，常为 0）
   *   曾因只看 pending_count=0 而误判「没挂上单」，而实际有 17 笔在排队。
   */
  include_pending?: boolean;
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
  /** 排队中的盘前挂单数（= pending_orders.length；恒返回，判断「挂上没有」看它） */
  queued_count: number;
  /** 历史订单接口里 pending 的笔数；**不含盘前挂单**，易误读，默认不返回 */
  pending_count?: number;
  filled_count: number;
  /** 盘前挂单明细（include_pending=true 时返回） */
  pending_orders?: any[];
  [key: string]: any;
}

/**
 * 工具提示词
 */
export const tradeMonitorPrompt: ToolPrompt<TradeMonitorParams, TradeMonitorResult> = {
  description: '查询订单执行状态与成交明细。适用于：portfolio_trade 或 algo_execute 之后确认成交结果、检查未成交订单。只读操作。⚠️ 盘前挂单（execute_at=market_open）的**排队笔数**看 queued_count（恒返回）；明细默认不返回，需要时传 include_pending=true；不要用 pending_count 判断「有没有挂上」（它不含盘前挂单）。每日收盘后核对全部成交用 trade_verify。',

  useCases: [
    '交易执行后确认订单状态',
    '检查未成交订单',
    '查询历史订单记录',
  ],

  examples: [
    {
      title: '查询所有订单',
      params: {
        account_name: 'agent_brain',
      },
      expectedResult: '返回近期全部订单列表',
    },
    {
      title: '查询特定订单',
      params: {
        account_name: 'agent_brain',
        order_id: 'ORD-20260828-001',
      },
      expectedResult: '返回该订单的详细信息',
    },
  ],

  notes: [
    '只读操作，不会修改任何数据',
    '返回近期订单，不包含历史全量数据',
    '每日收盘后核对全部成交请使用 trade_verify',
    '⚠️ 两个计数别混读：queued_count=排队中的盘前挂单数（判断「我挂上了吗」看它）；pending_count=历史订单里 pending 的笔数（不含盘前挂单，常为 0）。2026-09-13 实测：只看 pending_count=0 会误判「没挂单」，而实际有 17 笔排队。',
    '盘前挂单明细默认不返回（避免 reason 字段让输出膨胀）：逐笔核对时传 include_pending=true。',
  ],

  relatedTools: [
    'portfolio_trade',
    'algo_execute',
    'trade_verify',
  ],

  parameters: {
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_brain',
      default: 'agent_brain',
    },
    order_id: {
      type: 'string',
      description: '订单ID。传入则只查该订单；不传则返回近期全部订单',
    },
    include_pending: {
      type: 'boolean',
      description: '是否返回盘前挂单明细（默认 false：只给 queued_count 计数，明细按需取）',
      default: false,
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        orders: { type: 'array', description: '订单列表' },
        queued_count: { type: 'integer', description: '排队中的盘前挂单数（恒返回）' },
        pending_count: { type: 'integer', description: '历史订单里 pending 笔数（不含盘前挂单；include_pending=true 才返回）' },
        filled_count: { type: 'integer', description: '已成交订单数' },
      },
    },
    render: (_args, value) => [{
      type: 'text',
      text: JSON.stringify(value, null, 2),
    }],
  },
};
