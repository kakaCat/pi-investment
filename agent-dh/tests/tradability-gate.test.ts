/**
 * 可交易性闸门契约测试（P1/RFC 015 §4.6，w-f436d4ea）
 *
 * 重点锁死**方向差异化**语义——这是最容易被"一律 fail-closed"写错的地方：
 *   BUY  fail-closed（状态未知/停牌/涨停/冲突 → 拒单）
 *   SELL 仅确证停牌拒单；状态未知/涨停/冲突 **不阻塞**（不得阻断减仓与止损）
 */
import { describe, it, expect } from 'vitest';
import { checkTradabilityGate } from '../packages/trading/src/utils/tradability.js';

const stub = (payload: any) => ({ getTradingStatus: async () => payload } as any);
const ok = (data: any) => stub({ success: true, data });

const NORMAL = { symbol: '600150', tradeable: true, is_st: false, is_suspended: false, limit_up: false, limit_down: false, limit_ratio: 0.10, reason: '正常交易（限幅 10%）；可交易', as_of: '2026-09-11T14:00:00' };

describe('可交易性闸门（方向差异化）', () => {
  it('BUY + 正常 → 放行', async () => {
    const r = await checkTradabilityGate(stub({ success: true, data: NORMAL }), '600150', 'BUY');
    expect(r.rejection).toBeNull();
    expect(r.note).toContain('通过');
  });

  it('BUY + 状态未知（后端失败）→ 拒单（fail-closed）', async () => {
    const r = await checkTradabilityGate(stub({ success: false, error: 'down' }), '600150', 'BUY');
    expect(r.rejection).not.toBeNull();
    expect(String(r.rejection.reason)).toContain('fail-closed');
  });

  it('BUY + 状态未知（抛异常）→ 拒单', async () => {
    const bad: any = { getTradingStatus: async () => { throw new Error('boom'); } };
    const r = await checkTradabilityGate(bad, '600150', 'BUY');
    expect(r.rejection).not.toBeNull();
  });

  it('SELL + 状态未知 → **放行**（不得阻断减仓/止损）', async () => {
    const r = await checkTradabilityGate(stub({ success: false, error: 'down' }), '600150', 'SELL');
    expect(r.rejection).toBeNull();
    expect(r.note).toContain('不阻塞');
  });

  it('BUY + 涨停 → 拒单', async () => {
    const r = await checkTradabilityGate(ok({ ...NORMAL, limit_up: true, reason: '涨停' }), '600150', 'BUY');
    expect(r.rejection).not.toBeNull();
    expect(String(r.rejection.reason)).toContain('涨停');
  });

  it('SELL + 涨停 → 放行（涨停可卖出）', async () => {
    const r = await checkTradabilityGate(ok({ ...NORMAL, limit_up: true }), '600150', 'SELL');
    expect(r.rejection).toBeNull();
  });

  it('BUY/SELL + 停牌 → 双方向均拒单', async () => {
    const p = { ...NORMAL, is_suspended: true, tradeable: false, reason: '停牌' };
    expect((await checkTradabilityGate(ok(p), '600150', 'BUY')).rejection).not.toBeNull();
    expect((await checkTradabilityGate(ok(p), '600150', 'SELL')).rejection).not.toBeNull();
  });

  it('BUY + 跨源冲突 → 拒单；SELL + 冲突 → 放行', async () => {
    const p = { ...NORMAL, cross_source_conflict: { field: 'is_suspended', base: false, quote: true } };
    expect((await checkTradabilityGate(ok(p), '000004', 'BUY')).rejection).not.toBeNull();
    expect((await checkTradabilityGate(ok(p), '000004', 'SELL')).rejection).toBeNull();
  });

  it('BUY + tradeable=false（非停牌原因）→ 拒单', async () => {
    const r = await checkTradabilityGate(ok({ ...NORMAL, tradeable: false, reason: '异常' }), '600150', 'BUY');
    expect(r.rejection).not.toBeNull();
  });

  it('缺 tradeable 字段 → 视为状态未知（BUY 拒单）', async () => {
    const r = await checkTradabilityGate(ok({ symbol: '600150' }), '600150', 'BUY');
    expect(r.rejection).not.toBeNull();
  });
});
