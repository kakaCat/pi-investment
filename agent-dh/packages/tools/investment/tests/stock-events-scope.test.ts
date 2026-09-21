import { describe, it, expect } from 'vitest';
import { StockEventsTool } from '../src/tools/StockEventsTool/StockEventsTool';

/**
 * stock_events 标的过滤回归（2026-09-12，w-adb088f2）
 * 缺陷：后端在个股无事件时回落返回全局/宏观事件，旧实现原样当『该股事件』返回
 * （实证：600919 返回 21 条 policy/nbs/lpr，symbols 为空）→ 排雷场景会被误读。
 * 契约：events 只含 symbols 命中本标的的事件；全局事件单列 market_events。
 */

const tool = (payload: any, opts: { success?: boolean } = {}) =>
  new StockEventsTool({
    getSymbolEvents: async () => (opts.success === false ? { success: false, error: 'all sources failed' } : { success: true, data: payload }),
  } as any) as any;

describe('stock_events 标的过滤', () => {
  it('混合返回：个股事件进 events，全局事件进 market_events', async () => {
    const t = tool({
      symbol: '600919',
      events: [
        { event_date: '2026-09-10', type: 'regulatory', symbols: ['600919'], title: '个股公告A' },
        { event_date: '2026-09-15', type: 'nbs', symbols: [], title: '国民经济运行数据发布' },
        { event_date: '2026-09-16', type: 'fomc', title: 'FOMC 决议' },
        { event_date: '2026-09-11', type: 'dividend', symbol: '600919', title: '分红实施' },
      ],
    });
    const r: any = await t.call({ symbol: '600919', days: 45 });
    expect(r.data.count).toBe(2);
    expect(r.data.events.map((e: any) => e.title)).toEqual(['个股公告A', '分红实施']);
    expect(r.data.market_events_count).toBe(2);
    expect(r.data.raw_count).toBe(4);
    expect(r.data.note).toContain('可溯源');
  });

  it('仅有全局事件 → events 为空且 note 明确禁止当作该股事件', async () => {
    const t = tool({ events: [ { event_date: '2026-09-15', type: 'nbs', title: '宏观' } ] });
    const r: any = await t.call({ symbol: '600919' });
    expect(r.data.count).toBe(0);
    expect(r.data.upcoming_count).toBe(0);
    expect(r.data.market_events_count).toBe(1);
    expect(r.data.note).toContain('无该股自身事件');
    expect(r.data.note).toContain('禁止当作该股事件');
  });

  it('真的没有任何事件 → note 说明是空而非失败', async () => {
    const t = tool({ events: [] });
    const r: any = await t.call({ symbol: '600919' });
    expect(r.data.count).toBe(0);
    expect(r.data.note).toContain('非失败');
  });

  it('symbols 带交易所后缀/前缀时仍认得住（不做假阴性）', async () => {
    // 2026-09-13 第三批审阅 A10：后端 symbols 存在 600150.SH / SH600150 等写法，
    // 原样比较会让真事件被错判成 market_events（排雷时"有雷当无雷"）。
    const t = tool({
      events: [
        { event_date: '2026-09-10', type: 'regulatory', symbols: ['600150.SH'], title: '后缀式' },
        { event_date: '2026-09-11', type: 'dividend', symbol: 'SH600150', title: '前缀式' },
        { event_date: '2026-09-12', type: 'nbs', symbols: [], title: '宏观' },
        { event_date: '2026-09-12', type: 'regulatory', symbols: ['600151'], title: '其它股' },
      ],
    });
    const r: any = await t.call({ symbol: '600150' });
    expect(r.data.count).toBe(2);
    expect(r.data.events.map((e: any) => e.title)).toEqual(['后缀式', '前缀式']);
    expect(r.data.market_events_count).toBe(2);
  });

  it('多源全失败仍显式报错（不把失败当无事件）', async () => {
    const t = tool({}, { success: false });
    let res: any = null;
    let threw: any = null;
    try { res = await t.call({ symbol: '600919' }); } catch (e: any) { threw = e; }
    // 兼容两种形态：BaseTool.call 可能返回失败响应，也可能抛出
    expect(threw !== null || res?.success === false).toBe(true);
    const blob = JSON.stringify(threw?.message ?? res ?? '');
    expect(blob).toContain('禁止据此判定');
  });
});
