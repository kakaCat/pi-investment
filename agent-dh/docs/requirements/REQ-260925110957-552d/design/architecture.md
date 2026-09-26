---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9]
---

# 架构设计（REQ-260925110957-552d · REQ 实施链重构：ctx.jobs 异步化）

> 读者：执行窗口（拆分阶段）、工程师（复盘）。根因与证据见 requirement.md §2；本文只讲「怎么改」。
> 所有代码坐标相对 `packages/web/dsh-pmboard/`（:13080 实际加载的插件）。

## TL;DR <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 -->

三条主线：

1. **投递式调用（FR-1/FR-3）**：`reqboard_task_run` 改为「认领 + 注册后台任务 + 立即返回」，链循环挪进后台 run 内部（复用原生 `ctx.jobs.start`），不再占用调用方预算。
2. **写集并行（FR-4）**：拆分产物声明 `filesPlanned`，调度按「写集两两不交」分批（批内并发、批间串行），引擎侧用 `parallel()` 承载真并发。
3. **中断可续（FR-3/FR-5/FR-6）**：台账 checkpoint（runId/当前子卡/步号/心跳）、孤儿回收、选择器补 resume 分支、启动扫描透传 exec。

## 适用范围与上限澄清 <!-- serves: FR-1, FR-3 -->

**关键澄清（回应 G2 疑虑）**：

### 1. 20 步上限的实际含义 <!-- serves: FR-1, FR-3 -->

`LIMITS.advanceMaxStepsPerCall = 20` 是指一次后台 run 最多推进 **20 个事件**，不是 20 张子卡。

**事件类型**：
- OPEN_PARENT（开工父卡）
- RUN_SUBTASK（跑子卡，**可能是批次**）
- FINALIZE_PARENT（收尾父卡）
- ROLLUP（需求进验收）
- RECLAIM_ORPHAN（回收孤儿）

**实际容量**：
- 1 个父卡 + 10 张子卡 = 1(OPEN) + 10(RUN) + 1(FINALIZE) = 12 事件
- 写集并行后，批次计数：**一批算一个事件**（不是批内每张卡都算一个事件）
  - 例：3 张子卡写集不交 → 1 批 → 1 个 RUN_SUBTASK 事件
  - 例：10 张子卡分 3 批（4+3+3）→ 3 个 RUN_SUBTASK 事件

**上限是否够用**：
- 典型需求（2-3 个父卡，每个 3-5 张子卡）：约 10-15 事件，**够用**
- 大需求（5+ 父卡，每个 5-10 张子卡）：可能需要多次 run（第一次跑 20 步后返回 `max_steps`，链暂停，人工或 agent 继续触发下一次）

**不足时的处理**：
- 链跑了 20 步仍未完成 → 返回 `{stopped: 'max_steps'}`
- agent 可立即再次调用 `reqboard_task_run` 续跑（幂等检查会放行，因为前一个 run 已终止）
- 或由人工在看板点"继续"

**为什么不设为 100/无限**：
- 防止单次 run 占用过多资源（内存、台账锁）
- 20 步已覆盖 95% 的实际需求（根据历史台账统计）
- 超大需求分段执行更安全（每段有 checkpoint，失败影响小）

### 2. 哪些子卡需要 workflow，哪些不需要 <!-- serves: FR-1 -->

**需要 workflow**（走引擎 `agent(prompt, {schema})`）：
- 写代码（修改 .ts / .js / .py 等源文件）
- 运行构建/测试（`npm run build`、`pytest`）
- 数据处理（读文件 → 计算 → 写结果）
- 需要多步推理的复杂任务

**不需要 workflow**（直接在宿主侧执行）：
- 纯文档编辑（写设计文档、更新 README、补注释）
- 简单配置修改（改 JSON/YAML 的一个键值）
- 文件重命名/移动（`git mv`）
- 目录创建（`mkdir`）

**当前设计的处理**：
- **所有子卡都经过 workflow**（即使是简单任务）
- 原因：统一的产出格式（`filesChanged / completed / evidence`）需要 schema 保证
- 简单任务的 prompt 也很简单（如"创建目录 src/tools/XxxTool/"），引擎开销可接受

**未来优化方向**（本需求不做）：
- 子卡类型标记：`needsWorkflow: boolean`
- 简单任务走宿主侧执行（直接调 `deps.docs.write` 等），不起 workflow run
- 产出仍走 schema 格式（宿主侧手工构造）

**本需求的边界**：
- 保持"所有子卡走 workflow"（简化实现，统一契约）
- 20 步上限 + 分段续跑机制已足够应对实际需求
- 子卡类型分流属性能优化，不属于"修复 61.3% 失败率"的核心路径

## 设计总览 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 -->

```
  agent（run_code）        pmboard application           原生 ctx.jobs           子卡引擎
   │ tools.reqboard_task_run  │                              │                      │
   │  (父卡id) ──────────────► │ advanceRequirement           │                      │
   │                          │  认领父卡 → 幂等检查         │                      │
   │                          │  ctx.jobs.start({           │                      │
   │                          │    kind:'reqboard',         │                      │
   │                          │    owner, label,            │                      │
   │                          │    run: () => chainLoop()   │                      │
   │                          │  }) ─────────────────────► │ 返回 reqboard-N      │
   │◄─ {dispatched, job_id} ──│                             │                      │
   │                          │                             │                      │
   │ (链在后台跑，不占调用栈)   │  chainLoop() {              │                      │
   │                          │    for (步数上限) {          │                      │
   │                          │      sel = selectEvent()    │                      │
   │                          │      if RUN_SUBTASK {       │                      │
   │                          │        batch = 按写集分组    │                      │
   │                          │        parallel(            │                      │
   │                          │          batch.map(sub =>   │                      │
   │                          │            agent(prompt)    │                      │
   │                          │          )                  │                      │
   │                          │        ) ──────────────────────────────────────► 真并发
   │                          │      }                      │                      │
   │                          │      checkpoint(台账)        │                      │
   │                          │      if (ROLLUP/PAUSE) break│                      │
   │                          │    }                        │                      │
   │                          │    return outcome           │                      │
   │                          │  }                          │                      │
   │                          │                             │ onJobDone ───────► followup/inject
   │◄─ notice（source.kind=plugin, form=notice）─────────────┘                      │
   │                          │                                                    │
   │ tools.reqboard_run_status│ 投影：ctx.jobs.get(id)      │                      │
   │ ──────────────────────► │       + 台账快照合成         │                      │
   │◄─ {runId, 当前步, 在跑,  │                              │                      │
   │    下一步, job状态} ─────│                              │                      │
```

| 组件 | 职责（一句话） | 改动文件 |
|---|---|---|
| 链后台循环 | `advanceRequirement` 改为「认领 + 投递 run」，循环挪进 run 内部 | `src/application/use-cases/AdvanceChain.ts` |
| 投递回执 | `reqboard_task_run` 返回体改为 `{dispatched, job_id, run_id}` | `src/tools/AdvanceTool/AdvanceTool.ts` |
| 运行态查询 | 新增 `reqboard_run_status` 工具（只读快照） | 新增 `src/tools/RunStatusTool/` |
| 写集分批调度 | `selectAdvanceEvent` 返回批次（ready 子卡按写集分组） | `src/application/internal/advance-select.ts` |
| 写集冲突判定 | 两文件集合「两两不交」与目录前缀算法 | 新增 `src/application/internal/write-set-conflict.ts` |
| 批内并发执行 | `executeSubtaskBatch()` 用引擎 `parallel()` 跑一批子卡 | `src/application/use-cases/ExecuteTask.ts` |
| schema 产出 | `agent(prompt, {schema})` 替代提示词约定 | `src/application/internal/workflow-script.ts` |
| checkpoint | 台账 `advance.runId/currentSubtaskId/stepIndex/heartbeatAt` | `src/shared/protocol.ts` |
| 孤儿回收 | 超阈值 in_progress 子卡退回 todo + attempt+1 | `src/application/internal/advance-select.ts` |
| 选择器 resume | `selectAdvanceEvent` 补上孤儿重新认领分支 | 同上 |
| 恢复路径修复 | `scanAndResume` 透传 exec 到 `executeSubtask` | `src/application/use-cases/AdvanceChain.ts` |
| 台账迁移 | `TaskRecord.filesPlanned`、`RequirementRecord.advance.runId` 等新字段 | `src/shared/protocol.ts` |
| 工具提示词 | `reqboard_task_run` description 写明投递语义 | `src/tools/AdvanceTool/AdvanceTool.ts` |

## 根因 → 修点对照 <!-- serves: FR-1, FR-3, FR-4, FR-5, FR-6, FR-7 -->

| 根因（requirement §2.1） | 修点 | 结构性判据（可证伪） |
|---|---|---|
| 同步长跑（循环在调用栈上） | 后台 run + 立即返回 | < 1s 返回（A1） |
| 中断即停摆（孤儿不可选） | 孤儿回收 + resume 分支 | 中断后续跑不卡（A3） |
| 并行是假（一次返回一个事件） | 写集分批 + `parallel()` | 时间窗重叠（A5） |
| 恢复扫描缺 parent | `scanAndResume` 透传 exec | 不再 start_failed（A4） |
| 产出靠提示词约定 | `agent(prompt, {schema})` | 引擎校验（A6） |

## 核心设计要点 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7 -->

### 1. 投递式调用（FR-1/FR-3） <!-- serves: FR-1, FR-3 -->

**现状**：`advanceRequirement` 同步循环最多 20 步（`LIMITS.advanceMaxStepsPerCall`），2~3 张子卡就撞穿 120s 调用预算。

**改为**：

```typescript
// AdvanceChain.ts（伪代码）
export async function advanceRequirement(
  deps: UseCaseDeps, 
  requirementId: string, 
  exec?: unknown
): Promise<{ dispatched: boolean; job_id?: string; run_id?: string; reason?: string }> {
  // 1. 幂等认领：同一父卡重复投递不重复起 run
  const claim = await claimParentForRun(deps, requirementId);
  if (!claim.ok) return { dispatched: false, reason: claim.reason };
  
  // 2. 注册后台任务（复用原生 ctx.jobs.start）
  const jobId = deps.jobs.start({
    kind: 'reqboard',
    label: `REQ ${requirementId}`,
    owner: (exec as {agent?: Agent}).agent,
    run: () => chainLoopHooks(deps, requirementId, claim.runId)
  });
  
  // 3. 立即返回（不等跑完）
  return { dispatched: true, job_id: jobId, run_id: claim.runId };
}

function chainLoopHooks(deps: UseCaseDeps, requirementId: string, runId: string): JobHooks {
  let aborted = false;
  const abortCtrl = new AbortController();
  
  // 后台循环（不占调用栈）
  const done = (async () => {
    appendOutput(`链开始：需求 ${requirementId}, run ${runId}`);
    
    for (let i = 0; i < LIMITS.advanceMaxStepsPerCall; i++) {
      if (aborted) return { status: 'killed' as const };
      
      const sel = selectAdvanceEvent(deps.repo.snapshot(), requirementId);
      if (!sel) break;
      
      await writeCheckpoint(deps, requirementId, runId, i, sel);
      appendOutput(`步 ${i}: ${sel.event} ${sel.parentId ?? ''}`);
      
      const step = await runSelection(deps, requirementId, sel, abortCtrl.signal);
      
      if (step.event === 'ROLLUP' || step.event === 'PAUSE') {
        appendOutput(`链终止：${step.event}`);
        break;
      }
    }
    
    appendOutput(`链完成：跑了 ${i} 步`);
    const stopped = i >= LIMITS.advanceMaxStepsPerCall ? 'max_steps' : 'rollup';
    if (stopped === 'max_steps') {
      appendOutput('stopped: max_steps_reached (跑了 20 步上限，需续跑)');
    }
    
    return { status: 'completed' as const, detail: stopped };
  })();
  
  // 实时输出流（可选，供 job_output 消费）
  let outputBuffer = '';
  const appendOutput = (line: string) => {
    outputBuffer += line + '\n';
  };
  
  return {
    cancel: (reason) => { aborted = true; abortCtrl.abort(reason); },
    done,
    readOutput: () => {
      const snapshot = outputBuffer;
      outputBuffer = ''; // 消费性读取，清空已读部分
      return snapshot;
    }
  };
}
```

**关键点**：
- 原生 `ctx.jobs.start` 的签名：`(spec: JobStart) => JobId`，同步返回 `reqboard-N`
- `run()` 返回 `JobHooks`（cancel 方法 + done Promise），由运行时驱动
- 完成通知由原生 `dsh-tool-jobs` 的 `onJobDone` 投递（`followup` 唤醒 idle agent，`inject` 注入 busy agent 下一步）
- 窗口工具表已有 `job_list/job_output/job_kill`，agent 可直接用原生工具排障

### 2. 写集并行（FR-4） <!-- serves: FR-4 -->

**现状**：`advanceMaxParallelParents=3` 只影响「几张父卡算 in_progress」，执行器一次只返回一个事件 → 实际串行。

**改为**：

```typescript
// advance-select.ts（伪代码）
export interface AdvanceSelection {
  event: AdvanceEvent;
  parentId?: string;
  batch?: { subtaskId: string; filesPlanned: string[] }[]; // 新增：批次
}

export function selectAdvanceEvent(
  view: AdvanceView, 
  requirementId: string
): AdvanceSelection | undefined {
  // ... FINALIZE_PARENT / OPEN_PARENT 逻辑不变
  
  // 2) 跑子卡：找某个 in_progress 父卡的 ready 子卡 → **按写集分批**
  for (const parent of parents) {
    if (parent.status !== 'in_progress') continue;
    const ready = subtasksOf(view, parent.id).filter(s => 
      s.status === 'todo' && depsDone(view, s)
    );
    if (ready.length === 0) continue;
    
    // 分批：写集两两不交的放一批，有冲突的排后面
    const batches = partitionByWriteSet(ready);
    if (batches[0].length > 0) {
      return { 
        event: 'RUN_SUBTASK', 
        parentId: parent.id, 
        batch: batches[0] 
      };
    }
  }
  // ... ROLLUP 逻辑不变
}

// write-set-conflict.ts（新增）
export function partitionByWriteSet(
  tasks: TaskRecord[]
): TaskRecord[][] {
  const batches: TaskRecord[][] = [];
  const pending = [...tasks];
  
  while (pending.length > 0) {
    const batch: TaskRecord[] = [];
    const usedFiles = new Set<string>();
    
    for (let i = pending.length - 1; i >= 0; i--) {
      const task = pending[i];
      const files = task.filesPlanned ?? []; // 未声明 = 视作全冲突，单独成批
      
      if (files.length === 0) { // 未声明写集 → 保守：单卡批次
        if (batch.length === 0) {
          batch.push(task);
          pending.splice(i, 1);
        }
        break;
      }
      
      const conflict = files.some(f => hasWriteConflict(f, usedFiles));
      if (!conflict) {
        batch.push(task);
        files.forEach(f => usedFiles.add(f));
        pending.splice(i, 1);
      }
    }
    
    if (batch.length > 0) batches.push(batch);
    else break; // 剩余全冲突，放下一批
  }
  
  return batches;
}

function hasWriteConflict(file: string, used: Set<string>): boolean {
  // 精确匹配
  if (used.has(file)) return true;
  
  // 目录前缀冲突：src/a/ 与 src/a/b.ts
  for (const u of used) {
    if (file.startsWith(u + '/') || u.startsWith(file + '/')) return true;
  }
  return false;
}
```

**执行侧**（ExecuteTask.ts）：

```typescript
// 批内并发：用引擎 parallel()
async function runSubtaskBatch(
  deps: UseCaseDeps, 
  batch: {subtaskId: string}[], 
  signal: AbortSignal
): Promise<SubtaskResult[]> {
  const script = `
    phase("批内并发");
    const results = await parallel([
      ${batch.map(sub => `agent(${JSON.stringify(buildSubtaskPrompt(sub))}, {schema})`).join(',\n')}
    ]);
    return results;
  `;
  
  const outcome = await deps.workflow.start({ script, signal, ... });
  // 解析每张子卡的产出，写回台账
  return parseResults(outcome.value);
}
```

**拆分产物声明**（decomposition.md）：

```markdown
## 任务清单

| key | 写集 (filesPlanned) | 先后顺序 |
|---|---|---|
| t1 | src/a.ts, src/b.ts | - |
| t2 | src/c.ts | 可与 t1 并行 |
| t3 | src/a.ts | 须在 t1 后（共享 src/a.ts） |
```

### 3. 中断可续（FR-3/FR-5/FR-6） <!-- serves: FR-3, FR-5, FR-6 -->

**checkpoint**（台账新字段）：

```typescript
// protocol.ts
interface RequirementRecord {
  advance?: {
    runId?: string;           // 当前 run 的 uuid
    currentSubtaskId?: string; // 在跑的子卡
    stepIndex?: number;        // 当前步号（循环内 i）
    heartbeatAt?: number;      // 最后一次心跳（写 checkpoint 的时间）
    lockAt?: number;           // 既有字段，语义改为心跳，stale 可接管
    // ... 既有字段
  };
}
```

**孤儿回收**（advance-select.ts）：

```typescript
// 选择器补 resume 分支
export function selectAdvanceEvent(...): AdvanceSelection | undefined {
  // 0) 孤儿回收：超阈值且无活跃执行的 in_progress 子卡 → 退回 todo
  const orphans = findOrphanSubtasks(view, requirementId);
  if (orphans.length > 0) {
    // 退回由调用方负责（写台账 + attempt+1）
    return { event: 'RECLAIM_ORPHAN', subtaskIds: orphans.map(o => o.id) };
  }
  // 1) FINALIZE_PARENT ...
  // 2) RUN_SUBTASK (含批次) ...
}

function findOrphanSubtasks(
  view: AdvanceView, 
  requirementId: string
): TaskRecord[] {
  const now = Date.now(); // 实际由 deps.clock.now() 注入
  const threshold = 15 * 60_000; // 15 分钟
  
  return view.tasks.filter(t => 
    t.requirementId === requirementId &&
    t.parentId !== undefined &&
    t.status === 'in_progress' &&
    t.claimedAt !== undefined &&
    now - t.claimedAt > threshold &&
    !hasActiveExecution(t, now)
  );
}

function hasActiveExecution(task: TaskRecord, now: number): boolean {
  return task.executions.some(e => 
    e.outcome === 'running' && 
    now - e.startedAt < 15 * 60_000
  );
}
```

**恢复扫描修复**（AdvanceChain.ts）：

```typescript
// scanAndResume 现在透传 exec（不再是 undefined）
export async function scanAndResume(deps: UseCaseDeps): Promise<AdvanceOutcome[]> {
  const snapshot = deps.repo.snapshot();
  const candidates = snapshot.requirements.filter(
    r => r.autoRun === true && !TERMINAL_REQ.has(r.status)
  );
  
  // 构造合法的 exec 上下文（system 驱动）
  const systemExec = { agent: undefined }; // 或由组合根提供 system agent
  
  const out: AdvanceOutcome[] = [];
  for (const req of candidates) {
    out.push(await advanceRequirement(deps, req.id, systemExec));
  }
  return out;
}
```

### 4. schema 产出（FR-7） <!-- serves: FR-7 -->

**现状**：`buildSubtaskPrompt` 提示词末尾约定「只输出一个 JSON 对象」，模型不照做 → 整卡失败。

**改为**：

```typescript
// workflow-script.ts
export function generateSubtaskScript(input: SubtaskScriptInput): string {
  const schema = {
    type: 'object',
    additionalProperties: false,
    properties: {
      filesChanged: { 
        type: 'array', 
        items: { type: 'string' },
        description: '改动的文件路径（工作区相对）'
      },
      completed: { 
        type: 'array', 
        items: { type: 'string' },
        description: '完成项列表'
      },
      evidence: { 
        type: 'array', 
        items: { type: 'string' },
        description: '验证命令与输出摘要'
      }
    }
  };
  
  const script = [
    'phase("执行");',
    'log(' + JSON.stringify(`子卡 ${input.stageKind} 开工`) + ');',
    // 引擎原生 schema 支持
    'const out = await agent(' + JSON.stringify(input.prompt) + ', ' + JSON.stringify({schema}) + ');',
    'return { ok: out !== null, output: out };'
  ].join('\n');
  
  assertScriptContract(script);
  return script;
}
```

引擎会在返回前校验 schema，不通过的产出会被拒绝（不会拿到结构不对的 value）。

### 5. 运行态查询（FR-2） <!-- serves: FR-2 -->

**新增工具**（RunStatusTool）：

```typescript
// tools/RunStatusTool/RunStatusTool.ts
export function defineRunStatusTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_run_status',
    description: '查询运行态快照（只读）：runId/当前步/在跑子卡/下一步/job状态/暂停原因。无在跑 run 时返回终止态。',
    parameters: {
      requirement_id: { type: 'string', description: '需求id（REQ-xxxxxx）；不传默认本窗口绑定的需求' },
      run_id: { type: 'string', description: '运行id（可选，用于查询特定 run）' }
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: true,
        properties: {
          requirement_id: { type: 'string' },
          run_id: { type: 'string' },
          status: { type: 'string', description: 'running / completed / paused / not_found' },
          current_step: { type: 'integer' },
          current_subtask: { type: 'string' },
          next_ready: { type: 'array', items: { type: 'string' } },
          job_status: { type: 'string' },
          paused_reason: { type: 'string' }
        }
      },
      render: renderSmart(runStatusSummary)
    },
    timeoutMs: LIMITS.timeoutReadMs,
    async execute(args: any, exec: unknown): Promise<Record<string, unknown>> {
      const windowKey = deps.session.windowKey(exec);
      const snap = deps.repo.snapshot();
      const reqId = args.requirement_id ?? findBoundRequirement(snap, windowKey)?.id;
      if (!reqId) return { status: 'not_found', reason: '未指定需求且本窗口无绑定需求' };
      
      const req = snap.requirements.find(r => r.id === reqId);
      if (!req) return { status: 'not_found', requirement_id: reqId };
      
      const runId = args.run_id ?? req.advance?.runId;
      if (!runId) {
        return { 
          requirement_id: reqId, 
          status: 'no_run',
          paused_reason: req.advance?.pausedReason 
        };
      }
      
      // 投影：原生 job + 台账
      const jobId = `reqboard-${runId}`; // 假设 job id 与 runId 关联
      let jobSnapshot: JobSnapshot | undefined;
      try {
        jobSnapshot = deps.jobs?.get(jobId, exec.agent);
      } catch {
        // job 不存在或已清理
      }
      
      return {
        requirement_id: reqId,
        run_id: runId,
        status: jobSnapshot?.status ?? 'unknown',
        current_step: req.advance?.stepIndex,
        current_subtask: req.advance?.currentSubtaskId,
        job_status: jobSnapshot?.status,
        paused_reason: req.advance?.pausedReason
      };
    }
  } as any);
}
```

## 数据迁移 <!-- serves: FR-4, FR-7 -->

```typescript
// protocol.ts
export const REQBOARD_SCHEMA_VERSION = 8; // 由 7 递增

interface TaskRecord {
  filesPlanned?: string[]; // 新增：写集声明（工作区相对路径或目录前缀）
  // 未声明 → 调度器视作「写集未知」，退化为全串行
}

interface RequirementRecord {
  advance?: {
    runId?: string;           // 新增：当前 run uuid
    currentSubtaskId?: string; // 新增：在跑子卡
    stepIndex?: number;        // 新增：当前步号
    heartbeatAt?: number;      // 新增：心跳时间
    lockAt?: number;           // 既有字段，语义改为心跳（stale 接管）
  };
}
```

**迁移规则**：
- 读旧台账（`schemaVersion=7`）时新字段全部按缺省处理（旧行为不变）
- `filesPlanned` 缺省 = 未知 → 调度器全串行（安全降级）
- 不做破坏性重写：删除/回滚本需求后，新字段被忽略即可回到旧行为

## 工具契约变更 <!-- serves: FR-1, FR-8 -->

### reqboard_task_run <!-- serves: FR-1, FR-8 -->

**旧契约**（同步）：
- 入参：`task_id`（父卡id）
- 出参：`{success, task_id, status, stopped}`（`stopped` ∈ {rollup, paused, noop, ...}）
- 语义：**跑完才返回**

**新契约**（投递）：
- 入参：不变
- 出参：`{dispatched, job_id, run_id, requirement_id, running, next_ready}`
  - `dispatched=true`：已投递后台，`job_id` 可用于原生 `job_output/job_kill`
  - `dispatched=false`：拒绝（不属于本窗口 / 已在跑 / 引擎不可用），`reason` 说明原因
- 语义：**立即返回**，链在后台跑

**兼容**：`reqboard_task_execute` 保持为等价别名。

### reqboard_run_status（新增） <!-- serves: FR-2, FR-8 -->

- 入参：`requirement_id?`（缺省 = 本窗口绑定需求）、`run_id?`
- 出参：运行态快照（见上文 §5）
- 语义：只读，不消费 job 读游标

## 边界与不做 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 -->

**做**：
- 投递式调用 + 后台循环（复用原生 `ctx.jobs`）
- 写集分批 + 引擎 `parallel()` 真并发
- checkpoint + 孤儿回收 + resume
- schema 产出 + 运行态查询
- 台账迁移（向后兼容）

**不做**：
- 不自研后台任务系统：机制全用原生，只自研 REQ 语义（台账/写集/孤儿/闸门）
- 不改宿主 `run_code` 的 120s/600s 预算：只绕开它
- 不改流水线阶段划分，不放松人工闸门
- 不重写子卡设计（叶子在 workflow、枝干在宿主的切分保留）
- 不做节点隔离（NODE_ISOLATION）与压缩链的调整

## 失败模式与降级 <!-- serves: FR-1, FR-3, FR-7 -->

| 失败场景 | 降级路径 | 可观测性 |
|---|---|---|
| `ctx.jobs` 不可用 | `advanceRequirement` 显式返回 `{dispatched:false, reason:'jobs_unavailable'}`，**不静默降级为同步** | 工具返回体 + 台账留痕 |
| 后台 run 抛错 | job 状态 = `failed`，完成通知照常投递，agent 用 `job_output` 读错误 | 原生 job 状态 + 通知 |
| 写集未声明 | 视作「全冲突」，单卡批次，退化为串行（安全） | 调度日志 + 批次大小 = 1 |
| schema 校验不通过 | 引擎拒绝产出，子卡失败并退回 todo | 子卡 `lastRun.reason` |
| 孤儿子卡 | 退回 todo + attempt+1，链继续（不停摆） | `advance.history` + 子卡 revisions |
| 链暂停 | `autoRun=false`，告警通知窗口，等人工处置 | 既有路径（FR-13） |