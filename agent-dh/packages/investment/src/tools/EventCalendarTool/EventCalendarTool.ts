import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { eventCalendarPrompt, EventCalendarParams, EventCalendarResult } from './prompt';

const VALID_TYPES = ['cpi_ppi', 'pmi', 'nbs', 'lpr', 'fomc', 'us_cpi', 'nfp', 'earnings', 'futures_delivery', 'policy', 'other'];
const VALID_STATUSES = ['pending', 'notified', 'collected', 'reviewed', 'skipped'];

export class EventCalendarTool extends BaseTool<EventCalendarParams, EventCalendarResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'event_calendar_check',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = eventCalendarPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: EventCalendarParams): ValidationResult {
    const mode = args.mode || 'upcoming';
    if (mode !== 'upcoming' && mode !== 'range') {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'mode',
        issue: 'mode 必须是 upcoming 或 range',
        received: mode,
        expected: 'upcoming | range',
      };
    }
    if (args.days !== undefined && (typeof args.days !== 'number' || args.days < 0 || args.days > 30)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'days',
        issue: 'days 必须是 0-30 的数字',
        received: args.days,
        expected: '0-30',
      };
    }
    if (args.event_type && !VALID_TYPES.includes(args.event_type)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'event_type',
        issue: `event_type 非法`,
        received: args.event_type,
        expected: VALID_TYPES.join(' | '),
      };
    }
    if (args.status && !VALID_STATUSES.includes(args.status)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'status',
        issue: `status 非法`,
        received: args.status,
        expected: VALID_STATUSES.join(' | '),
      };
    }
    return { success: true };
  }

  protected async execute(
    args: EventCalendarParams,
    context: ToolContext
  ): Promise<EventCalendarResult> {
    const mode = args.mode || 'upcoming';

    if (mode === 'upcoming') {
      const days = args.days ?? 2;
      const res = await this.qv2.getUpcomingEvents(days);
      return {
        mode: `upcoming(${days}天)`,
        count: res.count ?? res.events?.length ?? 0,
        events: res.events ?? [],
        note: (res.count ?? 0) === 0 ? '未来无待处理事件' : undefined,
      };
    }

    // range 模式
    const res = await this.qv2.listEvents({
      start: args.start,
      end: args.end,
      event_type: args.event_type,
      status: args.status,
      symbol: args.symbol,
    });
    return {
      mode: 'range',
      count: res.count ?? res.events?.length ?? 0,
      events: res.events ?? [],
      note: (res.count ?? 0) === 0 ? '区间内无匹配事件' : undefined,
    };
  }
}
