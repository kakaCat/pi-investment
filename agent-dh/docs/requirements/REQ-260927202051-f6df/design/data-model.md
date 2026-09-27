# 数据模型设计（REQ-260927202051-f6df）

> 任务数据的载体从台账 `tasks[]` 迁到按需求分片的 `queue.json`；台账 schema v8→v9 移除 `tasks`。
> 字段级清单另见 [queue-schema.md](./queue-schema.md)。

## 核心实体：QueueFile `serves: FR-1`

队列文件是**任务唯一存储**，一个需求一个文件：`docs/requirements/<REQ>/queue.json`。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `version` | `number` | ✅ | 队列格式版本（当前 1） |
| `requirement_id` | `string` | ✅ | 所属需求 ID |
| `schemaVersion` | `number` | ✅ | 对应台账 schema 版本（迁移后为 9）——用于判定该文件取自哪个时代的写入方 |
| `generated_at` | `string` | ✅ | 生成时间（ISO 8601） |
| `updated_at` | `string` | ❌ | 最后更新时间（每次任务写回刷新） |
| `tasks` | `QueueTask[]` | ✅ | **完整 TaskRecord** 列表（含 layer） |
| `edges` | `QueueEdge[]` | ✅ | 依赖边（from → to） |
| `layers` | `QueueLayer[]` | ✅ | 按依赖深度的层级分组 |
| `ready` | `string[]` | ✅ | 当前可执行任务 id（派生，写回时重算） |

### 与旧设计的差异（重要） `serves: FR-1`

| 项 | 旧（派生副本） | 新（唯一存储） |
|---|---|---|
| tasks 内容 | 精简投影（task_id/key/title/status/depends_on/layer） | **完整 TaskRecord** + `layer` |
| 主键字段 | `task_id` | `id`（与 `TaskRecord.id` 同名，读方零改名） |
| 依赖引用 | 计划键（t1/t2） | **任务 id**（`t-xxxxxx`，与 `TaskRecord.dependsOn` 同义） |
| 权威性 | 台账为准，队列可丢 | **队列为准**，台账无任务 |

理由：读方原本访问 `task.id` / `task.dependsOn` 等字段，保持同构可使 36 处改造退化为"只换数据源"。

---

## 子实体 `serves: FR-1`

### QueueTask = TaskRecord + layer `serves: FR-1`

```typescript
type QueueTask = TaskRecord & {
  /** DAG 层级（0 = 无依赖）。派生字段，由 topology 计算 */
  layer: number
}
```

`TaskRecord` 的全部字段原样保留（依据 `src/shared/protocol.ts:1150`），关键字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `string` | `t-xxxxxx`（主键） |
| `requirementId` | `string` | 所属需求 |
| `title` / `description` | `string` | 标题与说明 |
| `phase` / `side` / `scope` | 枚举 | 阶段 / 端侧 / 范围 |
| `dependsOn` | `string[]` | 同需求内任务 id 依赖（DAG 边来源） |
| `acceptance` | `string` | 验收标准 |
| `implementation` | `string?` | 实施方案 |
| `context` / `dependsSummary` | `string?` | 需求背景 / 上游产出摘要 |
| `parentId` / `stageKind` / `stages` | `?` | 父子卡与子卡阶段 |
| `attempt` / `revisions` | `?` | 重跑次数 / 卡片修订记录 |
| `lastRun` / `lastReport` | `?` | 最近 run 证据 / 汇报摘要 |
| `status` / `blocked` | 枚举 / `?` | 状态与卡因 |
| `executions` / `statusHistory` / `comments` | `[]` | 执行记录 / 状态时间线 / 评论 |
| `version` / `createdAt` / `updatedAt` / `createdBy` / `updatedBy` | — | 乐观锁与审计 |

**字段完整性由迁移契约测试逐字段比对锁定**（见 test-cases.md TC-6.x）——
少迁一个字段（如 `lastRun`）会让子卡完工凭证门静默失效。

### QueueEdge / QueueLayer `serves: FR-1`

```typescript
interface QueueEdge { from: string; to: string }          // from 是 to 的前置
interface QueueLayer { layer: number; tasks: string[] }   // 同层任务可并行
```

`edges` 由 `tasks[].dependsOn` 展开得到；`layers` 由拓扑排序分层得到；两者均为派生视图，
写回时整份重算，不允许手工编辑。

---

## 实体关系 `serves: FR-1`

```
QueueFile (1) ─── tasks (N) ──► QueueTask ──dependsOn[]──┐
     │                                ▲                   │
     │                                └───────────────────┘ 自引用
     ├── edges (N)   ── from/to ──► QueueTask.id
     ├── layers (N)  ── tasks[]  ──► QueueTask.id
     └── ready[]     ──          ──► QueueTask.id
```

---

## 台账 schema v8 → v9 数据契约 `serves: FR-6`

### 变更后的 ReqboardLedger `serves: FR-6`

```typescript
interface ReqboardLedger {
  schemaVersion: number      // 9
  revision: number
  requirements: RequirementRecord[]
  // tasks: TaskRecord[]     ← 字段移除（v9）
  triages: TriageRecord[]
  migrations?: { from: number; to: number; at: number; by: string }[]
}
```

| 变更项 | 旧版本行为 | 新版本行为 | 迁移方案 |
|---|---|---|---|
| `tasks` 字段 | 必填数组，读方从这里取任务 | **移除**；`isPlausibleLedger` 不再要求该字段 | 迁移脚本把 tasks 写入 queue.json 后从台账删除 |
| `REQBOARD_SCHEMA_VERSION` | 8 | 9 | 常量同步改；`emptyLedger()` 不再产出 tasks |
| 读到 v8 文件（含 tasks） | 正常加载 | **拒绝启动 + 提示先迁移** | 跑 `migrate-ledger.ts --apply` |
| `LedgerChange.tasks` | 变更通知携带任务 | 移除该字段；任务变更由 `TaskStore` 自身订阅 | 订阅者改订阅 `TaskStore` |
| `repo.mutate` 的 tasks 返回 | 返回改动任务 | 只返回 requirements / triages | 任务写走 `taskStore.mutate` |

### 已迁移数据的回溯字段 `serves: FR-6`

`migrations[]` 追加 `{ from: 8, to: 9, at, by: 'migrate-ledger.ts' }`，
使"这份台账何时被谁升到 v9"可追溯（与既有 v4→v5→v6→v7 留痕同构）。

---

## 数据约束（校验规则 V-1 ~ V-6） `serves: FR-5`

> **规则编号即单一事实源**。接口实现见 [interfaces.md](./interfaces.md)，
> 测试覆盖见 [test-cases.md](./test-cases.md)，场景见 [use-cases.md](./use-cases.md)。
> 变更任一规则须同步四处。

**V-1 必填字段完整性**：`version` / `requirement_id` / `schemaVersion` / `generated_at` / `tasks` / `edges` / `layers` / `ready`
均存在且类型正确（`updated_at` 可选）

**V-2 标识唯一性**：`tasks[].id` 两两唯一

**V-3 引用完整性**：
- `tasks[].dependsOn[]` 中每个 id 必须存在于**同需求**的 `tasks[]`
- `edges.from` / `edges.to` / `layers[].tasks[]` / `ready[]` 的 id 都必须在 `tasks[]` 中
- `tasks[].requirementId` 必须等于 `queue.requirement_id`（防跨需求串档）

**V-4 层级一致性**：`layer >= 0`；若 `t.dependsOn` 含 `d` 则 `t.layer > d.layer`；`layer === 0` 的任务 `dependsOn` 必须为空

**V-5 ready 双向一致性**：
- 假就绪禁止：`ready` 中任务的依赖状态必须全为 `done`
- 漏就绪禁止：依赖已全 `done` 且自身为 `todo` 的任务必须出现在 `ready` 中

**V-6 无环性**：对 `edges` 拓扑排序可完整完成

**新增（相对旧设计）**：V-2 由「task_id 与 key 双唯一」收窄为「id 唯一」（key 概念随计划键不再持久化而取消）；
V-3 增加同需求约束（防跨档引用）。

---

## 数据生命周期 `serves: FR-3`

### 生成（拆分时） `serves: FR-3`

```
Decompose 得到 PlanTask[] → 构造 TaskRecord[] → 建 QueueFile（layer 待算）
  → topology 分层 → 求 ready → validateQueueFile → 原子写 queue.json
```

### 更新（状态推进时） `serves: FR-3`

```
MoveTask(taskStore.mutate) → 改 tasks[].status/statusHistory/updatedAt
  → 重算 edges/layers/ready → 校验 → 原子写 → 失效缓存
```

### 迁移（一次性） `serves: FR-3`

```
读台账 v8 → 按 requirementId 分组 tasks → 每组写 queue.json
  → 台账去 tasks、schemaVersion=9、migrations 留痕 → 备份 + 原子替换
```

### 删除 `serves: FR-3`

需求被归档/取消时**不删** queue.json（归档材料需要任务历史）；仅当需求整册删除时才随目录一并删除。

---

## 存储与版本 `serves: FR-4`

- 位置：`docs/requirements/<REQ>/queue.json`（工作区相对路径）
- 编码 UTF-8；JSON 2 空格缩进（便于 diff 与人工查看）
- 原子写：复用 `persistAtomic`（写临时文件 → fsync → rename）
- 版本：`version`（队列格式）与 `schemaVersion`（台账时代）双字段，
  前者管格式演进、后者管迁移判定

---

## 变更历史 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8`

- 2026-09-27 21:05 - 初始数据模型（队列为派生副本，task_id/key 双主键）
- 2026-09-27 22:40 - **范围变更重写**：QueueTask 改为完整 TaskRecord + layer（主键换 `id`、依赖改任务 id）；
  新增台账 v9 数据契约与迁移留痕；V-2 收窄、V-3 增同需求约束；补数据生命周期与删除策略（investor w-3936d77f）
