import type { ToolPrompt } from '@pi-investment/core-tool';

export interface EventCalendarParams {
  /** 查询模式：upcoming=未来N天待处理事件；range=按日期区间/条件过滤 */
  mode?: 'upcoming' | 'range';
  /** upcoming 模式：未来天数（默认 2，含今天） */
  days?: number;
  /** range 模式：开始日期 YYYY-MM-DD */
  start?: string;
  /** range 模式：结束日期 YYYY-MM-DD */
  end?: string;
  /** 事件层级过滤（P3/RFC 015 §3）：macro=宏观（既有日历）/ industry=行业 / individual=个股。
   *  传入 scope 时改走多源事件流接口（/api/events/feed），可查宏观之外的行业与个股事件。 */
  scope?: 'macro' | 'industry' | 'individual';
  /** range 模式：事件类型过滤（cpi_ppi/pmi/nbs/lpr/fomc/earnings/futures_delivery/policy/other，
   *  以及 P3 新增：unlock/placement/shareholder_meeting/regulatory/dividend） */
  event_type?: string;
  /** range 模式：状态过滤（pending/notified/collected/reviewed/skipped） */
  status?: string;
  /** range 模式：标的代码过滤（财报/交割/解禁用） */
  symbol?: string;
}

export interface EventCalendarResult {
  mode: string;
  count: number;
  events: Array<Record<string, any>>;
  note?: string;
  [key: string]: any;
}

export const eventCalendarPrompt: ToolPrompt<EventCalendarParams, EventCalendarResult> = {
  description: '查询事件日历（宏观/行业事件）。适用于：盘前检查未来几日的重大宏观事件（CPI/PMI/央行议息）、行业政策事件。⚠️ 查询个股事件（解禁/财报/股东会）请用 stock_events 工具（体验更好，专门针对个股排雷）。数据来自 quant.event_calendar（2026 年已初始化 FOMC/CPI/PMI/LPR/交割等 67 条）。',

  useCases: [
    { title: '每日盘前检查', description: '查未来2天的宏观事件', example: 'event_calendar_check({ days: 2 })' },
    { title: '宏观环境评估', description: '查本周/本月的CPI/PMI/FOMC等', example: 'event_calendar_check({ mode: "range", start: "2026-09-11", end: "2026-09-18", scope: "macro" })' },
    { title: '行业政策监控', description: '查询行业政策、产业变化', example: 'event_calendar_check({ scope: "industry", event_type: "policy" })' },
  ],

  parameters: {
    mode: {
      type: 'string',
      description: '查询模式。upcoming（默认）：查未来N天待处理事件（每日检查核心）；range：按日期区间/类型/状态/标的过滤',
      enum: ['upcoming', 'range'],
      example: 'upcoming',
    },
    days: {
      type: 'number',
      description: 'upcoming 模式：未来天数（0-30，默认 2，含今天）',
      example: 2,
    },
    start: {
      type: 'string',
      description: 'range 模式：开始日期 YYYY-MM-DD',
      example: '2026-09-01',
    },
    end: {
      type: 'string',
      description: 'range 模式：结束日期 YYYY-MM-DD',
      example: '2026-09-30',
    },
    event_type: {
      type: 'string',
      description: 'range 模式：事件类型。cpi_ppi/pmi/nbs/lpr/fomc/earnings/futures_delivery/policy/other',
      example: 'fomc',
    },
    status: {
      type: 'string',
      description: 'range 模式：状态。pending/notified/collected/reviewed/skipped',
      example: 'pending',
    },
    symbol: {
      type: 'string',
      description: 'range 模式：标的代码（财报/交割/解禁用）',
      example: '002241',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        mode: { type: 'string' },
        count: { type: 'number' },
        events: { type: 'array' },
        note: { type: 'string' },
      },
    },
    render: (args, data) => {
      const lines: string[] = [];
      lines.push(`## 事件日历查询（${data.mode}）`);
      lines.push(`共 ${data.count} 条事件`);
      lines.push('');
      if (data.events.length === 0) {
        lines.push('（无事件）');
      } else {
        for (const e of data.events) {
          const imp = e.importance === 3 ? '🔴高' : e.importance === 2 ? '🟡中' : '⚪低';
          const time = e.event_time ? ` ${e.event_time}` : '';
          const sym = e.symbol ? ` [${e.symbol}]` : '';
          lines.push(`- **${e.event_date}**${time}${sym} [${e.event_type}] ${e.title}（${imp}，${e.status}）`);
          if (e.description) lines.push(`  ${e.description}`);
        }
      }
      if (data.note) lines.push('', `> ${data.note}`);
      return [{ type: 'text', text: lines.join('\n') }];
    },
  },

  examples: [
    {
      scenario: '每日盘前检查（最常用）',
      params: { mode: 'upcoming', days: 2 },
      expectedBehavior: '返回未来2天的待处理宏观事件',
    },
    {
      scenario: '查本周宏观事件',
      params: { mode: 'range', start: '2026-09-11', end: '2026-09-18', scope: 'macro' },
      expectedBehavior: '返回本周的CPI/PMI/FOMC等宏观事件',
    },
  ],

  notes: [
    '2026-09-11: P1-4 事件双轨合流 - 明确工具分工（本工具负责宏观/行业，个股用 stock_events）',
    '查个股事件时：虽然本工具支持 scope=individual + symbol，但 stock_events 工具体验更好（专门针对个股排雷设计）',
    '每日盘前例行：event_calendar_check({ days: 2 }) 查宏观事件 + stock_events({ symbol }) 查持仓股票事件',
  ],

  relatedTools: [
    { name: 'stock_events', relationship: '个股事件排雷', useCase: '买入前/持仓监控时查个股事件（解禁/财报/股东会）' },
    { name: 'stock_intel', relationship: '个股公告原文', useCase: '需要公告/新闻全文时使用' },
    { name: 'data_fetch_macro', relationship: '宏观数据', useCase: '查询宏观指标的历史值和趋势' },
  ],
};
