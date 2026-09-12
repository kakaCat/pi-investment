/**
 * OS 任务入选判据回归 — 2026-09-12 w-c8cae280
 *
 * 故障现场：「智能执行 → 今日时间轴」少了当天最该出现的例程（盘前 09:25、盘后 18:30、盘中扫描 10:15/13:45）。
 * 根因：入选判据只认 payload.executor === 'dsh-webhook'，而这些任务靠 webhook_url 投递、
 * payload 里根本没有该字段 → 被静默过滤（既不进「调度任务」也不进「时间轴」）。
 * 本用例锁定：判据以 **webhook_url 是否指向 DSH** 为准，同时保留 disabled / 无 webhook / v2 内部 三类排除。
 * 样例字段取自 2026-09-12 对 /api/v1/scheduler/tasks 的真实读取。
 */
import { describe, expect, it } from 'vitest';

import { shouldIncludeOsTask } from '../src/services/data-aggregation';

const DSH = 'http://127.0.0.1:13080/agent-os-trigger';
const V2_INTERNAL = 'http://127.0.0.1:5001/internal/scheduler/webhook';

describe('OS 任务入选判据（shouldIncludeOsTask）', () => {
  it('pre-market-routine：payload 无 executor，但 webhook 指向 DSH → 必须入选（本次修复的回归钉子）', () => {
    expect(shouldIncludeOsTask({
      enabled: true,
      payload: { prompt: '【盘前例程 9:25】…', window: 'w-5b8aac2a' },
      webhook_url: DSH,
    })).toBe(true);
  });

  it('post-market-routine-live / intraday-surge-scan-*：同样形态 → 入选', () => {
    for (const n of ['post-market-routine-live', 'intraday-surge-scan-am', 'intraday-surge-scan-pm']) {
      expect(shouldIncludeOsTask({ enabled: true, payload: { prompt: n }, webhook_url: DSH })).toBe(true);
    }
  });

  it('payload.executor=dsh-webhook（老写法）→ 仍入选（保持兼容）', () => {
    expect(shouldIncludeOsTask({ enabled: true, payload: { executor: 'dsh-webhook' }, webhook_url: DSH })).toBe(true);
  });

  it('webhook 指向 v2 内部（:5001/…）→ 排除，避免与 v2 scheduler 双计', () => {
    expect(shouldIncludeOsTask({ enabled: true, payload: { prompt: 'x' }, webhook_url: V2_INTERNAL })).toBe(false);
    expect(shouldIncludeOsTask({ enabled: true, payload: { executor: 'dsh-webhook' }, webhook_url: V2_INTERNAL })).toBe(false);
  });

  it('无 webhook 且无 executor（如 equity-snapshot-daily）→ 排除（该任务不唤醒 agent）', () => {
    expect(shouldIncludeOsTask({ enabled: true, payload: { prompt: 'x' }, webhook_url: null })).toBe(false);
  });

  it('disabled（无论形态）→ 排除', () => {
    expect(shouldIncludeOsTask({ enabled: false, payload: {}, webhook_url: DSH })).toBe(false);
    expect(shouldIncludeOsTask({ enabled: 'false', payload: {}, webhook_url: DSH })).toBe(false);
  });

  it('enabled 的字符串/数字形态都要认（1 / "true" / "1"）', () => {
    for (const en of [true, 1, 'true', '1'] as unknown[]) {
      expect(shouldIncludeOsTask({ enabled: en, payload: {}, webhook_url: DSH })).toBe(true);
    }
  });
});
