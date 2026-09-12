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
    const rawEvents: any[] = Array.isArray(p) ? p : (p?.events ?? []);

    // 2026-09-12 修复（w-adb088f2）：后端 /api/events/symbol/{symbol} 在个股无事件时
    // 会**回落返回全局/宏观事件**（policy/nbs/lpr/pmi/cpi 等，symbols 为空）。
    // 旧实现把它们当作"该股事件"返回 → 排雷时会被误读为个股公告。
    // 现按标的严格过滤：只有 symbols/symbol 命中本标的才算该股事件，
    // 其余单列到 market_events（明确标注为背景，不参与 upcoming 统计）。
    const belongsToSymbol = (e: any): boolean => {
      const syms: string[] = Array.isArray(e?.symbols)
        ? e.symbols.map((s: any) => String(s))
        : (e?.symbol ? [String(e.symbol)] : []);
      return syms.includes(String(args.symbol));
    };
    const events = rawEvents.filter(belongsToSymbol);
    const marketEvents = rawEvents.filter((e: any) => !belongsToSymbol(e));
    const today = new Date().toISOString().slice(0, 10);
    const upcoming = events.filter((e: any) => String(e?.event_date ?? e?.effective_date ?? '') >= today);

    let note: string;
    if (events.length > 0) {
      note = '事件来自多源聚合，逐条带 source/url 可溯源';
    } else if (marketEvents.length > 0) {
      note = `该窗口内**无该股自身事件**；后端同批返回的 ${marketEvents.length} 条为全局/宏观事件（已单列到 market_events，**禁止当作该股事件**）`;
    } else {
      note = '该窗口内无事件记录（多源均成功返回空，非失败）';
    }

    return sanitizeLossless({
      symbol: p?.symbol ?? args.symbol,
      count: events.length,
      upcoming_count: upcoming.length,
      events,
      market_events: marketEvents,
      market_events_count: marketEvents.length,
      raw_count: rawEvents.length,
      source: res.source ?? p?.source ?? null,
      attempted_sources: res.attempted_sources ?? null,
      degraded: res.degraded ?? false,
      stale: res.stale ?? false,
      as_of: res.as_of ?? p?.as_of ?? null,
      note,
    });
  }
}
