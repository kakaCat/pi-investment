---
requirement_refs: [FR-1, FR-2, FR-8]
---

# 接口设计（REQ-260925110957-552d）

> 工具签名、端口契约、错误码。

## 工具接口变更 <!-- serves: FR-1, FR-8, FR-10 -->

**精简说明（FR-10 范围调整）**：
- 删除 `reqboard_task_execute`：与 `reqboard_task_run` 完全等价的别名，无需保留
- 删除 `reqboard_confirm_receipt`：功能并入 `reqboard_ask_confirm` 的 ticket 查询模式
- `reqboard_create` 内部化：作为 `reqboard_capture` 的降级路径，不暴露为独立工具
- 总计：15 个工具 → 12 个工具



### reqboard_task_run（修改） <!-- serves: FR-1, FR-8 -->

**职责**：推进父卡的自动实施链（投递后台 run，立即返回）。

**签名**：

```typescript
defineTool({
  name: 'reqboard_task_run',
  description: '推进任务的自动实施链（父卡开工/子卡执行/收尾/rollup）。投递后立即返回；链在后台跑，完成时收到通知。用 reqboard_run_status 查询进度，用原生 job_output/job_kill 读取/终止。',
  parameters: {
    task_id: { 
      type: 'string', 
      description: '父卡 id（t-xxxxxx）', 
      required: true 
    }
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: true,
      properties: {
        success: { type: 'boolean', required: true },
        dispatched: { 
          type: 'boolean', 
          description: 'true=已投递后台；false=拒绝（见 reason）' 
        },
        job_id: { 
          type: 'string', 
          description: '后台任务 id（reqboard-N），可用于 job_output/job_kill' 
        },
        run_id: { 
          type: 'string', 
          description: '本次运行 uuid，可用于 reqboard_run_status 查询' 
        },
        requirement_id: { type: 'string' },
        task_id: { type: 'string' },
        running: { 
          type: 'array', 
          items: { type: 'string' },
          description: '投递时在跑的子卡（可能为空）' 
        },
        next_ready: { 
          type: 'array', 
          items: { type: 'string' },
          description: '投递时下一批 ready 子卡' 
        },
        reason: { 
          type: 'string', 
          description: '拒绝原因（dispatched=false 时）' 
        }
      }
    },
    render: (args, value) => {
      if (value.dispatched) {
        return [{
          type: 'text',
          text: `✓ 已投递后台：job_id=${value.job_id}, run_id=${value.run_id}\n链在后台跑，完成时会收到通知。用 reqboard_run_status 查询进度。`
        }];
      } else {
        return [{
          type: 'text',
          text: `✗ 投递失败：${value.reason}`
        }];
      }
    }
  },
  timeoutMs: 10_000, // 投递本身很快（< 1s），不需要交互式超时
  async execute(args: { task_id: string }, exec: unknown) {
    // ... 实现见 architecture.md §1
  }
})
```

**返回值详解**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| success | boolean | ✓ | 兼容既有调用方；`dispatched` 更精确 |
| dispatched | boolean | ✓ | true=已投递；false=拒绝 |
| job_id | string | 当 dispatched=true | 原生 job id（`reqboard-N`），可用于 `job_output/job_kill` |
| run_id | string | 当 dispatched=true | 本次 run uuid，可用于 `reqboard_run_status` |
| requirement_id | string | ✓ | 任务所属需求 |
| task_id | string | ✓ | 入参父卡 id |
| running | string[] | 当 dispatched=true | 投递时在跑的子卡（用于诊断） |
| next_ready | string[] | 当 dispatched=true | 投递时下一批 ready 子卡 |
| reason | string | 当 dispatched=false | 拒绝原因（见错误码表） |

**完成后的状态查询**：

由于 `reqboard_task_run` 立即返回（链在后台跑），agent 需要通过以下方式获取最终状态：

1. **完成通知**（原生 dsh-tool-jobs 自动投递）
   ```
   background job reqboard-1 (reqboard: REQ REQ-abc123) finished [status: completed]
   stopped: max_steps_reached (跑了 20 步上限，需续跑)
   ```
   
   通知包含：
   - job 状态（completed / killed / failed）
   - stopped 原因（仅 completed 时有）：rollup / max_steps / paused / noop

2. **job_output 读取**（原生工具，消费性读取）
   ```typescript
   const out = await tools.job_output({ job_id: 'reqboard-1' });
   // out.text 包含链的执行摘要，如：
   // "完成 3 个父卡，stopped: max_steps_reached"
   ```

3. **reqboard_run_status 查询**（本需求新增，非消费性）
   ```typescript
   const status = await tools.reqboard_run_status({ run_id: 'uuid-1' });
   // status.paused_reason === 'max_steps_reached'
   ```

4. **台账直接读取**（通过看板或 reqboard_status）
   ```typescript
   const reqStatus = await tools.reqboard_status({ requirement_id: 'REQ-abc123' });
   // reqStatus.open_requirements[0].advance.pausedReason
   ```

**agent 工作流示例**：

```typescript
// 1. 投递
const r = await tools.reqboard_task_run({ task_id: 't-parent1' });
if (!r.dispatched) {
  console.log('投递失败:', r.reason);
  return;
}

// 2. 继续其他工作（不等链跑完）
// ...

// 3. 收到完成通知（原生机制，自动注入）
// "background job reqboard-1 finished [status: completed]
//  stopped: max_steps_reached"

// 4. 读取详情
const out = await tools.job_output({ job_id: r.job_id });

// 5. 判断是否需要续跑
if (out.text.includes('max_steps')) {
  console.log('链跑了 20 步上限，续跑');
  await tools.reqboard_task_run({ task_id: 't-parent1' }); // 续跑
} else if (out.text.includes('rollup')) {
  console.log('链已完成，需求进验收');
}
```

**错误码**：

| code | reason 文案 | 触发条件 |
|---|---|---|
| REQBOARD_TASK_NOT_FOUND | 任务不存在：t-xxxxx | 台账无该任务 |
| REQBOARD_NOT_PARENT | 任务不是父卡（有 parentId） | 传入子卡 id |
| REQBOARD_NOT_BOUND | 任务不属于本窗口绑定的需求 | 权限校验失败 |
| REQBOARD_ALREADY_RUNNING | 该需求已有 run 在跑（runId=xxx） | 幂等检查：重复投递 |
| REQBOARD_JOBS_UNAVAILABLE | 后台任务系统不可用（ctx.jobs=undefined） | 依赖缺失 |
| REQBOARD_ENGINE_UNAVAILABLE | workflow 引擎不可用 | deps.workflow=undefined |

### reqboard_task_execute（兼容别名） <!-- serves: FR-8 -->

**签名**：与 `reqboard_task_run` 完全相同（参数、返回值、语义）。

**用途**：向后兼容旧调用方。

### reqboard_run_status（新增） <!-- serves: FR-2 -->

**职责**：查询运行态快照（只读，不消费 job 读游标）。

**签名**：

```typescript
defineTool({
  name: 'reqboard_run_status',
  description: '查询运行态快照（只读）：runId / 当前步 / 在跑子卡 / 下一步 / job 状态 / 暂停原因。无在跑 run 时返回终止态与原因。不传参数查本窗口绑定需求。',
  parameters: {
    requirement_id: { 
      type: 'string', 
      description: '需求 id（REQ-xxxxxx）；不传默认本窗口绑定的需求' 
    },
    run_id: { 
      type: 'string', 
      description: '运行 id（uuid）；不传查该需求当前 run' 
    }
  },
  output: {
    schema: {
      type: 'object',
      additionalProperties: true,
      properties: {
        requirement_id: { type: 'string', required: true },
        run_id: { type: 'string' },
        status: { 
          type: 'string', 
          required: true,
          enum: ['running', 'completed', 'paused', 'no_run', 'not_found'],
          description: 'running=在跑 / completed=已完成 / paused=已暂停 / no_run=无运行记录 / not_found=需求不存在'
        },
        current_step: { 
          type: 'integer', 
          description: '当前步号（0-based）' 
        },
        current_subtask: { 
          type: 'string', 
          description: '当前正在执行的子卡 id（t-xxxxxx）' 
        },
        next_ready: { 
          type: 'array', 
          items: { type: 'string' },
          description: '下一批 ready 子卡 id 列表' 
        },
        job_status: { 
          type: 'string', 
          enum: ['running', 'stopping', 'completed', 'killed', 'failed'],
          description: '原生 job 状态（ctx.jobs.get 返回）' 
        },
        job_detail: { 
          type: 'string', 
          description: 'job 状态详情（如 exit code）' 
        },
        paused_reason: { 
          type: 'string', 
          description: '暂停原因（status=paused 时）' 
        },
        heartbeat_at: { 
          type: 'integer', 
          description: '最后心跳时间戳（毫秒）' 
        }
      }
    },
    render: (args, value) => {
      if (value.status === 'not_found') {
        return [{ type: 'text', text: `✗ 需求不存在：${value.requirement_id}` }];
      }
      if (value.status === 'no_run') {
        return [{ type: 'text', text: `需求 ${value.requirement_id} 无运行记录${value.paused_reason ? '（已暂停：' + value.paused_reason + '）' : ''}` }];
      }
      
      const lines = [
        `需求：${value.requirement_id}`,
        `运行：${value.run_id}`,
        `状态：${value.status}${value.job_status ? ' (job: ' + value.job_status + ')' : ''}`,
      ];
      
      if (value.current_step !== undefined) {
        lines.push(`步号：${value.current_step}`);
      }
      if (value.current_subtask) {
        lines.push(`在跑：${value.current_subtask}`);
      }
      if (value.next_ready && value.next_ready.length > 0) {
        lines.push(`下一批：${value.next_ready.join(', ')}`);
      }
      if (value.paused_reason) {
        lines.push(`暂停原因：${value.paused_reason}`);
      }
      
      return [{ type: 'text', text: lines.join('\n') }];
    }
  },
  timeoutMs: 5_000, // 只读查询，很快
  async execute(args: { requirement_id?: string; run_id?: string }, exec: unknown) {
    // ... 实现见 architecture.md §5
  }
})
```

**返回值详解**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| requirement_id | string | ✓ | 查询的需求 id |
| run_id | string | - | 运行 uuid（status=no_run 时为空） |
| status | enum | ✓ | running / completed / paused / no_run / not_found |
| current_step | integer | - | 当前步号（0~19） |
| current_subtask | string | - | 在跑子卡 id（仅 status=running） |
| next_ready | string[] | - | 下一批 ready 子卡 |
| job_status | enum | - | 原生 job 状态（running / completed / killed / failed） |
| job_detail | string | - | job 状态详情 |
| paused_reason | string | - | 暂停原因（status=paused 时） |
| heartbeat_at | integer | - | 心跳时间戳（毫秒） |

## 端口契约 <!-- serves: FR-1 -->

### JobRegistry 端口（原生，只复用不修改） <!-- serves: FR-1 -->

```typescript
// @deepseek-ai/dsh-jobs/lib/types/index.d.ts（已读取）
interface JobRegistry {
  /**
   * 注册并启动后台任务。
   * @returns 同步返回 job id（<kind>-N 格式）
   * @throws 前置校验失败（无 controller / owner 不可达）
   */
  start(spec: JobStart): JobId;
  
  /**
   * 非消费性快照（不改变读游标或通知状态）。
   * @throws 未知 job 或权限不符
   */
  get(id: JobId, caller?: Agent): JobSnapshot;
  
  /**
   * 消费性读取（终态读标记 reported）。
   * @throws 未知 job 或权限不符
   */
  read(id: JobId, caller?: Agent): JobRead;
  
  /**
   * 请求取消。
   * @returns 'requested' / 'already-finished'
   * @throws 未知 job 或权限不符
   */
  kill(id: JobId, caller?: Agent, reason?: string): 'requested' | 'already-finished';
  
  /**
   * 注册完成监听器（effect-scoped）。
   */
  onJobDone(listener: JobDoneListener): () => void;
  
  /**
   * 注册 controller（必需，否则 start 拒绝）。
   */
  attachController(name: string): () => void;
}

interface JobStart {
  kind: JobKind; // 'reqboard'
  label: string; // 模型可见标签
  owner?: Agent; // 归属 agent（访问围栏）
  run(): JobHooks; // 同步返回 hooks
}

interface JobHooks {
  cancel(reason?: string): void; // 同步、幂等、最终 settle done
  done: Promise<JobOutcome>; // 不 reject；终态
  readOutput?(): string; // 可选：流式输出
}

interface JobSnapshot {
  id: JobId;
  kind: JobKind;
  label: string;
  status: 'running' | 'stopping' | 'completed' | 'killed' | 'failed';
  detail?: string;
  startedAt: number;
  finishedAt?: number;
  reported: boolean; // 终态读标记
}
```

**pmboard 使用约定**：

- `kind: 'reqboard'`（需在 `JobKindMap` 声明合并）
- `label: 'REQ <requirementId>'`
- `owner: exec.agent`（归属启动它的窗口）
- `run()` 返回链循环的 hooks（见 architecture.md §1）
- 不实现 `readOutput`（链产出在台账，job 只标记状态）

### UseCaseDeps 新增端口 <!-- serves: FR-1 -->

```typescript
// src/application/ports.ts
export interface UseCaseDeps {
  // ... 既有端口
  
  /**
   * 原生后台任务注册表（新增，FR-1）。
   * 缺省 = 不可用 → advanceRequirement 显式返回 {dispatched:false, reason:'jobs_unavailable'}。
   * 
   * 注意：这是**原生 ctx.jobs**，不是自研系统。组合根注入 `() => ctx.jobs` 的 thunk。
   */
  jobs?: JobRegistry;
}
```

**注入方式**（wiring/index.ts）：

```typescript
// 组合根（伪代码）
export function apply(ctx: Context) {
  const deps: UseCaseDeps = {
    // ... 既有依赖
    jobs: ctx.jobs, // 直接注入原生服务
  };
  
  // 注册工具
  ctx.tools.register(defineAdvanceTool(deps));
  ctx.tools.register(defineRunStatusTool(deps));
  // ...
}
```

## 错误处理 <!-- serves: FR-1, FR-2 -->

### 错误码枚举 <!-- serves: FR-1, FR-8 -->

```typescript
// src/domain/errors.ts（新增或扩展）
export const REQBOARD_ERROR_CODES = {
  // 既有
  TASK_NOT_FOUND: 'REQBOARD_TASK_NOT_FOUND',
  NOT_PARENT: 'REQBOARD_NOT_PARENT',
  NOT_BOUND: 'REQBOARD_NOT_BOUND',
  
  // 新增
  ALREADY_RUNNING: 'REQBOARD_ALREADY_RUNNING',
  JOBS_UNAVAILABLE: 'REQBOARD_JOBS_UNAVAILABLE',
  ENGINE_UNAVAILABLE: 'REQBOARD_ENGINE_UNAVAILABLE',
  RUN_NOT_FOUND: 'REQBOARD_RUN_NOT_FOUND',
} as const;
```

### 工具层错误转换 <!-- serves: FR-8 -->

```typescript
// tools/AdvanceTool/AdvanceTool.ts（伪代码）
async function execute(args: { task_id: string }, exec: unknown) {
  try {
    const result = await advanceRequirement(deps, args.task_id, exec);
    return result;
  } catch (err) {
    // 端口层抛错 → 工具返回结构化失败
    if (err.code === 'REQBOARD_JOBS_UNAVAILABLE') {
      return { 
        success: false, 
        dispatched: false, 
        task_id: args.task_id,
        reason: '后台任务系统不可用（ctx.jobs=undefined）' 
      };
    }
    
    // 未知错误 → 诚实报出
    return { 
      success: false, 
      dispatched: false, 
      task_id: args.task_id,
      reason: (err as Error).message ?? String(err) 
    };
  }
}
```

### 用例层错误语义 <!-- serves: FR-1 -->

```typescript
// use-cases/AdvanceChain.ts（伪代码）
export async function advanceRequirement(
  deps: UseCaseDeps, 
  requirementId: string, 
  exec?: unknown
): Promise<AdvanceResult> {
  // 1. 依赖检查：显式失败（不静默降级）
  if (deps.jobs === undefined) {
    return { 
      dispatched: false, 
      reason: '后台任务系统不可用', 
      code: 'REQBOARD_JOBS_UNAVAILABLE' 
    };
  }
  
  // 2. 幂等检查：重复投递 → 返回既有 run
  const existing = await checkExistingRun(deps, requirementId);
  if (existing !== undefined) {
    return { 
      dispatched: false, 
      reason: `该需求已有 run 在跑（runId=${existing.runId}）`,
      code: 'REQBOARD_ALREADY_RUNNING',
      existing_run_id: existing.runId,
      existing_job_id: existing.jobId
    };
  }
  
  // 3. 投递（catch 前置校验失败）
  let jobId: JobId;
  try {
    jobId = deps.jobs.start({
      kind: 'reqboard',
      label: `REQ ${requirementId}`,
      owner: (exec as {agent?: Agent}).agent,
      run: () => chainLoopHooks(deps, requirementId, runId)
    });
  } catch (err) {
    // ctx.jobs.start 抛错 = 前置校验失败（无 controller / owner 不可达）
    return { 
      dispatched: false, 
      reason: `投递失败：${(err as Error).message}`,
      code: 'REQBOARD_START_FAILED' 
    };
  }
  
  // 4. 成功
  return { 
    dispatched: true, 
    job_id: jobId, 
    run_id: runId,
    requirement_id: requirementId 
  };
}
```

## 向后兼容 <!-- serves: FR-8 -->

### 调用方兼容性 <!-- serves: FR-8 -->

**旧代码**（期望同步返回）：

```typescript
// 旧窗口：期望 stopped ∈ {rollup, paused, noop}
const r = await tools.reqboard_task_run({ task_id: 't-abc123' });
if (r.stopped === 'rollup') {
  console.log('链跑完，进验收');
}
```

**新返回体兼容**：

- 旧代码读 `r.stopped` → undefined（新返回体无该字段）
- 旧代码读 `r.success` → true/false（新返回体保留该字段）
- **不兼容点**：旧代码无法区分「投递成功」与「跑完」

**缓解**：
1. 提示词同步更新（FR-8）：写明「投递 ≠ 完成」
2. 窗口升级后自然切换到新语义（读 `dispatched` 而非 `stopped`）
3. 旧窗口若误判，最多造成过早报告「完成」，不会静默失败（job 仍在跑，完成通知照常投递）

### 数据兼容性 <!-- serves: FR-3 -->

- 台账 schema v7 → v8：只读兼容（见 data-model.md）
- 删除本需求后回滚：新字段被忽略，回到旧行为