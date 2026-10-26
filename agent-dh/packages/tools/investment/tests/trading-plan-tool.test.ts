import { describe, it, expect } from 'vitest';
import { TradingPlanTool } from '../src/tools/TradingPlanTool/TradingPlanTool';

/**
 * trading_plan 工具契约（REQ-261021222905-6dff t12 · TC-22）
 * 假 client 记录调用 → 断言 action 到客户端方法的映射、账户缺省、参数透传。
 */
const makeTool = () => {
  const calls: Array<{ method: string; args: any[] }> = [];
  const record = (method: string) => async (...args: any[]) => {
    calls.push({ method, args });
    return { ok: true };
  };
  const qv2: any = {
    plansToday: record('plansToday'),
    listPlans: record('listPlans'),
    getPlan: record('getPlan'),
    createPlan: record('createPlan'),
    patchPlan: record('patchPlan'),
    applyPlan: record('applyPlan'),
    activatePlan: record('activatePlan'),
    pausePlan: record('pausePlan'),
    resumePlan: record('resumePlan'),
    closePlan: record('closePlan'),
    compilePlanPreview: record('compilePlanPreview'),
    planStats: record('planStats'),
    recordPlanReflection: record('recordPlanReflection'),
    listPlanReflections: record('listPlanReflections'),
    blockedSignalStats: record('blockedSignalStats'),
  };
  return { tool: new TradingPlanTool(qv2) as any, calls };
};

describe('trading_plan 工具（投资脑侧）', () => {
  it('today 走 plansToday，账户缺省不写死为空', async () => {
    const { tool, calls } = makeTool();
    const r: any = await tool.call({ action: 'today' });
    expect(r.success).toBe(true);
    expect(calls[0].method).toBe('plansToday');
    expect(typeof calls[0].args[0]).toBe('string');
    expect(calls[0].args[0].length).toBeGreaterThan(0);
  });

  it('patch 透传 expected_version/审计号/actor=agent', async () => {
    const { tool, calls } = makeTool();
    await tool.call({ action: 'patch', plan_id: 42, expected_version: 3,
      spec_patch: { exit: { stop_loss: { type: 'pct', value: 10 } } },
      reason: '放宽止损', decision_audit_id: 'd-1' });
    expect(calls[0].method).toBe('patchPlan');
    expect(calls[0].args[0]).toBe(42);
    expect(calls[0].args[1].expected_version).toBe(3);
    expect(calls[0].args[1].decision_audit_id).toBe('d-1');
    expect(calls[0].args[1].actor).toBe('agent');
  });

  it('缺 plan_id 的动作被校验拦下（不发请求）', async () => {
    const { tool, calls } = makeTool();
    const r: any = await tool.call({ action: 'apply', expected_version: 1 });
    expect(r.success).toBe(false);
    expect(calls.length).toBe(0);
  });

  it('未知 action 被拒', async () => {
    const { tool, calls } = makeTool();
    const r: any = await tool.call({ action: 'explode' });
    expect(r.success).toBe(false);
    expect(calls.length).toBe(0);
  });

  it('reflect 透传五问与 verdict', async () => {
    const { tool, calls } = makeTool();
    await tool.call({ action: 'reflect', plan_id: 7, verdict: 'keep', reason: '维持',
      answers: { q1: 'a', q2: 'b', q3: 'c', q4: 'd', q5: 'e' } });
    expect(calls[0].method).toBe('recordPlanReflection');
    expect(calls[0].args[1].answers.q1).toBe('a');
    expect(calls[0].args[1].verdict).toBe('keep');
  });
});
