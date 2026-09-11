import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { eventCalendarPrompt, EventCalendarParams, EventCalendarResult } from './prompt';

const VALID_TYPES = ['cpi_ppi', 'pmi', 'nbs', 'lpr', 'fomc', 'us_cpi', 'nfp', 'earnings', 'futures_delivery', 'policy', 'other'];
const VALID_STATUSES = ['pending', 'notified', 'collected', 'reviewed', 'skipped'];
// P3/RFC 015 §3：事件层级（macro=既有宏观日历；industry/individual=多源事件流）
const VALID_SCOPES = ['macro', 'industry', 'individual'];

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
    if (args.scope && !VALID_SCOPES.includes(args.scope)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'scope',
        issue: 'scope 非法',
        received: args.scope,
        expected: VALID_SCOPES.join(' | '),
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

    // P3/RFC 015 §3：指定 scope 时改走多源事件流（宏观之外新增行业/个股事件）。
    // 保持既有行为兼容：不传 scope 时完全走原路径。
    if (args.scope) {
      const res: any = await (this.qv2 as any).getEventsFeed({
        scope: args.scope,
        type: args.event_type,
        date_from: args.start,
        date_to: args.end,
        limit: 200,
      });
      // 多源失败语义：显式失败，禁止把失败当「无事件」
      if (!res || res.success !== true) {
        const why = res?.error || res?.message || '未知原因';
        const att = res?.attempted_sources ? `（已尝试: ${(res.attempted_sources || []).join(', ')}）` : '';
        throw new Error(`事件流查询失败（scope=${args.scope}）：${why}${att}。禁止据此判定『无事件』`);
      }
      const p: any = res.data ?? res;
      const events: any[] = Array.isArray(p) ? p : (p?.events ?? []);
      return {
        mode: `feed(scope=${args.scope}${args.event_type ? ', type=' + args.event_type : ''})`,
        count: events.length,
        events,
        note: `多源事件流：source=${res.source ?? p?.source ?? '?'}；attempted=${(res.attempted_sources ?? []).join(',') || '-'}；degraded=${res.degraded ?? false}；as_of=${res.as_of ?? p?.as_of ?? '?'}`,
      } as any;
    }

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
