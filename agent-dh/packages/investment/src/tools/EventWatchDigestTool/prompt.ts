import type { ToolPrompt } from '@pi-investment/core-tool';

export interface EventWatchDigestParams {
  /** 逗号分隔的标的；不传 = 看未来 N 天的全部事件 */
  symbols?: string;
  /** 前瞻天数（1-180），默认 30 */
  days?: number;
}

export const eventWatchDigestPrompt: ToolPrompt<EventWatchDigestParams, any> = {
  description:
    '事件→盯盘规则**建议**（前瞻日历）：列出未来 N 天值得挂规则的事件时点（解禁/财报披露/股东会/定增等），' +
    '每条给出标的、事件类型、事件日、重要度与建议规则名。适用于：盘前把"接下来会发生什么"变成可执行的盯盘计划。' +
    '⚠️ 本工具**只产建议，不建规则**（建规则会真实触发提醒与资金动作，按 R-015 必须经用户确认后用 watch_manage 创建）。' +
    '⚠️ 与 stock_events 的分工：stock_events 问"这只票过去/未来有什么事件"（单标的排雷），' +
    '本工具问"未来 N 天全市场/指定标的有哪些值得盯的时点"（前瞻计划，带规则建议）。' +
    '⚠️ 数据前提：个股事件当前只覆盖「持仓 ∪ 盯盘」宇宙（RFC 015 的 default_universe），' +
    '全市场覆盖是 RFC 015 §4 的待实施项 —— 所以"没有建议"不等于"没有事件"。',

  useCases: [
    { title: '盘前排期', description: '把未来 30 天的解禁/财报时点列出来，提前安排减仓或回避', example: 'event_watch_digest({ days: 30 })' },
    { title: '持仓专项', description: '只看持仓票未来两周有什么要盯', example: 'event_watch_digest({ symbols: "600150,000408", days: 14 })' },
    { title: '建规则前复核', description: '拿到建议后按 R-015 走用户确认，再用 watch_manage 建规则', example: 'event_watch_digest({ symbols: "600150" })' },
  ],

  parameters: {
    symbols: {
      type: 'string',
      description: '逗号分隔的 A 股 6 位代码；不传则看未来 N 天的全部事件（当前覆盖 = 持仓 ∪ 盯盘）',
      example: '600150,000408',
    },
    days: {
      type: 'number',
      description: '前瞻天数（1-180），默认 30',
      default: 30,
      example: 30,
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        success: { type: 'boolean' },
        data: { type: 'array', items: { type: 'object', additionalProperties: true } },
        count: { type: 'number' },
        evaluated: { type: 'number' },
        days: { type: 'number' },
        note: { type: 'string' },
      },
    },
    render: (_args, data: any) => [
      {
        type: 'text',
        text:
          `未来 ${data?.days ?? '?'} 天的盯盘建议（${data?.count ?? 0} 条，评估 ${data?.evaluated ?? 0} 条事件）:\n` +
          JSON.stringify(data, null, 2) +
          '\n⚠️ 以上仅为建议：建规则须按 R-015 经用户确认后调用 watch_manage（本工具不建规则）。',
      },
    ],
  },
};
