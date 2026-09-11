/**
 * StockEventsTool - 个股事件（P3/RFC 015 §3）
 *
 * 定位：买入前的**事件排雷**——把"解禁/定增/股东会/财报/减持/监管"这类
 * 会改变供需与预期的事件，从事后看新闻变成事前可查的结构化清单。
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface StockEventsParams { symbol: string; days?: number; }

export const stockEventsPrompt: ToolPrompt<StockEventsParams, any> = {
  name: 'stock_events',
  description: '查询个股事件清单（公告/解禁/定增/股东会/财报/监管/分红），用于买入前排雷与事件驱动分析。适用于：① 买入前确认未来有无解禁/减持等供给冲击；② 财报/股东大会日期临近时评估事件风险；③ 复盘时解释异动的催化剂。注意事项：个股事件来自多源聚合（巨潮/东财/akshare），每条带 source 与 url 可溯源；数据源失败会显式报错，不返回空清单冒充"无事件"。',
  parameters: {
    symbol: { type: 'string', description: 'A股6位代码，如 600150', required: true },
    days: { type: 'integer', description: '回溯/前瞻天数（默认 90，含已公告与未来生效）' },
  },
  output: {
    schema: { type: 'object', additionalProperties: true, properties: {
      symbol: { type: 'string' },
      count: { type: 'integer', description: '事件条数' },
      events: { type: 'array', items: { type: 'object', additionalProperties: true }, description: '事件（type/date/title/source/url/importance）' },
      upcoming_count: { type: 'integer', description: '未来事件数（排雷重点）' },
    }, additionalProperties: true },
    render: (_a: StockEventsParams, v: any) => [{ type: 'text', text: JSON.stringify(v, null, 2) }],
  },
  examples: [
    { scenario: '买入前排雷', params: { symbol: '600150' }, expectedBehavior: '返回事件清单 + upcoming_count' },
    { scenario: '只看近期', params: { symbol: '600150', days: 30 }, expectedBehavior: '窄窗口事件' },
  ],
  useCases: [
    { title: '买入前排雷', description: '解禁/减持/定增是供给冲击，事先可见', example: "stock_events({ symbol: '600150' })" },
    { title: '事件驱动复盘', description: '解释异动催化剂', example: '配合 stock_intel 公告使用' },
  ],
  notes: [
    '2026-09-11 上线（P3/RFC 015 §3）。',
    '与 stock_intel 的分工：stock_intel 抓公告/新闻/内部人「原文」；本工具给**结构化事件**（含类型与生效日）。',
  ],
  relatedTools: [
    { name: 'stock_intel', relationship: '原文', useCase: '需要公告全文时用 stock_intel' },
    { name: 'event_calendar_check', relationship: '宏观日历', useCase: '宏观/行业事件看日历' },
  ],
};
