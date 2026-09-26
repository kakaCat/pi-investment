---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9]
---

# 测试用例设计（REQ-260925110957-552d）

> 单测、集成测试、回归验证。

## 单测（纯函数，无 I/O） <!-- serves: FR-4, FR-5 -->

### 写集冲突判定 <!-- serves: FR-4 -->

**文件**：`tests/write-set-conflict.test.ts`

```typescript
import { describe, it, expect } from 'vitest';
import { hasWriteConflict, partitionByWriteSet } from '../src/application/internal/write-set-conflict';

describe('hasWriteConflict', () => {
  it('精确匹配冲突', () => {
    const used = new Set(['src/a.ts']);
    expect(hasWriteConflict('src/a.ts', used)).toBe(true);
  });
  
  it('目录前缀冲突', () => {
    const used = new Set(['src/tools/']);
    expect(hasWriteConflict('src/tools/AdvanceTool/AdvanceTool.ts', used)).toBe(true);
    expect(hasWriteConflict('src/tools/StatusTool/index.ts', used)).toBe(true);
  });
  
  it('反向前缀冲突', () => {
    const used = new Set(['src/tools/AdvanceTool/AdvanceTool.ts']);
    expect(hasWriteConflict('src/tools/', used)).toBe(true);
  });
  
  it('不同文件不冲突', () => {
    const used = new Set(['src/a.ts']);
    expect(hasWriteConflict('src/b.ts', used)).toBe(false);
  });
  
  it('不同目录不冲突', () => {
    const used = new Set(['src/tools/']);
    expect(hasWriteConflict('src/application/', used)).toBe(false);
  });
});

describe('partitionByWriteSet', () => {
  it('无冲突 → 全部在第一批', () => {
    const tasks = [
      makeTask({ id: 't1', filesPlanned: ['src/a.ts'] }),
      makeTask({ id: 't2', filesPlanned: ['src/b.ts'] }),
      makeTask({ id: 't3', filesPlanned: ['src/c.ts'] }),
    ];
    
    const batches = partitionByWriteSet(tasks);
    expect(batches).toHaveLength(1);
    expect(batches[0]).toHaveLength(3);
    expect(batches[0].map(t => t.id)).toEqual(['t1', 't2', 't3']);
  });
  
  it('有冲突 → 分批', () => {
    const tasks = [
      makeTask({ id: 't1', filesPlanned: ['src/a.ts'] }),
      makeTask({ id: 't2', filesPlanned: ['src/a.ts'] }), // 与 t1 冲突
      makeTask({ id: 't3', filesPlanned: ['src/b.ts'] }),
    ];
    
    const batches = partitionByWriteSet(tasks);
    expect(batches).toHaveLength(2);
    expect(batches[0].map(t => t.id)).toEqual(['t1', 't3']); // t1 t3 并行
    expect(batches[1].map(t => t.id)).toEqual(['t2']); // t2 第二批
  });
  
  it('目录前缀冲突', () => {
    const tasks = [
      makeTask({ id: 't1', filesPlanned: ['src/tools/'] }),
      makeTask({ id: 't2', filesPlanned: ['src/tools/AdvanceTool/AdvanceTool.ts'] }), // 冲突
      makeTask({ id: 't3', filesPlanned: ['src/application/'] }), // 不冲突
    ];
    
    const batches = partitionByWriteSet(tasks);
    expect(batches[0].map(t => t.id)).toContain('t1');
    expect(batches[0].map(t => t.id)).toContain('t3');
    expect(batches[1].map(t => t.id)).toEqual(['t2']);
  });
  
  it('未声明写集 → 单独成批', () => {
    const tasks = [
      makeTask({ id: 't1', filesPlanned: ['src/a.ts'] }),
      makeTask({ id: 't2', filesPlanned: undefined }), // 未声明
      makeTask({ id: 't3', filesPlanned: ['src/b.ts'] }),
    ];
    
    const batches = partitionByWriteSet(tasks);
    // t2 单独成批（保守：视作与所有卡冲突）
    expect(batches.some(b => b.length === 1 && b[0].id === 't2')).toBe(true);
  });
  
  it('空写集 → 单独成批', () => {
    const tasks = [
      makeTask({ id: 't1', filesPlanned: ['src/a.ts'] }),
      makeTask({ id: 't2', filesPlanned: [] }), // 空数组
      makeTask({ id: 't3', filesPlanned: ['src/b.ts'] }),
    ];
    
    const batches = partitionByWriteSet(tasks);
    expect(batches.some(b => b.length === 1 && b[0].id === 't2')).toBe(true);
  });
});
```

### 孤儿回收 <!-- serves: FR-5 -->

**文件**：`tests/orphan-reclaim.test.ts`

```typescript
import { describe, it, expect } from 'vitest';
import { findOrphanSubtasks, selectAdvanceEvent } from '../src/application/internal/advance-select';

describe('findOrphanSubtasks', () => {
  it('正常子卡不是孤儿', () => {
    const now = Date.now();
    const tasks = [
      makeSubtask({ 
        id: 't1', 
        status: 'in_progress', 
        claimedAt: now - 5 * 60_000, // 5 分钟前
        executions: [{ startedAt: now - 5 * 60_000, outcome: 'running' }]
      })
    ];
    
    const orphans = findOrphanSubtasks({ tasks }, 'req1', now);
    expect(orphans).toHaveLength(0);
  });
  
  it('超阈值且无活跃执行 → 孤儿', () => {
    const now = Date.now();
    const tasks = [
      makeSubtask({ 
        id: 't1', 
        status: 'in_progress', 
        claimedAt: now - 20 * 60_000, // 20 分钟前，超阈值
        executions: [{ startedAt: now - 20 * 60_000, endedAt: now - 19 * 60_000, outcome: 'failed' }]
      })
    ];
    
    const orphans = findOrphanSubtasks({ tasks }, 'req1', now);
    expect(orphans).toHaveLength(1);
    expect(orphans[0].id).toBe('t1');
  });
  
  it('超阈值但有活跃执行 → 不是孤儿', () => {
    const now = Date.now();
    const tasks = [
      makeSubtask({ 
        id: 't1', 
        status: 'in_progress', 
        claimedAt: now - 20 * 60_000,
        executions: [
          { startedAt: now - 20 * 60_000, endedAt: now - 19 * 60_000, outcome: 'failed' },
          { startedAt: now - 5 * 60_000, outcome: 'running' } // 最近一次仍在跑
        ]
      })
    ];
    
    const orphans = findOrphanSubtasks({ tasks }, 'req1', now);
    expect(orphans).toHaveLength(0);
  });
  
  it('done/canceled 不算孤儿', () => {
    const now = Date.now();
    const tasks = [
      makeSubtask({ id: 't1', status: 'done', claimedAt: now - 20 * 60_000 }),
      makeSubtask({ id: 't2', status: 'canceled', claimedAt: now - 20 * 60_000 }),
    ];
    
    const orphans = findOrphanSubtasks({ tasks }, 'req1', now);
    expect(orphans).toHaveLength(0);
  });
});

describe('selectAdvanceEvent - RECLAIM_ORPHAN', () => {
  it('有孤儿 → 优先回收', () => {
    const now = Date.now();
    const view = {
      tasks: [
        makeParent({ id: 'p1', requirementId: 'req1', status: 'in_progress' }),
        makeSubtask({ 
          id: 's1', 
          parentId: 'p1', 
          requirementId: 'req1',
          status: 'in_progress', 
          claimedAt: now - 20 * 60_000,
          executions: []
        }),
        makeSubtask({ id: 's2', parentId: 'p1', requirementId: 'req1', status: 'todo' })
      ]
    };
    
    const sel = selectAdvanceEvent(view, 'req1', 3, now);
    expect(sel?.event).toBe('RECLAIM_ORPHAN');
    expect(sel?.subtaskIds).toEqual(['s1']);
  });
});
```

### 选择器 resume 分支 <!-- serves: FR-5 -->

**文件**：`tests/advance-select.test.ts`（扩展既有测试）

```typescript
describe('selectAdvanceEvent - 批次', () => {
  it('返回第一批 ready 子卡', () => {
    const view = {
      tasks: [
        makeParent({ id: 'p1', requirementId: 'req1', status: 'in_progress' }),
        makeSubtask({ id: 's1', parentId: 'p1', status: 'todo', filesPlanned: ['src/a.ts'] }),
        makeSubtask({ id: 's2', parentId: 'p1', status: 'todo', filesPlanned: ['src/b.ts'] }),
      ]
    };
    
    const sel = selectAdvanceEvent(view, 'req1', 3);
    expect(sel?.event).toBe('RUN_SUBTASK');
    expect(sel?.batch).toHaveLength(2);
    expect(sel?.batch?.map(s => s.id)).toEqual(['s1', 's2']);
  });
  
  it('写集冲突 → 只返回第一批', () => {
    const view = {
      tasks: [
        makeParent({ id: 'p1', requirementId: 'req1', status: 'in_progress' }),
        makeSubtask({ id: 's1', parentId: 'p1', status: 'todo', filesPlanned: ['src/a.ts'] }),
        makeSubtask({ id: 's2', parentId: 'p1', status: 'todo', filesPlanned: ['src/a.ts'] }),
        makeSubtask({ id: 's3', parentId: 'p1', status: 'todo', filesPlanned: ['src/b.ts'] }),
      ]
    };
    
    const sel = selectAdvanceEvent(view, 'req1', 3);
    expect(sel?.batch).toHaveLength(2); // s1 与 s3 并行
    expect(sel?.batch?.map(s => s.id).sort()).toEqual(['s1', 's3']);
  });
});
```

## 集成测试（含引擎替身） <!-- serves: FR-1, FR-3, FR-7 -->

### 投递回执（< 1s 返回） <!-- serves: FR-1 -->

**文件**：`tests/integration/dispatch.test.ts`

```typescript
import { describe, it, expect, vi } from 'vitest';

describe('advanceRequirement - 投递', () => {
  it('A1: 投递回执 < 1s', async () => {
    const mockJobs = makeMockJobRegistry();
    const deps = makeDeps({ jobs: mockJobs });
    
    const start = Date.now();
    const result = await advanceRequirement(deps, 'req1', mockExec);
    const elapsed = Date.now() - start;
    
    expect(elapsed).toBeLessThan(1000);
    expect(result.dispatched).toBe(true);
    expect(result.job_id).toMatch(/^reqboard-\d+$/);
    expect(result.run_id).toMatch(/^[0-9a-f-]{36}$/);
  });
  
  it('幂等：重复投递拒绝', async () => {
    const mockJobs = makeMockJobRegistry();
    const deps = makeDeps({ jobs: mockJobs });
    
    const r1 = await advanceRequirement(deps, 'req1', mockExec);
    expect(r1.dispatched).toBe(true);
    
    const r2 = await advanceRequirement(deps, 'req1', mockExec);
    expect(r2.dispatched).toBe(false);
    expect(r2.reason).toContain('已有 run 在跑');
    expect(r2.existing_run_id).toBe(r1.run_id);
  });
  
  it('jobs 不可用 → 显式失败', async () => {
    const deps = makeDeps({ jobs: undefined });
    
    const result = await advanceRequirement(deps, 'req1', mockExec);
    expect(result.dispatched).toBe(false);
    expect(result.reason).toContain('后台任务系统不可用');
  });
});
```

### 完成通知 <!-- serves: FR-3 -->

**文件**：`tests/integration/completion-notice.test.ts`

```typescript
describe('链完成通知', () => {
  it('A2: 跑完后收到通知', async () => {
    const mockJobs = makeMockJobRegistry();
    const notified: any[] = [];
    
    mockJobs.onJobDone((snapshot, owner) => {
      notified.push({ snapshot, owner });
    });
    
    const deps = makeDeps({ jobs: mockJobs });
    await advanceRequirement(deps, 'req1', mockExec);
    
    // 模拟链跑完
    await mockJobs.settleJob('reqboard-1', { status: 'completed' });
    
    expect(notified).toHaveLength(1);
    expect(notified[0].snapshot.status).toBe('completed');
  });
});
```

### 中断可续 <!-- serves: FR-3, FR-5, FR-6 -->

**文件**：`tests/integration/interruption.test.ts`

```typescript
describe('中断恢复', () => {
  it('A3: abort 后孤儿被回收', async () => {
    const abortCtrl = new AbortController();
    const deps = makeDeps({ signal: abortCtrl.signal });
    
    // 投递
    await advanceRequirement(deps, 'req1', mockExec);
    
    // 模拟中断（子卡跑到一半）
    abortCtrl.abort();
    
    // 等待一段时间（超过孤儿阈值）
    await sleep(16 * 60_000); // 模拟 16 分钟后
    
    // 重新投递
    const r2 = await advanceRequirement(deps, 'req1', mockExec);
    
    // 断言：孤儿被回收，链继续
    const snap = deps.repo.snapshot();
    const orphan = snap.tasks.find(t => t.id === 'orphan-subtask');
    expect(orphan?.status).toBe('todo'); // 已退回
    expect(orphan?.attempt).toBeGreaterThan(0); // attempt+1
  });
  
  it('A4: scanAndResume 不再 start_failed', async () => {
    const deps = makeDeps();
    
    // 构造「有 autoRun 需求」的场景
    await deps.repo.mutate('setup', (ledger) => {
      ledger.requirements.push(makeRequirement({ id: 'req1', autoRun: true, status: 'implementing' }));
      return { requirements: [ledger.requirements[0]] };
    });
    
    // 恢复扫描
    const outcomes = await scanAndResume(deps);
    
    // 断言：不抛 start_failed
    expect(outcomes).toHaveLength(1);
    expect(outcomes[0].steps.every(s => s.detail !== 'start_failed')).toBe(true);
  });
});
```

### 20 步上限与续跑 <!-- serves: FR-1, FR-3 -->

**文件**：`tests/integration/max-steps.test.ts`

```typescript
describe('20 步上限', () => {
  it('跑满 20 步后正常终止', async () => {
    const mockJobs = makeMockJobRegistry();
    const deps = makeDeps({ jobs: mockJobs });
    
    // 构造需要 26 事件的需求（5 父卡，每个 8 子卡分 3 批）
    await setupLargeRequirement(deps, {
      parentCount: 5,
      subtasksPerParent: 8,
      batchesPerParent: 3
    });
    
    // 第一次投递
    const r1 = await advanceRequirement(deps, 'req1', mockExec);
    await mockJobs.waitSettled(r1.job_id);
    
    // 断言：跑了 20 步后停下
    const snap1 = deps.repo.snapshot();
    const req1 = snap1.requirements.find(r => r.id === 'req1')!;
    expect(req1.advance?.stepIndex).toBe(20);
    expect(req1.advance?.pausedReason).toBe('max_steps_reached');
    
    // 断言：前 3 个父卡完成，第 4 个未完成
    const doneParents = snap1.tasks.filter(t => 
      t.requirementId === 'req1' && 
      t.parentId === undefined && 
      t.status === 'done'
    );
    expect(doneParents.length).toBeGreaterThanOrEqual(3);
    expect(doneParents.length).toBeLessThan(5);
  });
  
  it('续跑从断点继续', async () => {
    const mockJobs = makeMockJobRegistry();
    const deps = makeDeps({ jobs: mockJobs });
    
    // 构造需要 26 事件的需求
    await setupLargeRequirement(deps, {
      parentCount: 5,
      subtasksPerParent: 8,
      batchesPerParent: 3
    });
    
    // 第一次投递（跑 20 步）
    const r1 = await advanceRequirement(deps, 'req1', mockExec);
    await mockJobs.waitSettled(r1.job_id);
    
    // 第二次投递（续跑）
    const r2 = await advanceRequirement(deps, 'req1', mockExec);
    expect(r2.dispatched).toBe(true); // 幂等检查放行
    await mockJobs.waitSettled(r2.job_id);
    
    // 断言：全部 5 个父卡完成
    const snap2 = deps.repo.snapshot();
    const doneParents = snap2.tasks.filter(t => 
      t.requirementId === 'req1' && 
      t.parentId === undefined && 
      t.status === 'done'
    );
    expect(doneParents.length).toBe(5);
    
    // 断言：需求进验收
    const req2 = snap2.requirements.find(r => r.id === 'req1')!;
    expect(req2.status).toBe('accepting');
  });
  
  it('批次计数：无冲突 vs 全冲突', async () => {
    const deps = makeDeps();
    
    // 场景 1：10 张子卡全不冲突 → 1 批 → 1 事件
    await setupTasks(deps, {
      parentId: 'p1',
      subtasks: Array.from({ length: 10 }, (_, i) => ({
        id: `s${i}`,
        filesPlanned: [`src/file${i}.ts`] // 全不冲突
      }))
    });
    
    const sel1 = selectAdvanceEvent(deps.repo.snapshot(), 'req1', 3);
    expect(sel1?.event).toBe('RUN_SUBTASK');
    expect(sel1?.batch?.length).toBe(10); // 一批
    
    // 场景 2：10 张子卡全冲突 → 10 批 → 10 事件
    await setupTasks(deps, {
      parentId: 'p2',
      subtasks: Array.from({ length: 10 }, (_, i) => ({
        id: `s${10 + i}`,
        filesPlanned: ['src/shared.ts'] // 全冲突
      }))
    });
    
    const batches = [];
    let snap = deps.repo.snapshot();
    while (true) {
      const sel = selectAdvanceEvent(snap, 'req1', 3);
      if (sel?.event !== 'RUN_SUBTASK' || sel.parentId !== 'p2') break;
      batches.push(sel.batch?.length ?? 0);
      // 模拟完成第一张卡
      snap = { ...snap, tasks: snap.tasks.map(t => 
        t.id === sel.batch?.[0]?.id ? { ...t, status: 'done' } : t
      )};
    }
    
    expect(batches.length).toBe(10); // 10 批
    expect(batches.every(n => n === 1)).toBe(true); // 每批 1 张
  });
});
```

### 批内并行（时间窗重叠） <!-- serves: FR-4 -->

**文件**：`tests/integration/parallel-batch.test.ts`

```typescript
describe('写集并行', () => {
  it('A5: 写集不交 → 时间窗重叠', async () => {
    const mockWorkflow = makeMockWorkflowRunner();
    const timestamps: { id: string; start: number; end: number }[] = [];
    
    mockWorkflow.onSubtaskStart = (id) => {
      timestamps.push({ id, start: Date.now(), end: 0 });
    };
    mockWorkflow.onSubtaskEnd = (id) => {
      const entry = timestamps.find(t => t.id === id);
      if (entry) entry.end = Date.now();
    };
    
    const deps = makeDeps({ workflow: mockWorkflow });
    
    // 两张写集不交的子卡
    await setupTasks(deps, [
      makeSubtask({ id: 's1', filesPlanned: ['src/a.ts'] }),
      makeSubtask({ id: 's2', filesPlanned: ['src/b.ts'] }),
    ]);
    
    await advanceRequirement(deps, 'req1', mockExec);
    await mockWorkflow.waitAllSettled();
    
    // 断言：时间窗重叠
    const s1 = timestamps.find(t => t.id === 's1')!;
    const s2 = timestamps.find(t => t.id === 's2')!;
    const overlap = Math.max(0, Math.min(s1.end, s2.end) - Math.max(s1.start, s2.start));
    expect(overlap).toBeGreaterThan(0);
  });
  
  it('A5: 写集相交 → 不重叠', async () => {
    const mockWorkflow = makeMockWorkflowRunner();
    const timestamps: { id: string; start: number; end: number }[] = [];
    
    mockWorkflow.onSubtaskStart = (id) => {
      timestamps.push({ id, start: Date.now(), end: 0 });
    };
    mockWorkflow.onSubtaskEnd = (id) => {
      const entry = timestamps.find(t => t.id === id);
      if (entry) entry.end = Date.now();
    };
    
    const deps = makeDeps({ workflow: mockWorkflow });
    
    // 两张写集相交的子卡
    await setupTasks(deps, [
      makeSubtask({ id: 's1', filesPlanned: ['src/a.ts'] }),
      makeSubtask({ id: 's2', filesPlanned: ['src/a.ts'] }),
    ]);
    
    await advanceRequirement(deps, 'req1', mockExec);
    await mockWorkflow.waitAllSettled();
    
    // 断言：不重叠（s2.start >= s1.end）
    const s1 = timestamps.find(t => t.id === 's1')!;
    const s2 = timestamps.find(t => t.id === 's2')!;
    expect(s2.start).toBeGreaterThanOrEqual(s1.end);
  });
});
```

### schema 产出 <!-- serves: FR-7 -->

**文件**：`tests/integration/schema-output.test.ts`

```typescript
describe('子卡产出', () => {
  it('A6: schema 校验通过', async () => {
    const mockWorkflow = makeMockWorkflowRunner();
    mockWorkflow.setOutput({
      filesChanged: ['src/a.ts'],
      completed: ['改了 a.ts'],
      evidence: ['ls src/a.ts']
    });
    
    const deps = makeDeps({ workflow: mockWorkflow });
    const result = await executeSubtask(deps, { subtaskId: 's1', windowKey: 'test' });
    
    expect(result.ok).toBe(true);
    expect(result.filesChanged).toEqual(['src/a.ts']);
  });
  
  it('A6: schema 不通过 → 引擎拒绝', async () => {
    const mockWorkflow = makeMockWorkflowRunner();
    mockWorkflow.setOutput({ invalid: 'format' }); // 不符合 schema
    
    const deps = makeDeps({ workflow: mockWorkflow });
    const result = await executeSubtask(deps, { subtaskId: 's1', windowKey: 'test' });
    
    expect(result.ok).toBe(false);
    expect(result.reason).toContain('schema');
  });
});
```

## 回归验证（现场数据） <!-- serves: FR-8 -->

### 工具错误率对比 <!-- serves: FR-1, FR-3 -->

**文件**：`tests/regression/tool-error-rate.test.ts`

```typescript
describe('A8: 工具错误率回归', () => {
  it('reqboard_task_run 失败率 < 10%', async () => {
    // 读取 .dsh-data/sessions 下的 tool/ptc-dispatch 记录
    const logs = await readToolDispatchLogs();
    const calls = logs.filter(l => l.tool === 'reqboard_task_run');
    const errors = calls.filter(l => l.error);
    
    const errorRate = errors.length / calls.length;
    expect(errorRate).toBeLessThan(0.1); // 目标：< 10%（旧 61.3%）
  });
  
  it('tool call aborted 计数归零', async () => {
    const logs = await readToolDispatchLogs();
    const aborted = logs.filter(l => 
      l.tool === 'reqboard_task_run' && 
      l.error?.includes('tool call aborted')
    );
    
    expect(aborted.length).toBe(0); // A8 判据
  });
});
```

## 测试替身设计 <!-- serves: FR-1, FR-3, FR-7 -->

### MockJobRegistry <!-- serves: FR-1 -->

```typescript
// tests/mocks/MockJobRegistry.ts
export class MockJobRegistry implements JobRegistry {
  private jobs = new Map<JobId, JobEntry>();
  private listeners: JobDoneListener[] = [];
  private nextId = 1;
  
  start(spec: JobStart): JobId {
    const id = `${spec.kind}-${this.nextId++}` as JobId;
    const hooks = spec.run();
    
    const entry: JobEntry = {
      id,
      kind: spec.kind,
      label: spec.label,
      owner: spec.owner,
      status: 'running',
      startedAt: Date.now(),
      hooks
    };
    
    this.jobs.set(id, entry);
    
    // 模拟异步完成
    hooks.done.then(outcome => {
      entry.status = outcome.status;
      entry.finishedAt = Date.now();
      this.notifyDone(entry);
    });
    
    return id;
  }
  
  get(id: JobId): JobSnapshot {
    const entry = this.jobs.get(id);
    if (!entry) throw new Error('job not found');
    return this.toSnapshot(entry);
  }
  
  onJobDone(listener: JobDoneListener): () => void {
    this.listeners.push(listener);
    return () => {
      const idx = this.listeners.indexOf(listener);
      if (idx >= 0) this.listeners.splice(idx, 1);
    };
  }
  
  // 测试辅助：手动 settle 一个 job
  async settleJob(id: JobId, outcome: JobOutcome): Promise<void> {
    const entry = this.jobs.get(id);
    if (!entry) throw new Error('job not found');
    
    // 触发 hooks.done
    (entry.hooks as any).resolveWith(outcome);
  }
  
  private notifyDone(entry: JobEntry) {
    const snapshot = this.toSnapshot(entry);
    this.listeners.forEach(l => l(snapshot, entry.owner));
  }
  
  private toSnapshot(entry: JobEntry): JobSnapshot {
    return {
      id: entry.id,
      kind: entry.kind,
      label: entry.label,
      status: entry.status,
      startedAt: entry.startedAt,
      finishedAt: entry.finishedAt,
      reported: false
    };
  }
}
```

### MockWorkflowRunner <!-- serves: FR-1, FR-4 -->

```typescript
// tests/mocks/MockWorkflowRunner.ts
export class MockWorkflowRunner implements WorkflowRunner {
  private outputs = new Map<string, unknown>();
  public onSubtaskStart?: (id: string) => void;
  public onSubtaskEnd?: (id: string) => void;
  
  setOutput(output: unknown) {
    this.outputs.set('default', output);
  }
  
  async start(input: WorkflowStartInput): Promise<WorkflowRunOutcome> {
    const subtaskId = (input.args as any)?.subtaskId ?? 'default';
    
    this.onSubtaskStart?.(subtaskId);
    
    // 模拟异步执行
    await sleep(100);
    
    this.onSubtaskEnd?.(subtaskId);
    
    const output = this.outputs.get(subtaskId) ?? this.outputs.get('default');
    return { ok: true, value: { output } };
  }
  
  async waitAllSettled(): Promise<void> {
    // 等所有 mock 子卡完成
    await sleep(200);
  }
}
```

## 验收命令 <!-- serves: FR-1, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 -->

```bash
# 单测（纯函数）
cd packages/web/dsh-pmboard
npx vitest run tests/write-set-conflict.test.ts
npx vitest run tests/orphan-reclaim.test.ts
npx vitest run tests/advance-select.test.ts

# 集成测试（含替身）
npx vitest run tests/integration/dispatch.test.ts
npx vitest run tests/integration/interruption.test.ts
npx vitest run tests/integration/parallel-batch.test.ts
npx vitest run tests/integration/schema-output.test.ts

# 回归验证（现场数据）
npx vitest run tests/regression/tool-error-rate.test.ts

# 全量
npx vitest run

# 类型检查
npx tsc --noEmit -p tsconfig.json
```

**期望输出**：全绿，0 错误。