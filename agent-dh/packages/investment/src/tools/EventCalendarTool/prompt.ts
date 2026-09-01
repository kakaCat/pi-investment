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
  /** range 模式：事件类型过滤（cpi_ppi/pmi/nbs/lpr/fomc/earnings/futures_delivery/policy/other） */
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
  description: '查询事件日历（特殊日子：宏观数据发布/央行议息/财报披露/期货交割）。适用于：盘前检查未来几日有无重大事件、事件日盘前评估影响、财报季查持仓股披露日、交割日预警。数据来自 quant.event_calendar（2026 年已初始化 FOMC/CPI/PMI/LPR/交割等 67 条）。',

  useCases: ['盘前事件检查', '重大事件预警', '财报披露日查询', '交割日提醒'],

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
};
