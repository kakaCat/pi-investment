---
req_id: REQ-4842fe
doc: design/interfaces
serves: FR-3, FR-4, FR-5, FR-6, FR-8, FR-13, FR-14, FR-16
status: design
---

# REQ-4842fe 设计 · 接口

## 1. 工具接口  `serves: FR-4, FR-8, FR-13, FR-16`

### 1.1 `reqboard_task_run`（新增）  `serves: FR-4`

**输入**：`{ task_id: string }`（父卡 id）

**输出**：

```
{
  subtask_executed: { id, stageKind, status } | null,
  next_ready:       { id, stageKind } | null,
  chain:            { done: number, total: number },
  blocked:          { subtaskId, reason } | null,
  parent_status:    string
}
```

**行为**：执行"当前 ready 的那一张子卡"（一次独立 workflow run）；父卡为普通卡且无子卡时先懒展开；全部子卡 done 时在本调用内完成父卡收尾；需求全父卡 done 时触发 rollup。

**错误语义**：

| 情况 | 结果 |
|---|---|
| 父卡不存在 / 不属于本窗口绑定需求 | 拒绝（复用既有错误码） |
| 父卡未 in_progress | 提示先开工，未执行任何卡 |
| 链已全部 done（重入） | 幂等返回 `chain.done === chain.total` |
| 存在失败未仲裁的子卡 | 返回 `blocked`，不执行任何卡 |
| `autoRun=false` | 返回 `blocked.reason=已暂停`（需人工继续） |

### 1.2 `reqboard_task_move`（行为变更）  `serves: FR-3, FR-5`

- 普通卡 `to=in_progress`：**同事务懒展开**子卡链并按映射表/显式 stages 落库（幂等：已有子卡则跳过），写留痕评论；
- 子卡转移收紧：`in_progress → integrating/testing/in_review` 一律拒绝（子卡四态）；
- 人工门新增：`done → in_progress`（重开）、`done → canceled`；agent 身份调用被拒；
- 同需求 in_progress 父卡数超上限 → 拒绝（错误码见 §5）。

### 1.3 `reqboard_ask_confirm(target=plan)`（行为变更）  `serves: FR-16`

- 批准 = 同时批准拆分：**自动 decompose + 置 `autoRun=true` + 触发首个推进事件**，`decomposing → implementing` 随之放行（原「确认拆分清单」门并入本门）；
- 弹框文案必须含："批准后将自动拆分任务卡并立即开跑，中途不再打断；如需干预可在看板暂停或取消"；
- 未批准 → 不产生任何任务卡、不触发事件（门禁不变）。

### 1.4 `reqboard_decompose`（行为变更）  `serves: FR-1b, FR-10`

- 冲突拦截：互无依赖父卡的 `implementation` 文件路径集合有交集 → 拒绝，消息列出冲突文件；
- 透传显式 `stages`（每卡可选）→ 落库时作为该卡子卡集合；非法枚举/空/重复 → 拒绝；
- 不再要求人工二次确认（由 1.3 承担）。

## 2. 端口接口（application/ports.ts）  `serves: FR-4, FR-6`

```ts
export interface WorkflowRunOutcome {
  ok: boolean
  value?: unknown          // realm 物化后的 lossless JSON
  reason?: string          // stopReason：error / cancelled / 引擎缺失 ...
}

export interface WorkflowRunner {
  start(input: {
    script: string
    meta: { name: string; description: string; phases?: string[] }
    args?: Record<string, unknown>
    signal?: AbortSignal
  }): Promise<WorkflowRunOutcome>
}
```

**实现（唯一）**：`adapters/WorkflowEngineRunner.ts` 封装 `ctx.workflowEngine.start`，`await run.result` 后 `finally dispose()`；把 `stopReason !== completed` 翻译为 `ok:false`。

## 3. 域内纯函数接口  `serves: FR-1, FR-1b, FR-5, FR-14`

```ts
// domain/task/SubtaskTemplate.ts（新增，零 I/O）
type StageKind = "dev"|"integrate"|"review"|"test"|"repro"|"fix"|"regress"|"probe"
               | "collect"|"analyze"|"prepare"|"run"|"verify"|"change"|"dryrun"|"apply"

stagesForCardType(type: string): readonly StageKind[]      // 未映射 → ["dev","review"]
validateExplicitStages(stages: readonly string[]): { ok: true; value: StageKind[] } | { ok: false; error: string }
buildSubtaskSpecs(parent: TaskRecord, stages: readonly StageKind[]): SubtaskSpec[]  // 含依赖链与 acceptance 模板

// domain/task/TaskStatus.ts（改）
assertTaskTransition(from, to, actor, role: "parent"|"subtask"|"legacy"): void

// domain/requirement/RequirementStatus.ts（改）
// 新增转移 implementing → design，并列入 HUMAN_ONLY_REQ_TRANSITIONS
```

## 4. 事件与日志接口  `serves: FR-11, FR-12`

```ts
type AdvanceEvent = "OPEN_PARENT" | "RUN_SUBTASK" | "FINALIZE_PARENT" | "ROLLUP" | "PAUSE"

interface AdvanceRecord {
  at: number
  requirementId: string
  event: AdvanceEvent
  parentId?: string
  subtaskId?: string
  outcome: "ok" | "failed" | "skipped" | "noop"
  durationMs: number
  detail: string
}
```

字段口径与看板渲染见 `design/observability.md`。

## 5. 错误码  `serves: FR-9, FR-13`

| 错误码 | 触发 | 消息要点 |
|---|---|---|
| `REQBOARD_PARENT_LIMIT` | 同需求 in_progress 父卡超上限 | 当前上限值 + 已在跑的卡清单 |
| `REQBOARD_STAGES_INVALID` | 显式 stages 非法（枚举/空/重复） | 指出非法项 |
| `REQBOARD_FILE_CONFLICT` | 拆分期改动面重叠 | 列出冲突文件与涉及卡 |
| `REQBOARD_NOT_IN_PROGRESS` | task_run 作用于未开工父卡 | 提示先开工 |
| `REQBOARD_CHAIN_PAUSED` | autoRun=false 时触发事件 | 提示处置入口 |
| `REQBOARD_SUBTASK_GATE` | 子卡凭证门不过 | 指出不过的项（report/文件/stopReason） |
| `REQBOARD_HUMAN_GATE`（复用） | 人工资格动作（重开/取消/回退上游）由 agent 调用 | 明确该动作需人 |

## 6. 数据接口  `serves: FR-2, FR-15`

台账字段（`parentId` / `stageKind` / `attempt` / `revisions` / `autoRun`）与不变量（INV-1~7）见 `design/data-model.md`；本节的工具与端口接口只读写这些字段，不引入新存储。
