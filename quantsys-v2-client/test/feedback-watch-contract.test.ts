import { describe, expect, it, vi } from 'vitest';
import { QuantsysV2Client } from '../src/client';

function clientWithHttp(http: Record<string, any>): QuantsysV2Client {
  const client = new QuantsysV2Client({ baseURL: 'http://localhost:5001' });
  (client as any).client = http;
  return client;
}

describe('feedback watch client contracts', () => {
  it('enable/disable 透传 reason 与 decision_audit_id', async () => {
    const http = {
      patch: vi.fn(async () => ({ data: { success: true, data: { rule: { id: 7 } } } })),
    };
    const client = clientWithHttp(http);
    const audit = { rule_id: 7, reason: '复核后调整', decision_audit_id: 'DEC-test', source_trigger_id: 4786 };

    await client.manageWatchRule({ action: 'enable', ...audit });
    await client.manageWatchRule({ action: 'disable', ...audit });

    const { rule_id: _ruleId, ...expected } = audit;
    expect(http.patch).toHaveBeenNthCalledWith(1, '/api/watch/rules/7', { ...expected, enabled: true });
    expect(http.patch).toHaveBeenNthCalledWith(2, '/api/watch/rules/7', { ...expected, enabled: false });
  });

  it('delete 用 DELETE body 携带审计，而不是丢失理由', async () => {
    const http = {
      delete: vi.fn(async () => ({ data: { success: true, data: { archived: true } } })),
    };
    const client = clientWithHttp(http);

    await client.manageWatchRule({
      action: 'delete', rule_id: 9, reason: '长期无用', decision_audit_id: 'DEC-delete', todo_id: 3,
    });

    expect(http.delete).toHaveBeenCalledWith('/api/watch/rules/9', {
      data: { reason: '长期无用', decision_audit_id: 'DEC-delete', todo_id: 3 },
    });
  });

  it('机会扫描保留自动建规结果并显式传递只读/账户参数', async () => {
    const http = {
      post: vi.fn(async () => ({
        data: {
          success: true, scanned: 2, opportunities: [{ symbol: '600000' }],
          watch_rule_results: [{ symbol: '600000', action: 'skipped' }],
        },
      })),
    };
    const client = clientWithHttp(http);

    const result = await client.scanOpportunitiesDetailed({
      scan_type: 'accumulation', auto_create_rules: true, account_name: 'agent_brain',
      decision_audit_id: 'DA-scan',
    });

    expect(http.post).toHaveBeenCalledWith('/api/signals/scan', {
      scan_type: 'accumulation', auto_create_rules: true, account_name: 'agent_brain',
      decision_audit_id: 'DA-scan',
    });
    expect(result.scanned).toBe(2);
    expect(result.watch_rule_results[0].action).toBe('skipped');
  });

  it('告警映射保留通知资格、去重状态与资金窗口', async () => {
    const http = {
      get: vi.fn(async () => ({ data: { success: true, data: [{
        alert_id: 'alert-1', level: 'high', title: '持续风险', message: '五日累计',
        notify_worthy: false, notification_reason: 'unchanged', dedup_status: 'ok',
        content_fingerprint: 'abc', window: 'trailing_5d_cumulative',
        start: '2026-11-14', end: '2026-11-18', as_of: '2026-11-17', source_rows: 4,
      }] } })),
    };
    const alerts = await clientWithHttp(http).getAlerts({ level: 'all' });
    expect(alerts[0]).toMatchObject({
      id: 'alert-1', notify_worthy: false, notification_reason: 'unchanged',
      dedup_status: 'ok', content_fingerprint: 'abc',
      window: 'trailing_5d_cumulative', start: '2026-11-14',
      end: '2026-11-18', as_of: '2026-11-17', source_rows: 4,
    });
  });
});
