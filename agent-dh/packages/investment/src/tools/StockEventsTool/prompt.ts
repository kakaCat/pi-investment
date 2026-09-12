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
  description: '查询个股事件清单（公告/解禁/定增/股东会/财报/监管/分红），用于买入前排雷与事件驱动分析。适用于：① 买入前确认未来有无解禁/减持等供给冲击（排雷核心）；② 财报/股东大会日期临近时评估事件风险；③ 复盘时解释异动的催化剂。配合 event_calendar_check 使用：宏观事件看日历，个股事件用本工具。注意事项：个股事件来自多源聚合（巨潮/东财/akshare），每条带 source 与 url 可溯源；数据源失败会显式报错，不返回空清单冒充"无事件"。',
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
    { title: '买入前排雷（核心场景）', description: '确认未来有无解禁/减持/定增等供给冲击，upcoming_count > 0 需评估', example: "stock_events({ symbol: '600150' })" },
    { title: '持仓监控', description: '定期检查持仓股票的 upcoming_count，提前应对风险事件', example: 'position_list 后逐个 stock_events' },
    { title: '事件驱动复盘', description: '解释异动催化剂，结合 stock_intel 查看公告原文', example: '配合 stock_intel 公告使用' },
    { title: '财报季管理', description: '查询持仓股票的财报披露日，提前准备策略', example: "stock_events({ symbol: '600519', days: 60 })" },
  ],
  notes: [
    '2026-09-11 上线（P3/RFC 015 §3）。P1-4 事件双轨合流：本工具负责个股事件，event_calendar_check 负责宏观/行业事件。',
    '与 stock_intel 的分工：stock_intel 抓公告/新闻/内部人「原文」；本工具给**结构化事件**（含类型与生效日）。',
    '排雷最佳实践：买入前必查 upcoming_count，重点关注 unlock（解禁）、placement（定增）、regulatory（监管）类事件。',
    '与 event_calendar_check 配合：盘前先 event_calendar_check 看宏观，买入前 stock_events 看个股。',
  ],
  relatedTools: [
    { name: 'event_calendar_check', relationship: '宏观/行业事件', useCase: '盘前检查宏观事件（CPI/PMI/央行议息），本工具查个股事件' },
    { name: 'stock_intel', relationship: '公告/新闻原文', useCase: '需要公告全文或内部人交易详情时使用' },
    { name: 'data_fetch_financial', relationship: '基本面', useCase: '事件驱动分析时配合基本面判断' },
    { name: 'portfolio_trade', relationship: '交易执行', useCase: '排雷后确认无重大风险再执行买入' },
  ],
};
