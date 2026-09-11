import { describe, it, expect } from 'vitest';
import { assessBreakerTrigger, recomputeMaxDrawdown } from '../packages/core-tool/src/drawdownTrust';

// 熔断触发规则回归（2026-09-11，agent_brain 假熔断事故固化）
describe('assessBreakerTrigger', () => {
  // 造一个约 -20% 的真实回撤序列；claimed 一律取复算值本身（自洽）
  const navsOk = Array.from({ length: 60 }, (_, i) => 100 + i);
  navsOk[40] = 80;
  const dd = recomputeMaxDrawdown(navsOk)!.maxDrawdownPct; // ≈ -42.86%，勿手写
  // 小回撤序列（未达阈值但可复现）
  const navsSmall = Array.from({ length: 40 }, (_, i) => 100 + i * 0.1);
  navsSmall[30] = navsSmall[29] * 0.995; // ≈ -0.5%
  const ddSmall = recomputeMaxDrawdown(navsSmall)!.maxDrawdownPct;

  it('holdings_proxy 口径 → 一律不触发（事故形态）', () => {
    const r = assessBreakerTrigger(-8.88, 'holdings_proxy', [100, 99.87]);
    expect(r.triggered).toBe(false);
    expect(r.untrusted).toBe(true);
    expect(r.reason).toContain('holdings_proxy');
  });

  it('account_nav 但样本仅 2 点 → 不触发（不可复现/样本不足）', () => {
    const r = assessBreakerTrigger(-8.88, 'account_nav', [100, 99.87]);
    expect(r.triggered).toBe(false);
    expect(r.untrusted).toBe(true);
  });

  it('account_nav + 可复现 + 超阈值 → 触发', () => {
    const r = assessBreakerTrigger(dd, 'account_nav', navsOk);
    expect(r.triggered).toBe(true);
    expect(r.untrusted).toBe(false);
  });

  it('account_nav + 可复现 + 未超阈值 → 不触发但可信', () => {
    const r = assessBreakerTrigger(ddSmall, 'account_nav', navsSmall);
    expect(r.triggered).toBe(false);
    expect(r.untrusted).toBe(false);
  });
});
