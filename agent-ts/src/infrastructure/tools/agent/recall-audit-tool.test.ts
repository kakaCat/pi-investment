/**
 * 召回审计工具测试（2026-10-05 重写 · REQ-261004202231-bb99）
 *
 * 主题变化：原来打桩 fetch 断言 quantsys-v2 的三个端点；v2 记忆子系统下线后工具改走 agent-os。
 * 这里**不依赖模块 mock**（本仓 ESM mock 不可靠）：
 *   - 纯函数 deriveRecallStats 直接单测（stats 的全部算法）
 *   - feedback 退役 / 未知 action 走的是不触网路径
 */
import { describe, expect, it } from '@jest/globals';
import { recallAuditTool, deriveRecallStats } from './recall-audit-tool.js';

describe('deriveRecallStats（纯函数）', () => {
  it('按 resultsCount 派生 total/injected/suppressed/注入率', () => {
    const stats = deriveRecallStats([
      { resultsCount: 3 },
      { resultsCount: 0 },
      { resultsCount: 1 },
      { resultsCount: 0 },
    ]);

    expect(stats).toEqual({ total: 4, injected: 2, suppressed: 2, injection_rate: 0.5 });
  });

  it('空列表：不除零（注入率 0）', () => {
    expect(deriveRecallStats([])).toEqual({ total: 0, injected: 0, suppressed: 0, injection_rate: 0 });
  });

  it('缺 resultsCount 字段：按抑制算（防御性）', () => {
    const stats = deriveRecallStats([{} as any, { resultsCount: 2 }]);
    expect(stats.total).toBe(2);
    expect(stats.injected).toBe(1);
  });
});

describe('recall_audit（agent-os 版）', () => {
  it('feedback：能力已退役 → 显式报错，不静默成功', async () => {
    const res: any = await recallAuditTool.execute('test-call', {
      action: 'feedback', audit_id: 1, memory_id: 2, feedback: 'relevant',
    });

    expect(res.details.error).toContain('已随 quantsys-v2 记忆子系统下线');
  });

  it('未知 action：明确报错，不静默返回空', async () => {
    const res: any = await recallAuditTool.execute('test-call', { action: 'nope' });

    expect(res.details.error).toContain('unknown action');
  });
});
