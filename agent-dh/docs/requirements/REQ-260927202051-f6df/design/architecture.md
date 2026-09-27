# 架构设计（REQ-260927202051-f6df）

> 任务数据从台账迁出 → `queue.json` 成为任务唯一存储；台账 schema v8→v9 移除 `tasks`。
> 本文与 [data-model.md](./data-model.md)、[interfaces.md](./interfaces.md)、[migration.md](./migration.md) 配套。

## 目标与总体方案 `serves: FR-1`

**问题**：任务数据（587 条、含 465 条依赖边）与需求记录混存在单体台账 `dsh-reqboard.json`（7.8MB）中，
任务无法按需求分片读写，DAG 依赖没有显式载体；用户要求 tasks 不再记录到台账，改由队列承载。

**当前状况**：
- 任务存 `dsh-reqboard.json` 的 `tasks[]`；`JsonLedgerRepository` 是唯一 I/O 入口
- 36 个模块通过 `ledger.tasks` / `snapshot().tasks` / `changed.tasks` 读任务
- 队列不存在；看板任务页与甘特经 `http/routers/stages.ts` 从台账渲染

**设计方案**：
1. 新增**任务存储层**：`TaskStore` 端口（代码级"队列"）+ `QueueTaskStore` 实现，落在 `queue.json`
2. 新增**队列文件**：`docs/requirements/<REQ>/queue.json`，同时承载**完整 TaskRecord** 与 DAG 派生视图
   （`layer` / `edges` / `layers` / `ready`）
3. **台账瘦身**：`ReqboardLedger` 去掉 `tasks`，`schemaVersion` 8→9，只留 requirements / triages
4. **读方改造**：36 个模块从 `ledger.tasks` 改为经 `TaskStore` 取任务
5. **一次性迁移**：`scripts/migrate-ledger.ts` 追加 v8→v9 变换，587 条任务分片写入各自 queue.json

**不这么做的后果**：任务与需求继续耦合在单体文件，7.8MB 台账写放大持续累积；用户明确要求的
"执行从队列取父卡、状态更新在队列实现"无法成立。

---

## 关键决策 `serves: FR-1`

### 决策 1：queue.json 存**完整** TaskRecord，而非裁剪投影 `serves: FR-1`

| 方案 | 说明 | 结论 |
|---|---|---|
| A. 裁剪投影（只存 id/title/status/dependsOn） | 队列文件小，但每个读方都要回别处补字段 | ❌ 否 |
| **B. 完整 TaskRecord + 追加 `layer` 字段（选定）** | `queue.tasks[i]` 与 `TaskRecord` 同构，读方改数据源即可、不改字段访问 | ✅ 是 |

理由：FR-8 要改 36 个读方。若队列只存投影，每个读方还要补齐 20+ 个字段（`acceptance`/`implementation`/
`lastRun`/`revisions`/`executions`…），回归面反而放大。**让队列的形状等于任务契约，是最小回归路径。**

### 决策 2：以 `TaskStore` 端口作为"队列"的代码入口，而非让读方直接读文件 `serves: FR-1`

读方不得各自 `fs.readFile(queue.json)`，统一经 `TaskStore`（异步端口，内存缓存 + 原子写回）。
理由：36 个读方各写一份读取/解析/容错逻辑 = 36 处不一致；端口化后校验、缓存、原子写只实现一次。

### 决策 3（被否方案）：仅把队列当持久化后端、内存快照仍聚合全部 tasks `serves: FR-1`

启动时把所有 queue.json 反序列化进 `ledger.tasks`，36 个读方零改动。改动最小。
**否掉理由**：① 违背用户"执行从队列取父卡"的明确要求——读的还是内存聚合体；
② 队列文件与内存副本形成双真相，写路径一旦漏刷即静默漂移；
③ 无法回答"某需求的任务存在哪"，队列退化为影子文件。
保留该方案作为**回退路径**（见「回滚设计」）。

---

## 模块改动地图 `serves: FR-1`

```
                    拆分（Decompose）
                          │ 写任务
                          ▼
              ┌───────────────────────────┐
              │  TaskStore（端口，队列）   │
              │  get/list/create/move/     │
              │  report/mutate             │
              └───────────┬───────────────┘
                          │ 实现
                          ▼
              ┌───────────────────────────┐
              │  QueueTaskStore            │
              │  · 缓存 + 原子写            │
              │  · 调 topology/validate     │
              └───────────┬───────────────┘
                          │ 持久化
                          ▼
        docs/requirements/<REQ>/queue.json   ← 任务唯一存储
                          ▲
                          │ 读取
        ┌─────────────────┴──────────────────┐
        │ 36 个读方：看板/路由/工具/用例/门禁 │
        └────────────────────────────────────┘

              dsh-reqboard.json（v9）          ← 只留 requirements / triages
              └─ tasks[] 字段已移除
```

**改动清单**：

| 模块/文件 | 类型 | 改动内容 | 原因（serves哪条FR） | 影响范围 |
|---|---|---|---|---|
| S-1 `src/domain/queue/QueueTypes.ts` | 新增 | 队列类型：QueueFile / QueueTask(=TaskRecord+layer) / QueueEdge / QueueLayer / ValidationResult | FR-1 | 无 |
| S-2 `src/domain/queue/topology.ts` | 新增 | 纯函数：拓扑排序、层级、ready 推导 | FR-1 | 无 |
| S-3 `src/domain/queue/validateQueue.ts` | 新增 | 纯函数：V-1~V-6 校验 | FR-5 | 无 |
| S-4 `src/repositories/QueueRepository.ts` | 新增 | 队列文件 I/O：按需求读/写 + 复用 `persistAtomic` | FR-1, FR-2, FR-4 | 无 |
| S-5 `src/repositories/QueueTaskStore.ts` | 新增 | `TaskStore` 端口实现：任务 CRUD + 缓存 + 原子写 | FR-1, FR-2, FR-3 | 无 |
| S-6 `src/application/ports.ts` | 修改 | 新增 `TaskStore` 端口；`ReqboardLedger` 去 `tasks` | FR-1, FR-6 | 全仓类型面 |
| S-7 `src/shared/protocol.ts` | 修改 | `schemaVersion` 8→9；`ReqboardLedger` 去 `tasks`；`emptyLedger` 同步 | FR-6 | 全仓类型面 |
| S-8 `src/adapters/JsonLedgerRepository.ts` | 修改 | 读写去 tasks；`isPlausibleLedger` 不再要求 tasks；`LedgerChange` 去 tasks；读到 v8 拒绝启动 | FR-6 | 台账 I/O |
| S-9 `scripts/migrate-ledger.ts` | 修改 | 追加 v8→v9：任务分片写出 + 台账去 tasks + 留痕 + `--rollback` | FR-7 | 迁移 |
| S-10 `src/http/routers/{stages,tasks,requirements,verdicts}.ts` | 修改 | 任务改经 `TaskStore` 取 | FR-8 | 看板任务页/甘特 |
| S-11 `src/tools/{AdvanceTool,RunStatusTool,TaskStatusTool,TaskReportTool}` | 修改 | 任务改经 `TaskStore` 取 | FR-8 | 工具契约 |
| S-12 `src/application/use-cases/*` | 修改 | 任务改经 `TaskStore`；`mutate` 只改需求/分诊 | FR-1, FR-8 | 执行链 |
| S-13 `src/application/internal/*` | 修改 | 同上（plan-landing/lazy-expand/rollup/rtm-yaml/rework-update/verdicts/failure-handling/support/confirm-settle/agent-handle/capture-section/verification-doc-writer） | FR-8 | 门禁与派生 |
| S-14 `src/application/query/*` + `dive/idle-capture-actions.ts` + `gate/handlers/h3-inject.ts` | 修改 | 同上 | FR-8 | 查询与 Dive |

**分层理由**：纯类型/纯算法入 `domain/`（可单测、无 IO）；文件 I/O 入 `repositories/`
（与 `TaskRepository.ts` 同构）；端口在 `application/ports.ts` 定义、实现留在 `repositories/`
（依赖倒置，application 不 import 适配器）。

---

## 任务存储所有权 `serves: FR-1, FR-6`

| 数据 | 迁移前 | 迁移后 | 载体 |
|---|---|---|---|
| 任务卡（含依赖、验收、执行记录、汇报、修订） | 台账 `tasks[]` | **队列 `queue.json`** | 每需求一文件 |
| DAG 派生视图（layer/edges/layers/ready） | 不存在（运行期临时算） | **队列 `queue.json`** | 同上 |
| 需求记录 | 台账 `requirements[]` | 台账 `requirements[]`（不变） | `dsh-reqboard.json` |
| 分诊记录 | 台账 `triages[]` | 台账 `triages[]`（不变） | 同上 |
| 评论 / revision / migrations | 台账 | 台账（不变） | 同上 |

---

## 台账 schema v8→v9 `serves: FR-6`

**变更**：
- `tasks` 字段从写入内容中移除
- `REQBOARD_SCHEMA_VERSION` 8 → 9
- `migrations[]` 追加 `{ from: 8, to: 9, at, by }` 留痕
- `isPlausibleLedger` 去掉 `Array.isArray(o.tasks)` 要求（v9 无 tasks 不算损坏）
- **读兼容**：读到带 `tasks` 的旧文件（v8）→ 运行时不静默丢弃，而是**拒绝启动并提示先迁移**
  （静默丢任务是最坏结果：587 条任务凭空消失且无人知晓）

**为什么升版本而不是原地删字段**：留痕可追溯；旧文件被 v9 运行时代码拒绝时，报错能直接指向迁移脚本。

---

## 读方改造边界 `serves: FR-8`

**统一改法**：`ledger.tasks` / `snapshot().tasks` / `changed.tasks` → `await taskStore.listByRequirement(reqId)` /
`await taskStore.get(taskId)`；写任务 → `taskStore.mutate(reqId, fn)`。

**两类读方**：
1. **纯读**（看板 stages、TaskStatus、RunStatus、TaskTree、QueryStageDetail）：改数据源即可，无事务问题
2. **读改写**（MoveTask、ExecuteTask、AdvanceChain、rollup、rework-update、verdicts）：原先在
   一次 `repo.mutate` 事务里同改需求+任务；改造后拆成 **先 `taskStore.mutate` 改任务、再 `repo.mutate` 改需求**，
   并接受"两步非原子"。风险与兜底见下节。

---

## 一致性模型 `serves: FR-3`

**原则**：单需求内以 `queue.json` 为唯一真相；跨实体（任务 vs 需求状态）非原子。

| 场景 | 保证 | 兜底 |
|---|---|---|
| 单需求任务写 | 原子 rename，写前校验 V-1~V-6 | 校验失败不落盘，保持上次有效内容 |
| 多窗口并发写同需求 | last-write-wins | 原子 rename 保证不产生半截 JSON |
| 任务写成功、需求状态写失败 | **允许**：任务已推进 | 需求状态可由 rollup 重算修复（幂等） |
| 需求状态写成功、任务写失败 | **不允许**：顺序固定为先任务后需求 | 由接口调用顺序强制 |

**顺序纪律**：`taskStore.mutate` 必须早于 `repo.mutate`。理由：任务状态是 rollup 算需求状态的输入，
反向顺序会产生"需求已验收但任务未完成"的悬空态。

---

## 错误处理策略 `serves: FR-4`

| 错误场景 | 处理策略 | 是否落盘 |
|---|---|---|
| 队列文件不存在（未拆分需求） | 返回空列表，**不是错误** | — |
| 队列文件损坏（JSON 解析失败） | 隔离改名 `.corrupt-<ts>`，告警，返回空并标记该需求降级 | 否 |
| V-1~V-6 校验失败 | 抛 `QUEUE_VALIDATION_FAILED`，保留上次有效内容 | 否 |
| 写入失败（权限/磁盘满） | 抛错，中止操作 | 否 |
| 台账读到 v8（含 tasks） | **拒绝启动**并提示先跑迁移脚本 | 否 |
| 环依赖 | `generateQueueFile` 抛 `CIRCULAR_DEPENDENCY` | 否 |

---

## 回滚设计 `serves: FR-7`

1. **迁移前**：脚本自动备份台账为 `dsh-reqboard.json.backup-<ts>`（复用既有 `replaceAll` 语义）
2. **迁移中**：逐路径白名单校验，出现白名单外差异 → **中止且不落盘**
3. **迁移后回滚**：`--rollback` 从备份还原台账（任务回到 v8 的 tasks[]），并删除已生成的 queue.json
4. **运行期回退**：若读方改造成本超预算，可退回「决策 3」的内存聚合方案（读方零改动），
   队列文件继续存在但降级为持久化后端——回退不丢数据

---

## 性能考量 `serves: FR-4`

- 单需求队列文件 <100KB（任务数 <100）；生成 <50ms、读取 <10ms、更新 <20ms
- `TaskStore` 按需加载 + 内存缓存：启动时**不**预读全部 82 个需求的文件（避免启动期扫盘）
- 首访某需求时加载其 queue.json，之后走缓存；写后失效该需求的缓存

---

## 目录结构 `serves: FR-1`

```
packages/web/dsh-pmboard/
├── src/domain/queue/{QueueTypes,topology,validateQueue}.ts     # 纯类型与纯算法
├── src/repositories/{QueueRepository,QueueTaskStore}.ts        # 文件 I/O 与端口实现
├── src/application/ports.ts                                    # TaskStore 端口
├── src/adapters/JsonLedgerRepository.ts                        # 台账（去 tasks）
└── scripts/migrate-ledger.ts                                   # v8→v9 迁移
docs/requirements/<REQ>/queue.json                              # 任务唯一存储
```

---

## 依赖关系 `serves: FR-1`

**新增依赖**：无（复用 `node:fs/promises` 与已导出的 `persistAtomic`）

**复用而非重写**：
- `persistAtomic`（`adapters/JsonLedgerRepository.ts` 已导出）→ 队列原子写直接用，避免第二套原子写实现
- `scripts/migrate-ledger.ts` 迁移骨架（备份/白名单/幂等/留痕）→ v8→v9 追加为一次变换

---

## 测试策略 `serves: FR-5`

| 层级 | 覆盖 | 方式 |
|---|---|---|
| 单元 | topology / validateQueue / QueueRepository / QueueTaskStore | vitest，纯函数与临时目录 |
| 迁移 | 587 条 → 分片、dry-run/apply/verify、幂等、回滚、白名单拦截 | 脚本 + 真实台账副本 |
| 契约 | 任务字段在队列里完整（逐字段比对迁移前后） | 脚本断言 |
| 集成 | 拆分→执行→推进 全链路 | 新建测试需求 |
| 回归（最高风险） | 看板任务页与甘特在迁移后正常渲染 | 启动 :13080 实测页面 |
| 门禁 | plugin-schema 冒烟 + 全量 build | `pnpm build` / vitest |

**明确不做**：不把"单测绿"当作看板不回归的证据——看板必须实测（见 test-cases.md TC-9.x）。

---

## 变更历史 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8`

- 2026-09-27 21:00 - 初始设计（队列为派生副本）
- 2026-09-27 22:30 - **范围变更重写**：队列升级为任务唯一存储；新增台账 v9 去 tasks、587 条迁移、
  36 处读方改造三块；补关键决策与被否方案、一致性模型、回滚设计（investor w-3936d77f）
