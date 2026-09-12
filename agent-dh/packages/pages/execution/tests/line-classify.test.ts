/**
 * 业务线分类回归 — 2026-09-12 w-c8cae280（"分类字段没打通导致任务被折叠/丢失"的防复发钉子）
 *
 * 背景：分类原本只存在于 client 的一张硬编码名单里 → ①host 无法复用 ②新任务必落 other 被折叠
 * ③即使 DB 里已有 agent_line（2026-09-02 加列并回填），接口不暴露、代码也不读，字段形同死数据。
 * 本用例锁定三条：**字段优先**（事实优先于名单）、**名单兜底**、**未归类必须显式标记**（供对账暴露，禁止静默）。
 */
import { describe, expect, it } from 'vitest';

import { classifyTask, computeTaskCoverage, isDualLine, lineOfName } from '../src/shared/line-classify';

describe('分类：字段优先 → 名单兜底 → 未归类显式', () => {
  it('任务自带字段优先，且新任务无需改名单即可正确归类', () => {
    expect(classifyTask({ name: 'brand-new-task-2099', agentLine: 'autonomy' }))
      .toEqual({ line: 'autonomy', source: 'field', unclassified: false });
  });

  it('字段与名单冲突时以字段为准（事实优先于历史名单）', () => {
    // pre-market-routine 在名单里是 engine；若任务自报 autonomy，应信字段
    expect(classifyTask({ name: 'pre-market-routine', agentLine: 'autonomy' }).line).toBe('autonomy');
  });

  it('agent_line 落库值映射：profit_engine→engine / autonomy→autonomy', () => {
    expect(classifyTask({ name: 'x-new-task', agentLine: 'profit_engine' }).line).toBe('engine');
    expect(classifyTask({ name: 'y-new-task', agentLine: 'autonomy' }).line).toBe('autonomy');
  });

  it('无字段时回退名单（过渡期），来源标注为 name', () => {
    const c = classifyTask({ name: 'pre-market-routine' });
    expect(c.line).toBe('engine');
    expect(c.source).toBe('name');
    expect(c.unclassified).toBe(false);
    expect(lineOfName('attribution-daily')).toBe('engine');
    expect(lineOfName('evolution-distill-daily')).toBe('autonomy');
    expect(lineOfName('agent-brain-daily-review')).toBe('account');
  });

  it('名单与字段都认不出 → other 且 unclassified=true（供对账显式暴露，禁止静默）', () => {
    const c = classifyTask({ name: 'some-unknown-task-xyz' });
    expect(c.line).toBe('other');
    expect(c.source).toBe('fallback');
    expect(c.unclassified).toBe(true);
  });

  it('已知「其它」前缀不算未归类（board-/geer-/v2_health_check）', () => {
    for (const n of ['board-3341a342-verify', 'geer-take-profit-0901', 'v2_health_check']) {
      expect(classifyTask({ name: n }).unclassified).toBe(false);
    }
  });

  it('isDualLine 只认盈利引擎线 / Autonomy 线', () => {
    expect(isDualLine({ name: 'pre-market-routine' })).toBe(true);
    expect(isDualLine({ name: 'x', agentLine: 'autonomy' })).toBe(true);
    expect(isDualLine({ name: 'agent-brain-daily-review' })).toBe(false);
    expect(isDualLine({ name: 'board-3341a342-verify' })).toBe(false);
  });
});

describe('对账 computeTaskCoverage', () => {
  const tasks = [
    { name: 'pre-market-routine' },
    { name: 'evolution-distill-daily' },
    { name: 'agent-brain-daily-review' },
    { name: 'totally-unknown-task' },
  ];

  it('字段未打通时 fieldMissing=total（页面据此显式说明"需接通 API"）', () => {
    const c = computeTaskCoverage(tasks);
    expect(c.total).toBe(4);
    expect(c.fieldTagged).toBe(0);
    expect(c.fieldMissing).toBe(4);
    expect(c.byLine).toMatchObject({ engine: 1, autonomy: 1, account: 1, other: 1 });
    expect(c.unclassified).toEqual(['totally-unknown-task']);
  });

  it('部分任务带字段时 fieldTagged 计入，未归类清单随之下落', () => {
    const c = computeTaskCoverage([{ name: 'a', agentLine: 'engine' }, { name: 'b' }]);
    expect(c.fieldTagged).toBe(1);
    expect(c.fieldMissing).toBe(1);
    expect(c.byLine.engine).toBe(1);
  });

  it('v2 侧 domain 单独对账（六域与业务线正交，不计入 line 字段）', () => {
    const mixed = [
      { name: '每日数据更新', src: 'v2', domain: 'data' },
      { name: 'session-probe', src: 'v2', domain: null },
      { name: 'pre-market-routine', src: 'os', agentLine: 'profit_engine' },
    ] as any[];
    const c = computeTaskCoverage(mixed);
    expect(c.v2).toBeDefined();
    expect(c.v2!.total).toBe(2);
    expect(c.v2!.domainTagged).toBe(1);
    expect(c.v2!.domainMissing).toBe(1);
    expect(c.v2!.domainByValue).toEqual({ data: 1 });
    expect(c.v2!.missingNames).toEqual(['session-probe']);
    // line 字段只认 OS 侧：v2 任务不因带 domain 而被算成 fieldTagged
    expect(c.fieldTagged).toBe(1);
    expect(c.fieldMissing).toBe(2);
  });

  it('OS 侧 lineTagged 统计库中字段覆盖率（接口暴露后应等于并入数）', () => {
    const c = computeTaskCoverage(
      [
        { name: 'agent-brain-daily-review', src: 'os', agentLine: 'account' },
        { name: 'x', src: 'os', agentLine: null },
      ] as any[],
      { apiTotal: 3, included: 2, excluded: 1, byReason: { no_webhook: 1 } },
    );
    expect(c.os!.lineTagged).toBe(1);
    expect(c.os!.apiTotal).toBe(3);
    expect(c.v2).toBeUndefined();
  });

  it('OS 侧对账（接口总数/并入数/排除原因）原样透传，供页面披露"少了哪些、为什么"', () => {
    const c = computeTaskCoverage(tasks, {
      apiTotal: 27, included: 20, excluded: 7,
      byReason: { disabled: 3, v2_internal: 5, unparsable_time: 1 },
    });
    expect(c.os?.apiTotal).toBe(27);
    expect(c.os?.excluded).toBe(7);
    expect(c.os?.byReason.disabled).toBe(3);
  });
});
