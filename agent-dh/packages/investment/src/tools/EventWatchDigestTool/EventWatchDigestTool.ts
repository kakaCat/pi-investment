import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { eventWatchDigestPrompt, type EventWatchDigestParams } from './prompt';

/**
 * 事件 → 盯盘规则建议（前瞻日历）
 *
 * 为什么需要（2026-09-13 w-a9ec14d7 实测缺口）：事件源早就实现了
 * `EventFeedService.link_to_watchlist()`（application 层）并挂了 API
 * `GET /api/events/watch-suggestions`，但**没有任何 agent 工具消费它**——
 * 等于"装了插座没插电器"：库里有未来事件，agent 却看不到"接下来该盯什么"。
 * 本工具就是那个插头。
 *
 * 纪律：
 * - 只产建议，不建规则（建规则会真实触发提醒/资金动作，按 R-015 须经用户确认）；
 * - 失败必须显式抛错——把"接口挂了"当"没有事件"在排雷/排期场景是致命的假安全。
 */
export class EventWatchDigestTool extends BaseTool<EventWatchDigestParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'event_watch_digest', category: 'data', version: '1.0.0', timeoutMs: 30000,
  };
  protected readonly prompt = eventWatchDigestPrompt;
  constructor(private qv2: QuantsysV2Client) { super(); }

  protected validate(args: EventWatchDigestParams): ValidationResult {
    if (args?.symbols) {
      const list = String(args.symbols).replace(/，/g, ',').split(',').map((s: string) => s.trim()).filter(Boolean);
      const bad = list.filter((s: string) => !/^\d{6}$/.test(s));
      if (bad.length) {
        return {
          success: false, errorType: ErrorType.INPUT_ERROR, field: 'symbols',
          issue: `无效的股票代码: ${bad.join(', ')}`, expected: '逗号分隔的 6 位数字代码',
          example: '600150,000408',
        };
      }
    }
    if (args?.days !== undefined && (args.days < 1 || args.days > 180)) {
      return {
        success: false, errorType: ErrorType.INPUT_ERROR, field: 'days',
        issue: 'days 必须在 1-180 之间', received: String(args.days), expected: '1-180',
      };
    }
    return { success: true };
  }

  protected async execute(args: EventWatchDigestParams, _c: ToolContext): Promise<any> {
    const res: any = await (this.qv2 as any).getEventWatchSuggestions({
      symbols: args?.symbols, days: args?.days ?? 30,
    });
    if (!res || res.success !== true) {
      const why = res?.error || res?.message || '未知原因';
      throw new Error(
        `事件盯盘建议获取失败：${why}。**禁止据此判定『未来没有值得盯的事件』**——这是接口/数据源失败，不是"没有事件"。\n` +
        '可先用 stock_events 逐个标的手工核对，或检查后端 /api/events/watch-suggestions。',
      );
    }
    return res;
  }
}
