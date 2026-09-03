/**
 * CancelPendingOrderTool - 撤销挂单工具提示词和类型定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 参数类型
 */
export interface CancelPendingOrderParams {
  order_id: number;
  account_name?: string;
  reason?: string;
}

/**
 * 返回值类型
 */
export interface CancelPendingOrderResult {
  status: string;
  pending_order_id: number;
  cancelled_order?: {
    symbol: string;
    action: string;
    shares: number;
    price_limit: number | null;
    [key: string]: any;
  };
  [key: string]: any;
}

/**
 * 工具提示词
 */
export const cancelPendingOrderPrompt: ToolPrompt<CancelPendingOrderParams, CancelPendingOrderResult> = {
  description: '撤销未成交挂单（写操作，仅 pending 状态可撤）。适用于：发现重复/错误挂单、止盈止损计划变更、清理过期盘前挂单。撤单前必须先用 trade_monitor 确认挂单状态与内容，防止误撤。成交/已撤/过期的单子不可再撤（后端会拒绝）。',

  useCases: [
    '撤销重复的盘前挂单（防双重成交）',
    '计划变更时清理旧挂单',
    '止损/止盈规则更新后撤销过时的限价单',
  ],

  examples: [
    {
      title: '撤销指定挂单',
      params: {
        order_id: 19,
        account_name: 'agent_virtual',
        reason: '与 id=18 重复的 SELL 单，保留限价保护版',
      },
      expectedResult: '返回 status=cancelled 与被撤单详情',
    },
  ],

  notes: [
    '写操作：撤单立即生效，不可恢复（需重新挂单）',
    '仅 pending 状态可撤；filled/cancelled/expired 后端返回错误',
    '撤单不受交易时段限制（风险削减操作），但重新挂单仍须遵守交易时段',
    '建议填 reason 记录撤单依据，供复盘归因',
  ],

  relatedTools: [
    'trade_monitor',
    'portfolio_trade',
    'watch_manage',
  ],

  parameters: {
    order_id: {
      type: 'integer',
      description: '挂单 ID（trade_monitor 返回的 pending_orders[].id），必填',
      required: true,
    },
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      default: 'agent_virtual',
    },
    reason: {
      type: 'string',
      description: '撤单依据（强烈建议填写）：为什么撤、保留哪笔单',
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string', description: '撤单结果状态（cancelled）' },
        pending_order_id: { type: 'integer', description: '被撤销的挂单 ID' },
        cancelled_order: { type: 'object', additionalProperties: true, description: '被撤挂单的详情快照' },
      },
      additionalProperties: true,
    },
    render: (_args, value) => [{
      type: 'text',
      text: JSON.stringify(value, null, 2),
    }],
  },
};
