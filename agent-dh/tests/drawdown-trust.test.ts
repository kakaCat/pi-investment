import { describe, it, expect } from 'vitest';
import { recomputeMaxDrawdown, assessDrawdownTrust } from '../packages/trading/src/tools/M4CircuitBreakerTool/drawdownTrust';

// 熔断输入可信度闸门的回归测试（2026-09-11，w-f4aa1f6a）
describe('recomputeMaxDrawdown', () => {
  it('峰谷法复算：先涨后跌', () => {
    const r = recomputeMaxDrawdown([100, 120, 90, 100]);
    expect(r!.maxDrawdownPct).toBeCloseTo(-25, 4);
  });
  it('单调上涨无回撤', () => {
    expect(recomputeMaxDrawdown([100, 101, 102])!.maxDrawdownPct).toBe(0);
  });
});

describe('assessDrawdownTrust', () => {
  const flat55 = Array.from({ length: 55 }, (_, i) => 100000 + i * 10); // 55 点、单调上涨

  it('样本不足（<20）→ 不可信', () => {
    const r = assessDrawdownTrust(-9, [100, 99, 98]);
    expect(r.trusted).toBe(false);
    expect(r.reason).toContain('样本');
  });

  it('声明回撤与序列复算不符 → 不可信（这正是 09-10 事故形态）', () => {
    // 序列几乎无回撤，却声明 -10.71%
    const r = assessDrawdownTrust(-10.71, flat55);
    expect(r.trusted).toBe(false);
    expect(r.reason).toContain('无法由净值序列复现');
  });

  it('一致（容差内）→ 可信', () => {
    const navs = Array.from({ length: 55 }, (_, i) => 100 + i);
    navs[40] = 80; // 制造 -20% 回撤
    const claimed = recomputeMaxDrawdown(navs)!.maxDrawdownPct;
    const r = assessDrawdownTrust(claimed, navs);
    expect(r.trusted).toBe(true);
    expect(r.reason).toContain('可由净值序列复现');
  });

  it('空序列 → 不可信', () => {
    expect(assessDrawdownTrust(-9, []).trusted).toBe(false);
  });
});
