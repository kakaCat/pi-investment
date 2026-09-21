/**
 * TradingStatusTool - 交易状态（可交易性硬校验，P1/RFC 015）
 *
 * 背景（2026-09-11，w-f436d4ea）：下单前无法判断停牌/ST/涨跌停，等于闭眼下市价单。
 * 本工具把"可交易性"变成下单前的硬校验，且**跨源冲突时按保守值（不可交易）裁决**——
 * 宁可错杀一次委托，不可在停牌票上误下单。
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface TradingStatusParams {
  symbol: string;
}

export const tradingStatusPrompt: ToolPrompt<TradingStatusParams, any> = {
  name: 'trading_status',
  description: '查询个股交易状态（ST / 停牌 / 涨停 / 跌停 / 可交易性 + 涨跌幅限制）。适用于：①下单前硬校验（避免在停牌/涨停板上误下单）；②判断涨跌幅限制（主板 10% / 创业板科创 20% / ST 5%）；③风控与盯盘规则的前置条件。口径：基础状态来自 stocks 表（is_st/is_suspended），动态部分由实时行情推导；**两者冲突时取保守值（判为不可交易）**并标注 conflict。',

  parameters: {
    symbol: { type: 'string', description: 'A股6位代码，如 600150', required: true },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        symbol: { type: 'string' },
        is_st: { type: 'boolean', description: '是否 ST（涨跌幅限制 5%）' },
        is_suspended: { type: 'boolean', description: '是否停牌' },
        limit_up: { type: 'boolean', description: '是否涨停（难以买入）' },
        limit_down: { type: 'boolean', description: '是否跌停' },
        tradeable: { type: 'boolean', description: '是否可交易（下单前必须为 true）' },
        limit_ratio: { type: 'number', description: '涨跌幅限制（0.05/0.10/0.20）' },
        reason: { type: 'string', description: '判定说明（含跨源冲突标注）' },
        as_of: { type: 'string', description: '数据时点' },
      },
      additionalProperties: true,
    },
    render: (_args: TradingStatusParams, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
  },

  examples: [
    { scenario: '下单前校验', params: { symbol: '600150' }, expectedBehavior: '返回 tradeable/limit_ratio/reason/as_of' },
    { scenario: '检查 ST 股限幅', params: { symbol: '600150' }, expectedBehavior: 'is_st=true 时 limit_ratio=0.05' },
  ],

  useCases: [
    { title: '下单前硬校验', description: 'tradeable=false 时不得下单（fail-closed）', example: "trading_status({ symbol: '600150' })" },
    { title: '涨跌幅限制查询', description: '用于止损/止盈价位的合规计算', example: '跌停价 = 昨收 × (1 - limit_ratio)' },
  ],

  notes: [
    '2026-09-11 上线（P1/RFC 015）。',
    '保守裁决：stocks 表与行情推导矛盾 → 判不可交易 + reason 标注 conflict（宁错杀不误杀账户）。',
    '状态无法确定时同样 fail-closed（不返回 tradeable=true）。',
  ],

  relatedTools: [
    { name: 'portfolio_trade', relationship: '交易执行', useCase: '下单前的强制前置校验' },
    { name: 'risk_controller', relationship: '风控计算', useCase: '止损价需结合涨跌幅限制' },
  ],
};
