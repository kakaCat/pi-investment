/**
 * P1 微观结构验收测试（RFC 015 §4，w-f436d4ea）
 *
 * 覆盖：
 *  1. minute_kline 工具：多源真实数据 + source/attempted_sources/as_of 透出 + 失败语义
 *  2. trading_status 工具：可交易性 fail-closed（状态查不到必须报错，绝不默认可交易）
 *  3. 限幅口径：主板 10% / 创业板·科创 20% / 沪深 ST 5% / **北交所 30%**（2026-09-11 修正）
 *
 * 运行：cd agent-dh && LIVE=1 npx vitest run tests/p1-microstructure-verify.test.ts
 */
import { describe, it, expect } from 'vitest';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { MinuteKlineTool } from '../packages/investment/src/tools/MinuteKlineTool/MinuteKlineTool.js';
import { TradingStatusTool } from '../packages/investment/src/tools/TradingStatusTool/TradingStatusTool.js';

const LIVE = process.env.LIVE === '1';
const ctx = {} as any;
const client: any = new QuantsysV2Client({
  baseURL: process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001',
  timeout: 30000,
} as any);

describe('契约（无需后端）', () => {
  it('minute_kline：非法周期被拒', async () => {
    const tool: any = new MinuteKlineTool(client);
    const r: any = await tool.call({ symbol: '600150', period: '7m' } as any);
    expect(r.success).toBe(false);
    expect(String(JSON.stringify(r.error))).toContain('period');
  });

  it('trading_status：非法代码被拒', async () => {
    const tool: any = new TradingStatusTool(client);
    const r: any = await tool.call({ symbol: 'ABC' } as any);
    expect(r.success).toBe(false);
  });

  it('trading_status：后端失败必须 fail-closed（不得返回可交易）', async () => {
    const bad: any = { getTradingStatus: async () => ({ success: false, error: 'backend down' }) };
    const tool: any = new TradingStatusTool(bad);
    await expect(tool.execute({ symbol: '600150' }, ctx)).rejects.toThrow(/fail-closed|查询失败/);
  });

  it('trading_status：缺 tradeable 字段同样 fail-closed', async () => {
    const bad: any = { getTradingStatus: async () => ({ success: true, data: { symbol: '600150' } }) };
    const tool: any = new TradingStatusTool(bad);
    await expect(tool.execute({ symbol: '600150' }, ctx)).rejects.toThrow(/结构异常|fail-closed/);
  });

  it('minute_kline：全源失败必须显式报错（不得当无成交）', async () => {
    const bad: any = { getMinuteKlines: async () => ({ success: false, error: 'all providers failed', attempted_sources: ['tencent_minute'] }) };
    const tool: any = new MinuteKlineTool(bad);
    await expect(tool.execute({ symbol: '600150' }, ctx)).rejects.toThrow(/失败|无成交/);
  });

  it('minute_kline：空结果必须显式报错', async () => {
    const bad: any = { getMinuteKlines: async () => ({ success: true, data: [], source: 'x' }) };
    const tool: any = new MinuteKlineTool(bad);
    await expect(tool.execute({ symbol: '600150' }, ctx)).rejects.toThrow(/为空/);
  });
});

describe.skipIf(!LIVE)('LIVE（真实后端）', () => {
  it('minute_kline(600150, 5m)：真实分钟线 + 来源/时点透出', async () => {
    const tool: any = new MinuteKlineTool(client);
    const r: any = await tool.execute({ symbol: '600150', period: '5m', limit: 48 }, ctx);
    console.log('[minute_kline]', JSON.stringify({ count: r.count, source: r.source, attempted: r.attempted_sources, as_of: r.as_of, first: r.data?.[0]?.trade_datetime, last: r.data?.at(-1)?.trade_datetime }));
    expect(r.count).toBeGreaterThan(10);
    expect(r.source).toBeTruthy();
    expect(r.as_of).toBeTruthy();
    const bar = r.data[r.data.length - 1];
    expect(bar.high).toBeGreaterThanOrEqual(Math.max(bar.open, bar.close));
    expect(bar.low).toBeLessThanOrEqual(Math.min(bar.open, bar.close));
  }, 60000);

  it('trading_status(600150)：主板限幅 10%', async () => {
    const tool: any = new TradingStatusTool(client);
    const r: any = await tool.execute({ symbol: '600150' }, ctx);
    console.log('[trading_status 600150]', JSON.stringify({ tradeable: r.tradeable, limit_ratio: r.limit_ratio, reason: r.reason }));
    expect(r.limit_ratio).toBeCloseTo(0.10, 5);
    expect(typeof r.tradeable).toBe('boolean');
    expect(r.as_of).toBeTruthy();
  }, 60000);

  it('trading_status(300750)：创业板限幅 20%', async () => {
    const tool: any = new TradingStatusTool(client);
    const r: any = await tool.execute({ symbol: '300750' }, ctx);
    console.log('[trading_status 300750]', JSON.stringify({ limit_ratio: r.limit_ratio }));
    expect(r.limit_ratio).toBeCloseTo(0.20, 5);
  }, 60000);

  it('trading_status(920023)：北交所限幅 30%（2026-09-11 修正点）', async () => {
    const tool: any = new TradingStatusTool(client);
    const r: any = await tool.execute({ symbol: '920023' }, ctx);
    console.log('[trading_status 920023]', JSON.stringify({ limit_ratio: r.limit_ratio, is_st: r.is_st, reason: r.reason }));
    expect(r.limit_ratio).toBeCloseTo(0.30, 5);
  }, 60000);
});
