/**
 * trading_plan 工具契约（REQ-261021222905-6dff t12 · TC-22，fin-agent 侧）
 * 断言：plan.* 路由在册、PATCH 可派发、工具已注册。
 */
import { V2_COMMAND_LIST, runQuantV2 } from '../../adapters/quant/quant-v2-client';

describe('trading_plan（fin-agent）', () => {
  it('plan.* 路由全部在册', () => {
    for (const cmd of [
      'plan.today', 'plan.list', 'plan.get', 'plan.create', 'plan.patch',
      'plan.apply', 'plan.activate', 'plan.pause', 'plan.resume', 'plan.close',
      'plan.preview', 'plan.stats', 'plan.reflect', 'plan.reflections',
      'plan.blocked_stats',
    ]) {
      expect(V2_COMMAND_LIST).toContain(cmd);
    }
  });

  it('plan.patch 以 PATCH 方法派发', async () => {
    const orig = global.fetch;
    let seen: any;
    global.fetch = (async (url: any, init: any) => {
      seen = { url: String(url), init };
      return new Response(JSON.stringify({ success: true, data: { ok: true } }), {
        status: 200, headers: { 'content-type': 'application/json' },
      });
    }) as any;
    try {
      await runQuantV2('plan.patch', { plan_id: 42, expected_version: 3, decision_audit_id: 'd-1' });
      expect(seen.init.method).toBe('PATCH');
      expect(seen.url).toContain('/api/plans/42');
      expect(JSON.parse(seen.init.body).expected_version).toBe(3);
    } finally {
      global.fetch = orig;
    }
  });
});
