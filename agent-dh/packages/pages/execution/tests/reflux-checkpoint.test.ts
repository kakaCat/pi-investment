/**
 * m6_l2_reflux 判定分支回归 — 2026-09-12 w-c8cae280（REQ-9bcd0a WP6②）
 *
 * 背景：该检查点用于发现「回流边断链」——盘前分析没读昨日归因/决策评分时判红。
 * 上线当天是周六（expectDays=1-5 → off_day），**新分支一次都没执行过**；
 * 若分支写错（例如把 attribution_read=false 判成绿），断链会永远发现不了——
 * 这正是本次立项要消灭的盲区。本用例锁定五态语义。
 */
import { describe, expect, it } from 'vitest';

import { DataAggregationService } from '../src/services/data-aggregation';
import { getCheckpointById } from '../src/services/checkpoint-registry';

const CP = getCheckpointById('m6_l2_reflux');
if (!CP) throw new Error('m6_l2_reflux 未注册 —— 检查点被删或改名，本用例应随之失败');

/** 构造一个「时间可控」的聚合服务（now/weekday 是 readonly，测试里显式覆写） */
function svcAt(iso: string): any {
  const svc: any = new DataAggregationService({
    v2BaseURL: 'http://localhost:5001',
    osBaseURL: 'http://localhost:8080',
    genomeDir: '/tmp/nonexistent-genome',
  } as any);
  const d = new Date(iso);
  svc.now = d;
  svc.today = iso.slice(0, 10);
  svc.weekday = d.getDay();
  return svc;
}

/** vs: 预取包；verifyOne(cp, v2Available, tasksResult, runs, vs, genome) */
function check(iso: string, vs: Record<string, unknown>) {
  const svc = svcAt(iso);
  return svc.verifyOne(CP, true, { tasks: [] }, [], vs, {});
}

describe('m6_l2_reflux 回流消费检查点', () => {
  it('attribution_read=true → confirmed（绿），并带出教训覆盖率', () => {
    // 2026-09-14 周一 10:00（expectTime 09:25 + grace 60min = 10:25 前）
    const r = check('2026-09-14T10:00:00', { refluxRead: true, refluxLessonCoverage: 1 });
    expect(r.status).toBe('confirmed');
    expect(r.message).toContain('attribution_read=true');
    expect(r.message).toContain('教训覆盖率 1');
  });

  it('attribution_read=false → failed（红，回流边断链）——这是本检查点存在的理由', () => {
    const r = check('2026-09-14T10:00:00', { refluxRead: false });
    expect(r.status).toBe('failed');
    expect(r.message).toContain('断链');
  });

  it('今日未落库 + 未到 expectTime → pending（不误报）', () => {
    const r = check('2026-09-14T09:00:00', { refluxRead: null });
    expect(r.status).toBe('pending');
  });

  it('今日未落库 + 已过宽限 → late（区分「没做」与「做了但没读」）', () => {
    const r = check('2026-09-14T23:00:00', { refluxRead: null });
    expect(r.status).toBe('late');
  });

  it('非执行日（周六）→ off_day，优先于一切判定', () => {
    const r = check('2026-09-12T10:00:00', { refluxRead: false });
    expect(r.status).toBe('off_day');
  });

  it('v2 不可达时降级为 unknown，不得误报 failed', () => {
    const svc = svcAt('2026-09-14T10:00:00');
    const r = svc.verifyOne(CP, false, { tasks: [] }, [], { refluxRead: false }, {});
    expect(r.status).toBe('unknown');
  });
});
