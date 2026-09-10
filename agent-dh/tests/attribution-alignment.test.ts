import { describe, it, expect } from 'vitest';
import { alignByTradingDate } from '../packages/risk/src/tools/RiskMetricsTool/attributionAlignment';

// 按交易日对齐的回归测试（2026-09-11，w-f4aa1f6a）
// 关键场景：净值序列缺交易日时，旧的 length-based 对齐会错位一天以上；
// 按日期对齐必须让两侧跨同一段区间，并在基准缺端点时如实降级。
describe('alignByTradingDate', () => {
  const bench = [
    { date: '2026-06-19', trade_date: '2026-06-19', close: 100 },
    { date: '2026-06-22', close: 105 }, // 周一（净值缺这天）
    { date: '2026-06-23', close: 110 },
    { date: '2026-06-24', close: 99 },
  ];

  it('净值缺日：区间收益跨同一段，不错位', () => {
    const nav = ['2026-06-19', '2026-06-23', '2026-06-24'];
    const r = alignByTradingDate(nav, bench, 10);
    expect(r.complete).toBe(true);   // 端点完整
    expect(r.sufficient).toBe(false); // 仅 2 对，样本不足（与 ok 分离，语义不含混）
    expect(r.pairs).toBe(2);
    // 06-19→06-23 = 110/100-1 = 0.10；06-23→06-24 = 99/110-1
    expect(r.benchmarkReturns[0]).toBeCloseTo(0.1, 6);
    expect(r.benchmarkReturns[1]).toBeCloseTo(99 / 110 - 1, 6);
    expect(r.benchmarkReturnPct).toBeCloseTo(-1.0, 6);
  });

  it('基准缺端点：如实降级，不假装可用', () => {
    const nav = ['2026-06-19', '2026-06-23', '2026-06-24'];
    const partial = [bench[0], bench[3]];
    const r = alignByTradingDate(nav, partial, 10);
    expect(r.ok).toBe(false);
    expect(r.complete).toBe(false);   // 端点不完整（与"样本不足"分开断言）
    expect(r.missingDates).toContain('2026-06-23');
    expect(r.note).toContain('基准缺端点');
  });

  it('基准多出交易日不影响配对（只按净值日期对取数）', () => {
    const nav = ['2026-06-23', '2026-06-24'];
    const withExtra = bench.concat([{ date: '2026-06-25', close: 50 }]);
    const r = alignByTradingDate(nav, withExtra, 10);
    expect(r.pairs).toBe(1);
    expect(r.benchmarkReturns).toEqual([99 / 110 - 1]);
  });

  it('端点完整且 >=5 对时 ok=true', () => {
    // 7 个净值交易日 → 6 对，满足 sufficient（>=5）
    const nav = ['2026-06-19', '2026-06-22', '2026-06-23', '2026-06-24',
                 '2026-06-25', '2026-06-26', '2026-06-29'];
    const b2 = bench.concat([
      { date: '2026-06-25', close: 101 }, { date: '2026-06-26', close: 102 },
      { date: '2026-06-29', close: 103 }, { date: '2026-06-30', close: 104 },
    ]);
    const r = alignByTradingDate(nav, b2, 10);
    expect(r.complete).toBe(true);
    expect(r.pairs).toBe(6);
    expect(r.sufficient).toBe(true);
    expect(r.ok).toBe(true);
  });

  it('navPoints 只取尾部窗口', () => {
    const nav = ['2026-06-19', '2026-06-22', '2026-06-23', '2026-06-24'];
    const r = alignByTradingDate(nav, bench, 2);
    expect(r.dates).toEqual(['2026-06-23', '2026-06-24']);
  });
});
