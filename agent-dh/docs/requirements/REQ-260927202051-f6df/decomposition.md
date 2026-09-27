# 拆分计划（REQ-260927202051-f6df）

> **目标**：任务数据从台账 `dsh-reqboard.json` 迁到按需求分片的 `queue.json`（含 DAG 层级与 ready 队列），
> 拆分生成 / 执行读取 / 状态更新三处均以队列为准，台账 schema v8→v9 移除 `tasks`。
> **做法**：先立队列存储层（类型/拓扑/校验/仓储/TaskStore 端口）→ 台账去 tasks → 改造 36 处读方 →
> 接线工具 → 跑 587 条迁移 → 看板实测回归 → 端到端验收。
> 本计划须**人批准**后才能落任务卡（`reqboard_decompose`）。

---

## 编号口径

| 编号 | 出自 | 指什么 |
|---|---|---|
| FR-x | requirement.md 功能点表 | 需求条款（FR-1~FR-8） |
| I-x | interfaces.md 接口清单 | 接口（I-1~I-13） |
| S-x | architecture.md 改动清单 | 模块落点（S-1~S-14） |
| TC-x.y | test-cases.md 用例 | 测试用例 |
| UC-x | use-cases.md 场景 | 用户场景（UC-1~UC-9） |
| V-x | data-model.md 数据约束 | 校验规则（V-1~V-6） |
| D-x | migration.md 迁移步骤 | 迁移步骤（D-1~D-9） |
| t-x | 本文档任务表 | 任务 |

**落地路径基准**：`packages/web/dsh-pmboard/`｜**队列文件**：`docs/requirements/<REQ>/queue.json`
**※ 本需求为纯后端**：无 frontend.md / backend.md，模块编号由 architecture.md 改动清单承接。

---

## 任务表

| 计划 key | 任务 id | 标题 | 覆盖条款 | 落点（编号+文件） | 阶段 | 端侧 | 依赖 | 工作量 | 验收标准 |
|---|---|---|---|---|---|---|---|---|---|
| t1 | （落库后回填） | 定义队列类型与任务契约 | FR-1 | S-1 + `src/domain/queue/QueueTypes.ts` | implement | backend | — | S | ① `npx tsc --noEmit` 退出码 0；② 断言 `QueueTask = TaskRecord & { layer: number }`（类型级断言编译通过）；③ 脚本比对 `QueueTask` 键集 − `TaskRecord` 键集 = `{layer}`（差集恰为 1 个键）；④ `grep -c '^export interface'` ≥ 5 |
| t2 | （落库后回填） | 实现 DAG 拓扑分层与派生视图 | FR-1 | S-2, I-3 + `src/domain/queue/topology.ts` | implement | backend | t1 | S | ① `npx vitest run src/domain/queue/topology.test.ts` 全绿（TC-1.1~TC-1.7）；② 菱形 t1→{t2,t3}→t4 得 layers=[[t1],[t2,t3],[t4]] 且 ready=['t1']；③ 环输入抛错且 message 含 `CIRCULAR`（TC-1.3）；④ 空输入返回空三件套不抛错（TC-1.4）；⑤ `grep` 断言不 import `node:fs` |
| t3 | （落库后回填） | 实现队列数据校验 V-1~V-6 | FR-5 | S-3, I-4 + `src/domain/queue/validateQueue.ts` | implement | backend | t1 | M | ① `npx vitest run src/domain/queue/validateQueue.test.ts` 全绿（TC-2.1~TC-2.11）；② 6 条规则各有反例触发，脚本汇总 **6/6**；③ 合法队列 `passed=true` 且 `issues.length===0`；④ 全部失败用例 `passed=false` 且**未 throw**（TC-2.10）；⑤ 断言从 `topology.ts` import 环检测，未复制算法 |
| t4 | （落库后回填） | 实现队列仓储与原子写入 | FR-1, FR-4 | S-4, I-2 + `src/repositories/QueueRepository.ts` | implement | backend | t1, t2, t3 | M | ① `npx vitest run src/repositories/QueueRepository.test.ts` 全绿（TC-3.1~TC-3.6）；② `save` 后 `jq .` 解析成功且目录内**无 `.tmp` 残留**；③ `load` 不存在需求返回 `undefined`（非抛错）；④ 损坏 JSON → 产生 `.corrupt-<ts>` 隔离文件；⑤ 校验失败路径断言**文件不存在**（不落盘）；⑥ `grep` 断言复用 `persistAtomic`，未自造原子写 |
| t5 | （落库后回填） | 实现 TaskStore 端口与队列实现 | FR-1, FR-2, FR-3 | S-5, I-1 + `src/repositories/QueueTaskStore.ts` | implement | backend | t4 | M | ① `npx vitest run src/repositories/QueueTaskStore.test.ts` 全绿（TC-4.1~TC-4.8）；② `createMany` 5 任务后队列含 5 条且 `layer` 已算；③ 重复 id 幂等跳过不覆盖（TC-4.2）；④ `mutate` 改 done 后 `ready` 解锁下游、`updated_at` 刷新（TC-4.3）；⑤ 无队列需求 `mutate` 抛 `QUEUE_NOT_FOUND`（TC-4.4）；⑥ 写后 `get` 立即读到新值（缓存已失效，TC-4.7） |
| t6 | （落库后回填） | 台账 schema v9：移除 tasks | FR-6 | S-6, S-7, S-8, I-5, I-6, I-7 + `src/{application/ports.ts,shared/protocol.ts,adapters/JsonLedgerRepository.ts}` | implement | backend | t5 | M | ① 台账相关测试全绿（TC-5.1~TC-5.6）；② `emptyLedger()` 无 `tasks` 键且 `schemaVersion===9`；③ 加载 v8 台账（含 tasks）抛 `LEDGER_REQUIRES_MIGRATION` 且**未静默丢弃任务**（TC-5.3）；④ 落盘 JSON `grep` 无 `"tasks"` 键（TC-5.6）；⑤ `LedgerChange` 无 `tasks` 字段（编译期断言） |
| t7 | （落库后回填） | 读方改造 A：看板与 HTTP 路由 | FR-8 | S-10, I-12 + `src/http/routers/{stages,tasks,requirements,verdicts}.ts` | implement | backend | t6 | M | ① 四路由改经 `taskStore`（`grep` 无 `ledger.tasks`/`snapshot().tasks`）；② 迁移前后相同请求返回 JSON **逐字节相等**（TC-8.1~TC-8.4）；③ `stages` 返回任务数 = 队列内任务数；④ 异步改造后无未 await 的 Promise（类型检查） |
| t8 | （落库后回填） | 读方改造 B：执行工具 | FR-8 | S-11, I-13 + `src/tools/{AdvanceTool,RunStatusTool,TaskStatusTool,TaskReportTool}` | implement | backend | t6 | M | ① 四工具改经 `taskStore`；② 迁移前后输出**逐字节相等**（TC-8.5~TC-8.7）；③ `TaskReportTool` 写回落到队列且 `lastReport` 已写；④ `AdvanceTool` ready 选择结果与迁移前一致 |
| t9 | （落库后回填） | 读方改造 C：用例层 | FR-8 | S-12 + `src/application/use-cases/*` | implement | backend | t6 | M | ① 用例层全部改经 `taskStore`；② `TaskTree` 父子结构一致（TC-8.10）；③ `MoveTask` 打点断言任务写先于需求写（TC-8.11）；④ rollup 推导结果一致（TC-8.8）；⑤ `npx tsc --noEmit` 通过 |
| t10 | （落库后回填） | 读方改造 D：门禁、查询与 Dive | FR-8 | S-13, S-14 + `src/application/{internal,query}/*`、`dive/idle-capture-actions.ts`、`gate/handlers/h3-inject.ts` | implement | backend | t6 | M | ① 全部改经 `taskStore`；② RTM/覆盖门禁读到的任务键集一致（TC-8.9）；③ **全仓残留静态检查**：`grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks' src/` 命中数为 **0**（TC-8.12）；④ 类型检查通过 |
| t11 | （落库后回填） | 接线 Decompose：任务写入队列 | FR-1 | I-9 + `src/application/use-cases/Decompose.ts` + `src/application/internal/{plan-landing,confirm-settle}.ts` | implement | backend | t5, t6 | S | ① `reqboard_decompose` 后 `queue.json` 生成（TC-9.1）；② 返回体含非空 `queue_file`；③ **台账不新增任务**（台账无 tasks 键）；④ 重复调用幂等（重复 id 不覆盖，文件 mtime 不变）；⑤ **两条落库路径都不得写台账**：拆分路径（`Decompose.ts:189`）与"计划批准即落库"路径（`confirm-settle.ts:276`） |
| t12 | （落库后回填） | 接线 ExecuteTask/MoveTask：读队列与顺序契约 | FR-2, FR-3 | I-10, I-11 + `src/application/use-cases/{ExecuteTask,MoveTask}.ts` | implement | backend | t11 | M | ① `task_run` 日志含 `Queue ready tasks:` 且父卡字段取自队列（TC-9.2）；② `task_move(to=done)` 后队列 `ready` 出现下游（TC-9.3）；③ **顺序契约**打点断言 `taskStore.mutate` 先于 `repo.mutate`（TC-8.11）；④ `task_run` 前后队列 md5 相同（只读）；⑤ 队列缺失时 task_move 不崩（TC-9.4） |
| t13 | （落库后回填） | 实现 v8→v9 迁移变换与 CLI | FR-7 | S-9, I-8, D-1~D-9 + `scripts/migrate-ledger.ts` | implement | backend | t4, t6 | M | ① `--dry-run` 台账 md5/mtime **不变**且无 queue.json 生成（TC-6.1/6.2）；② `--apply` 后台账 `schemaVersion===9`、无 `tasks`、`migrations` 末条 `{8,9}`（TC-6.3/6.4）；③ `--verify` 无差异退出码 0（TC-6.6）；④ `--rollback` 还原 v8 并清理本次生成的 queue.json（TC-6.8）；⑤ **顺序断言**：日志/打点证明先写全部 queue.json 再改台账（D-7 先于 D-8） |
| t14 | （落库后回填） | 迁移安全：白名单、幂等与 orphan | FR-7 | S-9, D-3/D-8 + `scripts/migrate-ledger.ts` + 迁移测试 | implement | backend | t13 | M | ① 注入白名单外字段改动 → 中止、退出码 1、台账未被替换（TC-6.7）；② 连续两次 `--apply` 第二次报 `already_v9` 且文件 mtime 不变（TC-6.5）；③ orphan 任务（requirementId 缺失/指向不存在需求）计入报告且**不迁移不串档**（TC-6.9）；④ 环依赖需求中止迁移但其余照常，报告列出（TC-6.10） |
| t15 | （落库后回填） | 迁移契约比对：587 条零字段丢失 | FR-7 | S-9 + 契约测试 + TC-7.x | test | backend | t14 | M | ① 逐字段深比对：`queue.tasks[i]` 去 `layer` 后 `deepEqual` 源 `ledger.tasks[i]`（TC-7.1）；② 点名断言 `lastRun`/`lastReport`/`revisions`/`statusHistory`/`executions`/`parentId`/`stageKind`/`implementation`/`context` 均已迁移（TC-7.2）；③ 465 条 `dependsOn` 全部可解析（TC-7.3）；④ 状态分布一致 done 556 / in_progress 7 / todo 24（TC-7.4）；⑤ 每份 queue.json 的 `requirement_id` 与目录一致（TC-7.5） |
| t16 | （落库后回填） | 看板实测回归（真实打开页面） | FR-8 | S-10 + `:13080` 实测 + TC-10.x | test | backend | t7, t8, t9, t10, t12, t14 | M | ① 启动 `:13080` 任务页，历史与在制任务**可见**且数量与迁移后一致（TC-10.1）；② 甘特/阶段视图正常渲染，无空白无 500（TC-10.2）；③ 需求详情任务列表非空字段完整（TC-10.3）；④ 启动日志无 `LEDGER_REQUIRES_MIGRATION` 与未捕获异常（TC-10.4）；⑤ 本需求自身任务可见（TC-10.5）；⑥ 留页面截图路径作证据，**禁止以 curl 200 代替** |
| t17 | （落库后回填） | 端到端验收与文档同步 | FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 | TC 全量 + `docs/architecture/` 对应章节 | test | doc | t15, t16 | M | ① 端到端脚本（新建测试需求 → 拆分 → 队列生成且台账无新任务 → 推进 → ready 更新）退出码 0；② `pnpm build` 退出码 0；③ `npx vitest run apps/web/tests/plugin-schema.smoke.test.ts` 通过；④ 归档申报的 `manual_updates` 章节已实际写入且 `wiki_probe.py` 死链 0；⑤ 提交可复核证据清单（命令 + 输出摘要 + 队列文件路径 + 页面截图路径） |

- 一个任务只干一件事，标题动词开头。
- **落点** = 覆盖对照里出现过的编号 + 具体文件路径（无"相关模块"式写法）。
- 工作量口径：S = 半天内 / M = 1~2 天 / L = 3 天以上。**本表无 L**（t13/t14 已把迁移拆成"变换+CLI"与"安全护栏"两卡）。
- 文件写冲突规避：t4→t5 同包不同文件；t7‖t8‖t9‖t10 四类读方文件集互不重叠；
  t13→t14→t15 同改迁移脚本与契约测试，靠依赖串行。
  ⚠️ **t10 与 t11 的落点原划错，已勘误**：`src/application/internal/` 不是纯读方目录 ——
  `plan-landing.ts:121 ledger.tasks.push(...records)` 是全仓**唯一真正写任务**的地方（`:76` 为
  `repo.mutate('task-created')`），且有**两个调用方**：`Decompose.ts:189`（拆分）与
  `confirm-settle.ts:276`（"计划批准即落库"）。故 `internal/{plan-landing,confirm-settle,rollup}.ts`
  三个文件从 t10 让给 t11/t9，**整段任务写路径归同一实施者**，避免"改一半 → v9 台账已无 tasks 键
  → 任务静默消失"。t10 保留 `internal/` 其余文件（RTM/门禁/校验等读方）。

---

## 覆盖对照

| 需求条款 | 接口（interfaces） | 页面/模块（architecture 改动清单） | 测试用例（test-cases） | 接收任务 | 完整性 |
|---|---|---|---|---|---|
| FR-1 队列作为任务主存储 | I-1, I-2, I-3, I-9 （4） | S-1, S-2, S-4, S-5, S-12 （5） | TC-1.1, TC-1.2, TC-3.1, TC-4.1, TC-9.1 （5） | t1, t2, t4, t5, t11 （5） | ✅ |
| FR-2 执行从队列读取父卡 | I-1, I-10 （2） | S-5, S-12 （2） | TC-4.6, TC-9.2 （2） | t5, t12 （2） | ✅ |
| FR-3 状态更新在队列实现 | I-1, I-11 （2） | S-5, S-12 （2） | TC-4.3, TC-8.11, TC-9.3 （3） | t5, t12 （2） | ✅ |
| FR-4 原子写入 | I-2 （1） | S-4 （1） | TC-3.5, TC-3.6, TC-11.4 （3） | t4 （1） | ✅ |
| FR-5 数据校验与版本兼容 | I-4 （1） | S-3 （1） | TC-2.1, TC-2.2, TC-2.3, TC-2.4, TC-2.5, TC-2.6, TC-2.8, TC-2.11 （8） | t3 （1） | ✅ |
| FR-6 台账 schema v8→v9 | I-5, I-6, I-7 （3） | S-6, S-7, S-8 （3） | TC-5.1, TC-5.2, TC-5.3, TC-5.6 （4） | t6 （1） | ✅ |
| FR-7 历史任务迁移 | I-8 （1） | S-9 （1） | TC-6.1, TC-6.3, TC-6.4, TC-6.5, TC-6.7, TC-6.8, TC-7.1, TC-7.2, TC-7.3, TC-7.4 （10） | t13, t14, t15 （3） | ✅ |
| FR-8 读方改造 | I-12, I-13 （2） | S-10, S-11, S-13, S-14 （4） | TC-8.1, TC-8.5, TC-8.8, TC-8.12, TC-9.5, TC-10.1, TC-10.2, TC-10.3 （8） | t7, t8, t9, t10, t16 （5） | ✅ |
| **合计** | **16 接口引用**（I-1~I-13 全覆盖） | **22 模块引用**（S-1~S-14 全覆盖） | **45 用例引用** | **17 任务** | **8/8 条款有主** |

**场景（UC）覆盖对照**（逐条认领，无超范围设计）：

| 场景 | 对应条款 | 接收任务 | 说明 |
|---|---|---|---|
| UC-1 拆分生成队列 | FR-1 | t5, t11 | 主流程 |
| UC-2 执行取父卡 | FR-2 | t5, t12 | 主流程 |
| UC-3 状态推进解锁 | FR-3 | t5, t12 | 主流程（含顺序契约） |
| UC-4 并发写同需求 | FR-3 | t4, t5 | 缓存与 last-write-wins |
| UC-5 队列损坏容错 | FR-4 | t4 | 隔离与降级 |
| UC-6 看板查看任务 | FR-8 | t7, t16 | **P0 最高风险** |
| UC-7 数据自动校验 | FR-5 | t3, t4, t5 | 三个卡点 |
| UC-8 一次性迁移 | FR-7 | t13, t14, t15 | 主流程 |
| UC-9 迁移回滚 | FR-7 | t13 | `--rollback` |

**校验规则（V）覆盖对照**：

| 规则 | 接收任务 | 测试用例 |
|---|---|---|
| V-1 必填字段完整性 | t3 | TC-2.1 |
| V-2 标识唯一性 | t3 | TC-2.2 |
| V-3 引用完整性 | t3 | TC-2.3, TC-2.4 |
| V-4 层级一致性 | t3 | TC-2.5 |
| V-5 ready 双向一致性 | t3, t5 | TC-2.6, TC-2.7 |
| V-6 无环性 | t2, t3 | TC-1.3, TC-2.8 |

**迁移步骤（D）覆盖对照**：

| 步骤 | 接收任务 | 步骤 | 接收任务 |
|---|---|---|---|
| D-1 读台账 | t13 | D-6 校验 | t13, t15 |
| D-2 备份 | t13 | D-7 写队列（先） | t13 |
| D-3 分组 / orphan | t14 | D-8 台账变换（后） | t13, t14 |
| D-4 构造 QueueFile | t13 | D-9 原子替换 | t13 |
| D-5 拓扑分层 | t13, t15 | R-1~R-4 回滚 | t13 |

---

## 依赖图（批次）

```
批次1:  t1
批次2:  t2, t3
批次3:  t4
批次4:  t5
批次5:  t6
批次6:  t7, t8, t9, t10      （四类读方文件集互不重叠，可并行）
批次7:  t11
批次8:  t12, t13
批次9:  t14
批次10: t15, t16
批次11: t17
```

- 关键路径：t1 → t2 → t4 → t5 → t6 → t7 → t11 → t12 → t16 → t17
- 可并行：t2‖t3、t7‖t8‖t9‖t10、t12‖t13、t15‖t16

---

## 覆盖完整性规则（自检）

1. **每行三格不许空**：8 行 FR 的接口/模块/用例三格均非空 ✅
2. **反向也要查**：I-1~I-13 全被认领；S-1~S-14 全被认领；UC-1~UC-9 全有归属；
   V-1~V-6 全有归属；D-1~D-9 与 R-1~R-4 全有归属 ✅
3. **每个 FR 必须有人接**：FR-1~FR-8 全部有接收任务，无孤儿条款 ✅

---

## 风险、顺序纪律与不做项

**三条硬顺序纪律（违反会静默丢数据）**：

1. **迁移先写队列、再改台账**（D-7 先于 D-8，t13 断言）。反序会产生"台账已无任务、队列还没生成"的
   **双向丢失**态。
2. **运行期先改任务、再改需求**（`taskStore.mutate` 先于 `repo.mutate`，t12 打点断言）。反序会产生
   "需求已验收但任务未完成"的悬空态。
3. **台账 v9 与读方改造必须同批上线**（t6 与 t7~t10 之间不得中间发版）。v9 台账 + 旧读方 = 界面空白。

**已知风险**：

| 风险 | 影响 | 缓解 | 承接任务 |
|---|---|---|---|
| 看板任务页/甘特空白（**最高**） | 本 GUI 任务视图不可用 | 迁移与读方同批；`:13080` 真实开页面验收 | t16 |
| 字段少迁（如 `lastRun`） | 子卡凭证门静默失效 | 逐字段深比对 + 点名断言 | t15 |
| 依赖 id 断链 | ready 推导错误 | V-3 + 465 条 dependsOn 全量断言 | t15 |
| 台账被写坏 | 82 条需求记录受损 | 备份 + 白名单 + 原子替换 | t13, t14 |
| 读方改造卡住 | 工期超预算 | 保留「内存聚合」回退路径（不丢数据） | t9, t10 决策点 |

**诚实申报的两个边界**：
1. **回滚窗口有限**：`--rollback` 只能还原台账备份；迁移后在 v9 上**新产生**的任务不在备份内，
   回滚会丢这部分。回滚窗口限于"迁移完成、尚未投产新拆分"期间。
2. **自举**：本需求自身的 17 张卡由 t13/t14 迁移一并迁入队列；不依赖"本需求再拆一次"。

**本轮不做**（对应 requirement.md「边界（不做什么）」）：
队列 DAG 图形 UI、并行调度引擎、断点续传、跨需求依赖、双写兼容、分布式锁、取消台账。

---

## 变更历史

- 2026-09-27 21:40 - 初始拆分计划（8 卡，队列为派生副本）
- 2026-09-28 00:20 - **范围变更重写**：8 卡 → **17 卡**；新增台账 v9 去 tasks（t6）、
  读方改造四卡（t7/t8/t9/t10）、迁移变换与 CLI（t13）、迁移安全护栏（t14）、契约比对（t15）、
  看板实测回归（t16）；全部任务控制在 S/M（无 L）；补三条硬顺序纪律与两个诚实边界（investor w-3936d77f）
- 2026-09-27 latest  - **实施期勘误（不改变卡数/依赖/覆盖，只更正落点与验收口径）**（w-3936d77f）：
  · t11 落点补全：真正写任务的是 `internal/plan-landing.ts:121`，且有第二个调用方
    `confirm-settle.ts:276`（计划批准即落库）。原表只写 `Decompose.ts`，照此实施会让批准路径
    继续写 `ledger.tasks` → 在 v9 台账（已无该键）上**静默丢任务**。已把
    `internal/{plan-landing,confirm-settle,rollup}.ts` 从 t10 让给 t9/t11，并给 t11 增补验收⑤。
  · t2 验收①路径更正：`src/domain/queue/topology.test.ts` → `tests/queue/topology.test.ts`
    （本仓 `vitest.config.ts` 的 include 限定 `tests/**/*.test.ts`，原路径不可执行；未改配置）。
  · 字段口径更正：`design/queue-schema.md` §2.2 表 5 处与 `protocol.ts:TaskRecord` 不符，已修正
    （详见该文勘误段）；权威 = `TaskRecord` 37 字段（19 必填 + 18 可选）+ `layer`。
