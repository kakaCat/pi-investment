import { afterEach, describe, expect, it, vi } from 'vitest';
import { QuantsysV2Client } from '../src/client';

const ok = (data: any) => ({ data: { success: true, data } });

function accountView() {
  return {
    account: 'agent_brain',
    trade_date: '2026-11-03',
    plan_id: 7,
    version: 3,
    revision_status: 'active',
    generated_at: new Date().toISOString(),
    market_gate: { style: 'growth', allowed: true },
    readiness: { ready: true, reasons: [] },
    items: [{
      item_id: 2,
      symbol: '000063',
      name: '中兴通讯',
      action: 'buy',
      horizon: 'swing',
      target_weight: 0.02,
      target_qty: 100,
      execution_batch: 3,
      max_chase_pct: 2.5,
      entry: {
        combinator: 'all_of',
        conditions: [{ type: 'price_break', params: { price: 27.66, direction: 'above' } }],
      },
      exit: [{ role: 'stop_loss', type: 'pct', params: { value: 8 } }],
      state: { state: 'planned' },
    }],
  };
}

function makeClient() {
  return new QuantsysV2Client({ baseURL: 'http://v2.test', timeout: 1000 });
}

afterEach(() => { vi.restoreAllMocks(); });

describe('getCorePlan 当日计划视图', () => {
  it('账户级 items 归一化为 plans，active 且 ready 时可用', async () => {
    const client = makeClient();
    const get = vi.spyOn((client as any).client, 'get').mockResolvedValue(ok(accountView()));

    const result = await client.getCorePlan('agent_brain');

    expect(get).toHaveBeenCalledWith('/api/plans/today?account=agent_brain');
    expect(result.available).toBe(true);
    expect(result.unavailable_reason).toBeNull();
    expect(result.account).toBe('agent_brain');
    expect(result.plan?.plans).toHaveLength(1);
    expect(result.plan?.plans[0]).toMatchObject({
      plan: { id: 7, item_id: 2, status: 'active', version: 3 },
      targets: [{ symbol: '000063', role: 'buy', budget_pct: 2, position: 'planned' }],
      entry: { conditions: [{ type: 'price_break', params: { price: 27.66, direction: 'above' } }] },
      execution_batch: 3,
      max_chase_pct: 2.5,
      exit: { stop_loss: { type: 'pct', value: 8 } },
      env_gate: { allowed: true, verdict: 'allowed' },
    });
  });

  it('已生成但 readiness 未通过时如实报告未就绪', async () => {
    const client = makeClient();
    const body = accountView();
    body.revision_status = 'draft';
    body.readiness = {
      ready: false,
      reasons: [
        { code: 'REVIEW_REQUIRED', message: 'revision 尚未激活', item_id: null },
        { code: 'ENTRY_INCOMPLETE', message: 'buy 计划项必须补全入场条件', item_id: 2 },
      ],
    };
    vi.spyOn((client as any).client, 'get').mockResolvedValue(ok(body));

    const result = await client.getCorePlan('agent_brain');

    expect(result.available).toBe(false);
    expect(result.unavailable_reason).toContain('当日计划已生成但未就绪');
    expect(result.unavailable_reason).toContain('REVIEW_REQUIRED');
    expect(result.unavailable_reason).toContain('ENTRY_INCOMPLETE(item 2)');
    expect(result.unavailable_reason).not.toContain('当日无已生成计划');
    expect(result.plan?.plans).toHaveLength(1);
  });

  it('旧 plans 视图保持可用', async () => {
    const client = makeClient();
    const plan = { plan: { id: 1, status: 'active' }, targets: [] };
    vi.spyOn((client as any).client, 'get').mockResolvedValue(ok({
      generated_at: new Date().toISOString(),
      plans: [plan],
    }));

    const result = await client.getCorePlan('agent_brain');

    expect(result.available).toBe(true);
    expect(result.plan?.plans).toEqual([plan]);
  });

  it('真正空计划仍报告未生成', async () => {
    const client = makeClient();
    vi.spyOn((client as any).client, 'get').mockResolvedValue(ok({
      generated_at: new Date().toISOString(),
      empty: true,
      plans: [],
    }));

    const result = await client.getCorePlan('agent_brain');

    expect(result.available).toBe(false);
    expect(result.unavailable_reason).toContain('当日无已生成计划');
  });
});
