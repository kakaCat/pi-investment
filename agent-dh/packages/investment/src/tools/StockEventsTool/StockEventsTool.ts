import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { stockEventsPrompt, type StockEventsParams } from './prompt';

export class StockEventsTool extends BaseTool<StockEventsParams, any> {
  protected readonly metadata: ToolMetadata = { name: 'stock_events', category: 'data', version: '1.0.0', timeoutMs: 30000 };
  protected readonly prompt = stockEventsPrompt;
  constructor(private qv2: QuantsysV2Client) { super(); }
  protected validate(args: StockEventsParams): ValidationResult {
    if (!args?.symbol || !/^\d{6}$/.test(args.symbol)) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'symbol', issue: `无效的股票代码: ${args?.symbol}`, expected: 'A股6位数字代码，如 600150', example: '600150' };
    }
    if (args.days !== undefined && (args.days < 1 || args.days > 730)) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'days', issue: 'days 必须在 1-730 之间', received: String(args.days), expected: '1-730' };
    }
    return { success: true };
  }
  protected async execute(args: StockEventsParams, _c: ToolContext): Promise<any> {
    const res: any = await (this.qv2 as any).getSymbolEvents(args.symbol, { days: args.days ?? 90 });
    // 多源失败语义：全源失败 → 显式报错，禁止把失败当"无事件"（排雷场景下这会是致命的假安全）
    if (!res || res.success !== true) {
      const why = res?.error || res?.message || '未知原因';
      const att = res?.attempted_sources ? `（已尝试: ${(res.attempted_sources || []).join(', ')}）` : '';
      throw new Error(`个股事件查询失败（${args.symbol}）：${why}${att}。**禁止据此判定『该股无事件』**——排雷场景下"查不到"与"没有"必须区分`);
    }
    const p: any = res.data ?? res;
    const events: any[] = Array.isArray(p) ? p : (p?.events ?? []);
    const today = new Date().toISOString().slice(0, 10);
    const upcoming = events.filter((e: any) => String(e?.event_date ?? e?.effective_date ?? '') >= today);
    return sanitizeLossless({
      symbol: p?.symbol ?? args.symbol,
      count: events.length,
      upcoming_count: upcoming.length,
      events,
      source: res.source ?? p?.source ?? null,
      attempted_sources: res.attempted_sources ?? null,
      degraded: res.degraded ?? false,
      stale: res.stale ?? false,
      as_of: res.as_of ?? p?.as_of ?? null,
      note: events.length === 0 ? '该窗口内无事件记录（多源均成功返回空，非失败）' : '事件来自多源聚合，逐条带 source/url 可溯源',
    });
  }
}
