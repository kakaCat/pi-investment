import { describe, expect, it, vi } from 'vitest';
import { MarketAlertTool } from '../src/tools/MarketAlertTool/MarketAlertTool';

describe('market_alert notification semantics', () => {
  it('保留持续告警，并把新事件、未变化与去重异常分别汇总', async () => {
    const client = {
      getAlerts: vi.fn(async () => [
        { id: 'new', level: 'high', notify_worthy: true, notification_reason: 'new_or_changed' },
        { id: 'same', level: 'high', notify_worthy: false, notification_reason: 'unchanged' },
        { id: 'broken', level: 'high', notify_worthy: false,
          notification_reason: 'dedup_error', dedup_status: 'error' },
      ]),
    };
    const tool = new MarketAlertTool(client as any);
    const data = await (tool as any).execute({ level: 'all' }, {});
    expect(data).toHaveLength(3); // 持续风险仍在列表中，不能伪装成风险消失。
    const response = (tool as any).wrap(data, {});
    expect(response.metadata.notification).toEqual({
      notify_worthy: 1, unchanged: 1, dedup_errors: 1, unspecified: 0,
    });
    expect(response.message).toContain('持续未变 1 条');
    expect(response.message).toContain('去重异常 1 条');
  });
});
