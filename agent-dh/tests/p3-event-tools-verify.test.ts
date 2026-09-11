/**
 * P3 事件工具 LIVE 验收（RFC 015 §3，w-f436d4ea）
 *
 * 覆盖 stock_events（个股事件排雷）与 event_calendar_check(scope) 扩展。
 * 关键语义：**数据源失败必须显式报错，禁止当作"该股无事件"**——排雷场景下
 * "查不到"与"没有"混淆会产生致命的假安全。
 *
 * 运行：cd agent-dh && LIVE=1 npx vitest run tests/p3-event-tools-verify.test.ts
 */
import { describe, it, expect } from 'vitest';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { StockEventsTool } from '../packages/investment/src/tools/StockEventsTool/StockEventsTool.js';
import { EventCalendarTool } from '../packages/investment/src/tools/EventCalendarTool/EventCalendarTool.js';

const LIVE = process.env.LIVE === '1';
const ctx = {} as any;
const client: any = new QuantsysV2Client({
  baseURL: process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001',
  timeout: 40000,
} as any);

describe('契约（无需后端）', () => {
  it('stock_events：非法代码被拒', async () => {
    const tool: any = new StockEventsTool(client);
    const r: any = await tool.call({ symbol: 'XX' } as any);
    expect(r.success).toBe(false);
  });

  it('stock_events：多源失败必须显式报错（不得当"无事件"）', async () => {
    const bad: any = { getSymbolEvents: async () => ({ success: false, error: 'all providers failed' }) };
    const tool: any = new StockEventsTool(bad);
    await expect(tool.execute({ symbol: '600150' }, ctx)).rejects.toThrow(/无事件|失败/);
  });

  it('stock_events：空事件（多源成功但无数据）应正常返回 count=0 并说明非失败', async () => {
    const bad: any = { getSymbolEvents: async () => ({ success: true, data: [] }) };
    const tool: any = new StockEventsTool(bad);
    const r: any = await tool.execute({ symbol: '600150' }, ctx);
    expect(r.count).toBe(0);
    expect(String(r.note)).toContain('非失败');
  });

  it('event_calendar_check：scope 非法被拒', async () => {
    const tool: any = new EventCalendarTool(client);
    const r: any = await tool.call({ scope: 'bogus' } as any);
    expect(r.success).toBe(false);
  });
});

describe.skipIf(!LIVE)('LIVE（真实后端）', () => {
  it('stock_events(600150)：返回真实事件 + upcoming_count', async () => {
    const tool: any = new StockEventsTool(client);
    const r: any = await tool.execute({ symbol: '600150', days: 30 }, ctx);
    console.log('[stock_events 600150]', JSON.stringify({ count: r.count, upcoming: r.upcoming_count, source: r.source, head: (r.events || []).slice(0, 3).map((e: any) => `${e.event_date} ${e.event_type} ${String(e.title).slice(0, 26)}`) }));
    expect(r.count).toBeGreaterThan(0);
    expect(r.source).toBeTruthy();
  }, 60000);

  it('event_calendar_check(scope=individual)：走多源事件流', async () => {
    const tool: any = new EventCalendarTool(client);
    const r: any = await tool.execute({ scope: 'individual' } as any, ctx);
    console.log('[calendar scope=individual]', JSON.stringify({ mode: r.mode, count: r.count, note: String(r.note).slice(0, 90) }));
    expect(r.count).toBeGreaterThan(0);
    expect(String(r.mode)).toContain('individual');
  }, 60000);

  it('event_calendar_check()：不传 scope 时既有行为不变（宏观日历）', async () => {
    const tool: any = new EventCalendarTool(client);
    const r: any = await tool.execute({ mode: 'upcoming', days: 14 } as any, ctx);
    console.log('[calendar default upcoming]', JSON.stringify({ mode: r.mode, count: r.count }));
    expect(r.count).toBeGreaterThan(0);
    expect(String(r.mode)).toContain('upcoming');
  }, 60000);
});
