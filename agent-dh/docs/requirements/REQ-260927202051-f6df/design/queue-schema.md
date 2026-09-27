# 队列文件 Schema（字段级附录）

> **本文是 [data-model.md](./data-model.md) 的字段级附录**，不另立语义。
> 语义（实体关系、约束、生命周期）以 data-model.md 为准；本文只做字段清单与 JSON 示例速查。
> **服务功能点**：FR-1（队列生成）、FR-4（原子写入）、FR-5（版本兼容）、FR-7（迁移）。

## 1. 目标（可证伪） `serves: FR-1, FR-5`

在代码层面达成：
1. `QueueFile` 的字段级契约可被逐字段断言（含完整 TaskRecord 的 20+ 字段）
2. 迁移前后的字段可深比对（去掉 `layer` 后应完全相同）
3. 文件写入原子（临时文件 → fsync → rename）

**验证点**：类型编译通过；`validateQueueFile` 可检出缺字段（V-1）；迁移契约测试逐字段通过。

---

## 2. 字段清单 `serves: FR-1, FR-5`

### 2.1 QueueFile 顶层 `serves: FR-1`

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `version` | number | ✅ | 队列格式版本，当前 `1` |
| `requirement_id` | string | ✅ | `REQ-` 前缀；须与所在目录一致 |
| `schemaVersion` | number | ✅ | 迁移后为 `9`（对应台账时代） |
| `generated_at` | string | ✅ | ISO 8601 |
| `updated_at` | string | ❌ | 每次写回刷新 |
| `tasks` | QueueTask[] | ✅ | 完整 TaskRecord + `layer` |
| `edges` | QueueEdge[] | ✅ | 由 dependsOn 展开 |
| `layers` | QueueLayer[] | ✅ | 拓扑分层 |
| `ready` | string[] | ✅ | 派生；写回重算 |

### 2.2 QueueTask（= TaskRecord + layer） `serves: FR-1`

**字段顺序与必填性逐字对齐 `src/shared/protocol.ts` 的 `TaskRecord`（1150–1216 行）。**

| # | 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| 1 | `id` | string | ✅ | `t-xxxxxx`，主键 |
| 2 | `requirementId` | string | ✅ | 须等于顶层 `requirement_id`（V-3） |
| 3 | `title` | string | ✅ | 标题 |
| 4 | `description` | string | ✅ | 说明 |
| 5 | `phase` | TaskPhase | ✅ | doc/ui/analysis/implement/test/review/merge |
| 6 | `side` | TaskSide | ✅ | frontend/backend/fullstack/doc |
| 7 | `dependsOn` | string[] | ✅ | DAG 依赖（同需求任务 id） |
| 8 | `scope` | TaskScope | ✅ | 任务范围（**对象**`{apis,tables,files}`，不是字符串） |
| 9 | `acceptance` | string | ✅ | 验收标准 |
| 10 | `implementation` | string | ❌ | 实施方案（decompose 从 PlanTask 透传） |
| 11 | `context` | string | ✅ | 需求背景摘要（自足执行用） |
| 12 | `dependsSummary` | string | ❌ | 上游产出摘要（handoff） |
| 13 | `parentId` | string | ❌ | 有值 = 子卡，指向父卡 id |
| 14 | `stageKind` | StageKind | ❌ | 子卡阶段（子卡必填、父卡不得有，INV-2） |
| 15 | `stages` | StageKind[] | ❌ | 该卡显式声明子卡 stages（FR-1b 逃生舱口） |
| 16 | `attempt` | number | ❌ | 失败重跑次数（默认 0） |
| 17 | `revisions` | CardRevision[] | ❌ | 卡片修订记录（append-only，INV-6） |
| 18 | `lastRun` | TaskRunEvidence | ❌ | 最近 run 证据（子卡完工凭证门依赖） |
| 19 | `lastReport` | TaskReportSummary | ❌ | 最近汇报（done 凭证门依赖） |
| 20 | `teamTaskId` | string | ❌ | 团队执行映射（共享任务板 team task id ↔ 子卡 id） |
| 21 | `executorHint` | ExecutorHint | ❌ | 执行方式提示 |
| 22 | `cardDoc` | string | ❌ | 自足任务卡文档路径 |
| 23 | `requirementRefs` | string[] | ❌ | 需求条款引用（RTM 覆盖度追踪） |
| 24 | `skipIntegration` | boolean | ❌ | 跳过联调 |
| 25 | `status` | TaskStatus | ✅ | 状态 |
| 26 | `blocked` | boolean | ✅ | 卡因标记（**必填**） |
| 27 | `blockedReason` | string | ❌ | 卡因说明 |
| 28 | `claimedBy` | string | ❌ | 认领人 |
| 29 | `claimedAt` | number | ❌ | 认领时间 |
| 30 | `executions` | ExecutionRecord[] | ✅ | 执行记录 |
| 31 | `statusHistory` | StatusEvent[] | ❌ | 状态事件时间线（**可选**） |
| 32 | `comments` | CommentRecord[] | ✅ | 评论 |
| 33 | `version` | number | ✅ | 乐观锁 |
| 34 | `createdAt` / `updatedAt` | number | ✅ | 审计时间 |
| 35 | `createdBy` / `updatedBy` | ActorRef | ✅ | 审计主体 |
| — | **`layer`** | number | ✅ | **队列专有派生字段**（DAG 层级），非 TaskRecord 字段 |

**合计：TaskRecord 37 个字段（19 必填 + 18 可选）+ 队列专有 `layer` = 38 行。**

> **唯一新增字段是 `layer`**。其余与 `src/shared/protocol.ts:TaskRecord`（1150–1216 行）逐字对齐。
> 任何字段被省略都会破坏"读方只换数据源"的最小回归路径（见 architecture.md 决策 1）。
>
> **⚠️ 勘误（2026-09-27，w-3936d77f）：** 本节初版表格有 5 处与真身不符，已修正 ——
> ①`statusHistory` 原标必填，真身为可选（`protocol.ts:1209`）；
> ②`blocked` 原标可选，真身为必填（`:1203`）；
> ③原文写 `teamExecution: TeamExecution`，真身为 `teamTaskId?: string`（`:1194`）；
> ④漏列 7 个字段：`executorHint`/`cardDoc`/`requirementRefs`/`skipIntegration`/`blockedReason`/`claimedBy`/`claimedAt`；
> ⑤§3 JSON 示例 `"scope": "backend"` 为字符串，真身 `TaskScope` 是对象。
> **实现纪律**：`QueueTypes.ts` 用 `QueueTask extends TaskRecord`，**永不按本表重列字段** ——
> 这样文档再漂移也不会让实现漏字段；本表仅供人阅读理解。

### 2.3 QueueEdge / QueueLayer `serves: FR-1`

| 实体 | 字段 | 类型 | 约束 |
|---|---|---|---|
| QueueEdge | `from` | string | 前置任务 id，须存在于 tasks |
| QueueEdge | `to` | string | 后继任务 id，须存在于 tasks |
| QueueLayer | `layer` | number | ≥0，从 0 连续 |
| QueueLayer | `tasks` | string[] | 该层任务 id |

---

## 3. JSON 示例 `serves: FR-1`

```json
{
  "version": 1,
  "requirement_id": "REQ-260927202051-f6df",
  "schemaVersion": 9,
  "generated_at": "2026-09-27T22:00:00.000Z",
  "updated_at": "2026-09-27T23:30:00.000Z",
  "tasks": [
    {
      "id": "t-1a2b3c",
      "requirementId": "REQ-260927202051-f6df",
      "title": "定义队列数据结构与类型",
      "description": "…",
      "phase": "implement",
      "side": "backend",
      "scope": { "apis": [], "tables": [], "files": [] },
      "dependsOn": [],
      "acceptance": "npx tsc --noEmit 退出码 0",
      "implementation": "新建 src/domain/queue/QueueTypes.ts …",
      "context": "…",
      "status": "todo",
      "executions": [],
      "statusHistory": [{ "to": "todo", "at": 1759000000000, "by": { "kind": "agent" } }],
      "comments": [],
      "version": 1,
      "createdAt": 1759000000000,
      "updatedAt": 1759000000000,
      "createdBy": { "kind": "agent", "sessionId": "session-3936d77f" },
      "updatedBy": { "kind": "agent", "sessionId": "session-3936d77f" },
      "layer": 0
    }
  ],
  "edges": [],
  "layers": [{ "layer": 0, "tasks": ["t-1a2b3c"] }],
  "ready": ["t-1a2b3c"]
}
```

---

## 4. 原子写入契约 `serves: FR-4`

**复用** `adapters/JsonLedgerRepository.ts` 导出的 `persistAtomic`：

```
1. mkdir -p 所在目录
2. 写 .<random>.tmp（同目录，保证 rename 在同一文件系统）
3. fh.sync()  —— 防断电零长文件
4. rename(tmp, target)  —— 原子替换
```

**契约**：写入前必须 `validateQueueFile` 通过；失败抛错且**不创建临时文件**。
**断言**：写入后目录内无 `.tmp` 残留；并发写不产生半截 JSON。

---

## 5. 兼容与版本 `serves: FR-5`

| 版本字段 | 管什么 | 当前值 | 演进规则 |
|---|---|---|---|
| `version` | 队列**格式** | 1 | 增删/改义字段时 +1；新增可选字段不变 |
| `schemaVersion` | 队列写入时的**台账时代** | 9 | 随台账迁移同步；用于判定文件出处 |

**读取策略**：`version` 高于当前已支持版本 → 告警并按已知字段尽力解析（不静默丢弃）；
`schemaVersion` 低于 9 → 视为迁移未完成，提示先跑迁移脚本。

---

## 6. 错误处理 `serves: FR-4`

| 场景 | 处理 | 落盘 |
|---|---|---|
| 文件不存在 | `load` 返回 undefined（非错误） | — |
| JSON 解析失败 | 隔离改名 `.corrupt-<ts>` + 告警 + 降级 | 否 |
| V-1~V-6 失败 | 抛 `QUEUE_VALIDATION_FAILED` | 否 |
| 无写权限/磁盘满 | 抛错 | 否 |
| 环依赖 | 抛 `CIRCULAR_DEPENDENCY`（生成期） | 否 |

---

## 7. 安全与并发 `serves: FR-4`

- 不使用文件锁（避免死锁）；依赖 rename 原子性
- 同需求并发写：last-write-wins；写路径**强制重读文件后合并**，不信任缓存
- 不同需求写互相独立（分片隔离是本次改造的核心收益之一）
- 队列文件随需求目录权限；不含凭据等敏感信息

---

## 8. 变更历史 `serves: FR-1, FR-4, FR-5, FR-7`

- 2026-09-27 20:30 - 初始 Schema（队列为派生副本；主键 task_id + key；精简投影）
- 2026-09-27 23:30 - **范围变更重写**：降级为 data-model.md 的字段级附录；
  字段清单改为完整 TaskRecord（主键 `id`，唯一新增 `layer`）；新增 `schemaVersion`；
  补迁移深比对断言与 version/schemaVersion 双版本演进规则（investor w-3936d77f）
