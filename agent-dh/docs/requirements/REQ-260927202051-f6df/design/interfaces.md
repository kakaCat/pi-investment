# 接口设计（REQ-260927202051-f6df）

> 队列管理器、任务存储端口、台账改造与迁移脚本的函数签名与契约。

## TaskStore 端口（代码级"队列"） `serves: FR-1, FR-2, FR-3`

> 定义在 `src/application/ports.ts`，实现在 `src/repositories/QueueTaskStore.ts`。
> **36 个读方唯一的任务入口**——不得绕过端口直接读 queue.json。

### I-1 TaskStore `serves: FR-1, FR-2, FR-3`

```typescript
interface TaskStore {
  /** 取单个任务（不存在返回 undefined） */
  get(taskId: string): Promise<TaskRecord | undefined>
  /** 取某需求的全部任务（无队列文件 → 空数组，不是错误） */
  listByRequirement(requirementId: string): Promise<readonly TaskRecord[]>
  /** 取某需求的队列文件全量（含 DAG 视图）；无文件 → undefined */
  readQueue(requirementId: string): Promise<QueueFile | undefined>
  /** 在需求维度上变更任务（原子写；返回改动后的任务） */
  mutate(
    requirementId: string,
    fn: (tasks: QueueTask[], ctx: QueueMutateContext) => QueueTask[] | undefined,
  ): Promise<readonly TaskRecord[]>
  /** 批量写入（拆分落库用；幂等：已存在 id 不覆盖） */
  createMany(requirementId: string, tasks: readonly TaskRecord[]): Promise<readonly TaskRecord[]>
  /** 订阅任务变更（供 SSE / 缓存失效） */
  subscribe(fn: (change: TaskChange) => void): () => void
}

interface QueueMutateContext {
  /** 原子写前的钩子：重算派生视图（edges/layers/ready） */
  recompute: () => void
  now: () => number
}

interface TaskChange {
  requirementId: string
  kind: 'task-created' | 'task-updated' | 'task-moved' | 'task-removed'
  tasks: readonly TaskRecord[]
  revision: number
}
```

**错误契约**：

| 情形 | 行为 |
|---|---|
| 需求无 queue.json | `listByRequirement` 返回 `[]`；`readQueue` 返回 `undefined`（不抛错） |
| queue.json 损坏 | 隔离改名 `.corrupt-<ts>` + 告警；返回空并标记需求降级 |
| `mutate` 校验失败 | 抛 `QUEUE_VALIDATION_FAILED`，**文件保持上次有效内容** |
| `mutate` 目标需求无文件 | 抛 `QUEUE_NOT_FOUND`（写操作不隐式建空档） |
| `createMany` 有重复 id | 跳过已存在者（幂等），不覆盖 |
| 写入失败 | 抛错，中止 |

### I-2 QueueRepository（文件层） `serves: FR-1, FR-2, FR-3`

```typescript
interface QueueRepository {
  /** 读取并解析（+ V-1~V-6 校验）；不存在/损坏/校验失败 → undefined */
  load(requirementId: string): Promise<QueueFile | undefined>
  /** 校验后原子写（复用 persistAtomic）；校验失败抛错且不落盘 */
  save(requirementId: string, file: QueueFile): Promise<void>
  /** 队列文件绝对/相对路径 */
  pathOf(requirementId: string): string
}
```

**原子写流程**：`validateQueueFile` → `persistAtomic(path, JSON.stringify(file, null, 2))`
（`persistAtomic` 已由 `adapters/JsonLedgerRepository.ts` 导出：临时文件 → fsync → rename）。

### I-3 topology 纯函数 `serves: FR-1, FR-2, FR-3`

```typescript
/** 拓扑排序得层级；有环抛 Error（message 含 CIRCULAR） */
function computeLayers(tasks: readonly QueueTask[]): QueueLayer[]
/** 由 tasks 的 dependsOn 展开边集 */
function computeEdges(tasks: readonly QueueTask[]): QueueEdge[]
/** 由状态与依赖推导 ready（唯一实现，禁止在写路径另写一份） */
function computeReady(tasks: readonly QueueTask[]): string[]
```

### I-4 validateQueueFile（V-1 ~ V-6） `serves: FR-1, FR-2, FR-3`

```typescript
interface ValidationIssue {
  rule: 'V-1'|'V-2'|'V-3'|'V-4'|'V-5'|'V-6'
  message: string
  path?: string
}
interface ValidationResult { passed: boolean; issues: ValidationIssue[] }

function validateQueueFile(file: QueueFile): ValidationResult   // 不抛错，失败只填 issues
```

**调用时机**（三处，缺一不可）：`QueueRepository.save` 写入前、`QueueRepository.load` 解析后、
`TaskStore.mutate` 重算派生视图后。

---

## 台账改造接口 `serves: FR-6`

### I-5 ReqboardLedger（去 tasks） `serves: FR-6`

```typescript
// Before
interface ReqboardLedger {
  schemaVersion: number; revision: number
  requirements: RequirementRecord[]
  tasks: TaskRecord[]          // ← 移除
  triages: TriageRecord[]
  migrations?: MigrationMark[]
}

// After
interface ReqboardLedger {
  schemaVersion: 9
  revision: number
  requirements: RequirementRecord[]
  triages: TriageRecord[]
  migrations?: MigrationMark[]
}
```

### I-6 JsonLedgerRepository（去 tasks） `serves: FR-6`

```typescript
// Before
isPlausibleLedger(raw): boolean   // 要求 Array.isArray(o.tasks)
mutate(kind, fn: (ledger) => { requirements?, tasks?, triages? }): ...

// After
isPlausibleLedger(raw): boolean   // 不再要求 tasks
mutate(kind, fn: (ledger) => { requirements?, triages? }): ...   // tasks 通道移除
```

**读兼容（硬约束）**：加载到 `schemaVersion < 9` 或存在非空 `tasks` 的文件时，
**拒绝启动**并抛出指向迁移脚本的错误（`LEDGER_REQUIRES_MIGRATION`），不静默丢弃任务。

```typescript
// 错误契约
{ code: 'LEDGER_REQUIRES_MIGRATION',
  message: '台账为 v8（含 tasks），请先运行 scripts/migrate-ledger.ts --apply' }
```

### I-7 LedgerChange（去 tasks） `serves: FR-6`

```typescript
// After：任务变更不再经台账通知，改由 TaskStore.subscribe
interface LedgerChange {
  revision: number
  kind: 'requirement-created' | 'requirement-updated' | 'requirement-moved'
      | 'triage-created' | 'triage-updated' | 'comment-added' | 'ledger-replaced'
  requirements: readonly RequirementRecord[]
  triages: readonly TriageRecord[]
}
```

---

## 迁移脚本接口 `serves: FR-7`

### I-8 migrate-ledger.ts（追加 v8 → v9） `serves: FR-7`

```bash
node --import tsx/esm scripts/migrate-ledger.ts --file <ledger> --dry-run   # 默认：只报告
node --import tsx/esm scripts/migrate-ledger.ts --file <ledger> --apply     # 落盘
node --import tsx/esm scripts/migrate-ledger.ts --file <ledger> --verify    # 断言已一致
node --import tsx/esm scripts/migrate-ledger.ts --file <ledger> --rollback  # 从最近备份还原
```

```typescript
/** v8 → v9 变换（纯函数，内部 structuredClone，不改入参） */
export function migrateV8toV9(
  ledger: any,
  now: number,
  opts: { requirementDirOf: (reqId: string) => string },
): { ledger: any; queues: { requirementId: string; file: QueueFile; path: string }[]; changes: Record<string, Change> }
```

**行为契约**：

| 阶段 | 行为 |
|---|---|
| 备份 | 迁移前把台账复制为 `<ledger>.backup-<ts>`（存在则复用最近一份的路径记录） |
| 分组 | 按 `task.requirementId` 分组；`requirementId` 缺失/指向不存在需求 → 计入 `orphan_tasks` 并在 dry-run 报告，**不迁移**（宁可不迁也不串档） |
| 写队列 | 每组构造 QueueFile（`schemaVersion: 9`），分层求 ready，校验后写入 `<需求目录>/queue.json` |
| 台账 | 删除 `tasks`、`schemaVersion=9`、`migrations` 追加 `{from:8,to:9,at,by:'migrate-ledger.ts'}` |
| 白名单 | 逐路径比对：只允许 `schemaVersion` / `migrations` / `tasks`(删除) 三类差异；出现其他差异 → **中止且不落盘** |
| 幂等 | 已是 v9 时 `--apply` 无操作（报告 `already_v9`） |
| 回滚 | `--rollback` 从最近备份还原台账，并删除由本次迁移生成的 queue.json（按 `migrations` 留痕判定归属） |

**退出码**：`0` 成功 / `1` 白名单外差异或校验失败 / `2` 参数错误。

---

## 工具与用例接线点 `serves: FR-1, FR-8`

| 接口 | 文件 | 改动 |
|---|---|---|
| I-9 `reqboard_decompose` | `application/use-cases/Decompose.ts` | 拆分后 `taskStore.createMany` + 返回体新增 `queue_file`；**不再** `repo.mutate` 写 tasks |
| I-10 `reqboard_task_run` | `application/use-cases/ExecuteTask.ts` | 执行前 `taskStore.listByRequirement` 取父卡与 ready；日志打印 ready |
| I-11 `reqboard_task_move` | `application/use-cases/MoveTask.ts` | 状态改 `taskStore.mutate`（**先**），需求状态改 `repo.mutate`（**后**） |
| I-12 看板任务/甘特 | `http/routers/stages.ts`、`tasks.ts` | 任务列表由 `taskStore` 组装（异步路由改造） |
| I-13 执行工具 | `tools/{AdvanceTool,RunStatusTool,TaskStatusTool,TaskReportTool}` | 任务改经 `taskStore` |

**I-11 顺序契约（硬）**：`taskStore.mutate` 必须在 `repo.mutate` 之前。理由见 architecture.md「一致性模型」。

---

## 错误码 `serves: FR-4`

| 错误码 | 场景 | 处理 |
|---|---|---|
| `QUEUE_NOT_FOUND` | 对无队列的需求执行写操作 | 抛错（写不隐式建档） |
| `QUEUE_CORRUPTED` | 队列 JSON 解析失败 | 隔离改名 + 告警 + 降级返回空 |
| `QUEUE_VALIDATION_FAILED` | V-1~V-6 未通过 | 抛错，不落盘 |
| `CIRCULAR_DEPENDENCY` | 依赖成环 | 抛错，不落盘 |
| `LEDGER_REQUIRES_MIGRATION` | 台账为 v8（含 tasks） | 拒绝启动 + 指向迁移脚本 |
| `TASK_NOT_FOUND` | 任务 id 不存在 | 抛错 |
| `TEAM_TASK_NOT_FOUND` | 任务 id 不存在 | 抛错 |
| `WRITE_FAILED` | 文件写入失败 | 抛错，中止 |

---

## 变更历史 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8`

- 2026-09-27 21:10 - 初始接口（队列管理器 generateQueueFile/readQueue/updateQueue/validateQueueFile）
- 2026-09-27 22:50 - **范围变更重写**：新增 TaskStore 端口（I-1）与 QueueRepository（I-2）；
  接口改为任务维度；新增台账去 tasks 三接口（I-5/6/7）与迁移脚本接口（I-8，含回滚/白名单）；
  接线点扩到看板与执行工具（I-12/13）；补 `LEDGER_REQUIRES_MIGRATION` 等错误码（investor w-3936d77f）
