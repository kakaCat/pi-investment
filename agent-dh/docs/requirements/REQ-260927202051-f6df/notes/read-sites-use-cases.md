# 读方站点清单·用例层（task-11 / t9·t11·t12 前置只读调研）

> 卡片：team `task-11`（只读先行）｜产出唯一写域：本文件
> 工作目录基准：`packages/web/dsh-pmboard/`｜采集时点：2026-09-27（源码当时状态）
> 口径：`docs` 目录是 `packages/web/dsh-pmboard/docs -> ../../../docs` 符号链接，两路径同一 inode。
> 说明：本卡**只读** src/，未修改任何 src 文件；本文件是 t9/t11/t12 改造的核对底稿。

---

## 0. 采集命令与计数（可复现）

```bash
cd /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks\|\.tasks' \
  src/application/use-cases/ src/application/query/ | wc -l
# → 61
grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks\|\.tasks' src/application/use-cases/ | wc -l
# → 53
grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks\|\.tasks' src/application/query/ | wc -l
# → 8
```

**清单条数 = grep 实际命中数 = 61**（下表逐条对应，无遗漏、无凑数）。
其中 **台账相关（需改造）= 51**，**非台账（`a.tasks` / `plan.tasks` 入参语义，不改）= 10**。
`query/` 8 条属 reader-http 写域（t-8d4af7，task-12 成员），本表仅登记、不实施。

> 端口口径：`deps.taskStore`（`TaskStore`，interfaces.md I-1，落点 task-9 的 `t-bc1ba6` → `src/application/ports.ts` + `src/repositories/QueueTaskStore.ts`）。
> 「目标调用」列的 `get` = `await deps.taskStore.get(taskId)`；`list` = `await deps.taskStore.listByRequirement(reqId)`；
> `mutate` = `deps.taskStore.mutate(reqId, (tasks, ctx) => …)`（回调同步，`ctx.recompute()` 重算派生视图）。

---

## 1. 站点表（61 条）

| # | 站点（文件:行号） | 当前取值表达式 | 语义 | 目标调用 | 归属卡 |
|---|---|---|---|---|---|
| 1 | `src/application/use-cases/MoveTask.ts:73` | `snap.tasks.find(t => t.id === taskId)` | 任务存在性 + 窗口越权预检（只读前置） | `get(taskId)` | t9（t12 复检） |
| 2 | `src/application/use-cases/MoveTask.ts:86` | `ledger.tasks.find(t => t.id === taskId)` | `repo.mutate('task-moved')` 内取任务（待改状态） | `mutate`（回调入参 `tasks`） | t9 → t12 |
| 3 | `src/application/use-cases/MoveTask.ts:90` | `roleOf(task, ledger.tasks)` | 角色判定（父卡/子卡/存量卡，父子树） | `mutate`（回调入参 `tasks`） | t9 → t12 |
| 4 | `src/application/use-cases/MoveTask.ts:95` | `runningParents(ledger.tasks, task.requirementId)` | 同需求在跑父卡并发上限判据 | `mutate`（回调入参 `tasks`） | t9 → t12 |
| 5 | `src/application/use-cases/MoveTask.ts:160` | `ledger.tasks.filter(t => createdIds.includes(t.id))` | 懒展开新建子卡的回收（返回体投影） | `mutate` 返回值（改动任务集） | t9 → t12 |
| 6 | `src/application/use-cases/MoveTask.ts:164` | `(result.changed.tasks ?? []).find(...)` | 变更集读取（返回体投影 `moved.status/version`） | `mutate` 返回值 | t12（顺序契约） |
| 7 | `src/application/use-cases/SubmitVerification.ts:94` | `snapshot.tasks.filter(...).map(t => t.id)` | 文档完整性检查的 `taskIds` 输入 | `list(target.id)` | t9 |
| 8 | `src/application/use-cases/SubmitVerification.ts:131` | `for (const t of snapshot.tasks)` | 验收项「怎么验」扫描（`checkHowToVerify`） | `list(target.id)` | t9 |
| 9 | `src/application/use-cases/SubmitVerification.ts:177` | `ledger.tasks.filter(...)` | 验收单 items 生成（`repo.mutate` 内读任务） | 先 `list(...)` 取好再传入 mutate | t9 |
| 10 | `src/application/use-cases/SubmitVerification.ts:230` | `deps.repo.snapshot().tasks.filter(...)` | `verification.md` 渲染的任务映射（title/acceptance） | `list(target.id)` | t9 |
| 11 | `src/application/use-cases/SubmitVerification.ts:271` | `ledgerNow.tasks.filter(...)` | 验收/rollup 阻塞判定 | `list(target.id)` | t9 |
| 12 | `src/application/use-cases/AdvanceChain.ts:139` | `ledger.tasks.find(t => t.id === parentId)` | 自动链父卡开工（`advance-open-parent` 内） | `mutate` | t9 |
| 13 | `src/application/use-cases/AdvanceChain.ts:141` | `ledger.tasks.filter(...status === 'in_progress').length` | 并行父卡上限计数 | `mutate` | t9 |
| 14 | `src/application/use-cases/AdvanceChain.ts:165` | `(result.changed.tasks ?? []).length === 0` | OPEN_PARENT 的 noop 判定 | `mutate` 返回值 | t9 |
| 15 | `src/application/use-cases/AdvanceChain.ts:175` | `ledger.tasks.find(t => t.id === parentId)` | 父卡收尾（`advance-finalize-parent` 内） | `mutate` | t9 |
| 16 | `src/application/use-cases/AdvanceChain.ts:177` | `subtasksOf({ tasks: ledger.tasks }, parent.id)` | 子卡收尾条件（父子树） | `mutate` | t9 |
| 17 | `src/application/use-cases/AdvanceChain.ts:196` | `(result.changed.tasks ?? []).length === 0` | FINALIZE_PARENT 的 noop 判定 | `mutate` 返回值 | t9 |
| 18 | `src/application/use-cases/AdvanceChain.ts:275` | `selectAdvanceEvent({ tasks: snap.tasks }, …)` | **链事件选择（核心读点）** | `list(requirementId)` | t9 |
| 19 | `src/application/use-cases/AdvanceChain.ts:277` | `hasOpenWork({ tasks: snap.tasks }, …)` | 停滞熔断判据（有活没活） | `list(requirementId)` | t9 |
| 20 | `src/application/use-cases/AdvanceChain.ts:329` | `ledger.tasks.find(x => x.id === subId)` | 失败退回后的任务回读（`subtask-rollback` 内） | `mutate` | t9 |
| 21 | `src/application/use-cases/AdvanceChain.ts:489` | `ledger.tasks.filter(...parentId === undefined...)` | `progressOf` 父卡进度统计 | 入参改由调用方传队列任务 | t9 |
| 22 | `src/application/use-cases/AdvanceChain.ts:490` | `ledger.tasks.filter(...parentId !== undefined...)` | `progressOf` 子卡进度统计 | 入参改由调用方传队列任务 | t9 |
| 23 | `src/application/use-cases/MoveRequirement.ts:39` | `taskCompletenessGap(req0, snap.tasks, to)` | 需求推进的任务完整性预检（rollup 推导） | `list(req0.id)` | t9 |
| 24 | `src/application/use-cases/MoveRequirement.ts:50` | `taskCompletenessGap(req, ledger.tasks, to)` | `repo.mutate` 内复查（防并发漂移） | 先 `list(...)` 取好，在 mutate 前复查 | t9 |
| 25 | `src/application/use-cases/ConfirmArtifact.ts:153` | `req.plan.tasks.length` | 计划任务表条数（评论文案）——**非台账** | 不改 | — |
| 26 | `src/application/use-cases/ReportTask.ts:49` | `snapshot.tasks.find(t => t.id === taskId)` | 任务存在性 + 越权校验 | `get(taskId)` | t9 |
| 27 | `src/application/use-cases/ReportTask.ts:134` | `ledger.tasks.find(x => x.id === task.id)` | `lastReport` 落库（`requirement-updated` mutate 内） | `mutate` | t9 |
| 28 | `src/application/use-cases/TaskTree.ts:133` | `snap.tasks.filter(t => t.requirementId === requirementId)` | **父子树构建（TC-8.10 判据源）** | `list(requirementId)` | t9 |
| 29 | `src/application/use-cases/TaskTree.ts:142` | `snap.tasks.find(t => t.id === parentId)` | 跨需求 `parent_id` 探测（错误分支） | `get(parentId)` | t9 |
| 30 | `src/application/use-cases/SubtaskTeamRun.ts:90` | `deps.repo.snapshot().tasks.filter(t => t.parentId === parent.id)` | 同队子卡清单（建 team task 用） | `list(parent.requirementId)` | t9 |
| 31 | `src/application/use-cases/SubtaskTeamRun.ts:113` | `ledger.tasks.find(x => x.id === s.id)` | `teamTaskId` 回写（`team-task-link` mutate 内） | `mutate` | t9 |
| 32 | `src/application/use-cases/SubtaskTeamRun.ts:146` | `deps.repo.snapshot().tasks.find(...)?.lastReport` | Worker 产出回读（台账是唯一结果通道） | `get(task.id)` | t9 |
| 33 | `src/application/use-cases/IsolateNodeContext.ts:221` | `deps.repo.snapshot().tasks.find(t => … isInProgressTask(t))` | 当前在制任务卡（节点输入包） | `list(requirement.id)` + 筛选 | t9 |
| 34 | `src/application/use-cases/ExecuteTask.ts:151` | `snap.tasks.find(t => t.id === input.subtaskId)` | 子卡存在性（UC-2 入口） | `get(input.subtaskId)` | t9 → t12 |
| 35 | `src/application/use-cases/ExecuteTask.ts:154` | `snap.tasks.find(t => t.id === task.parentId)` | **父卡字段取数（acceptance/implementation/context/dependsSummary）** | `get(task.parentId)` | t9 → t12 |
| 36 | `src/application/use-cases/ExecuteTask.ts:269` | `snap.tasks`（`detectCrossCardOverwrite` 入参） | 跨卡覆盖检测的同需求任务集 | `list(task.requirementId)` | t9 |
| 37 | `src/application/use-cases/ExecuteTask.ts:291` | `ledger.tasks.find(x => x.id === task.id)` | `lastRun`/`lastReport`/开工落库（`subtask-ran` mutate 内） | `mutate` | t9 → t12 |
| 38 | `src/application/use-cases/ExecuteTask.ts:337` | `ledger.tasks.find(x => x.id === task.id)` | done 转移（`subtask-completed` mutate 内） | `mutate` | t9 → t12 |
| 39 | `src/application/use-cases/ExecuteTask.ts:351` | `ledger.tasks.find(x => x.id === task.id)` | 失败收尾（`subtask-failed` mutate 内） | `mutate` | t9 → t12 |
| 40 | `src/application/use-cases/ExecuteTask.ts:363` | `deps.repo.snapshot().tasks.find(...)?.teamTaskId` | 团队任务重开定位 | `get(task.id)` | t9 |
| 41 | `src/application/use-cases/Decompose.ts:27` | `a.tasks` | 入参校验——**非台账** | 不改 | — |
| 42 | `src/application/use-cases/Decompose.ts:70` | `snapshot.tasks.filter(t => t.requirementId === target.id …)` | **拆分幂等守卫（已有任务判据）** | `list(target.id)` | t11 |
| 43 | `src/application/use-cases/Decompose.ts:87` | `target.plan?.tasks ?? []` | 已批准计划任务表——**非台账** | 不改 | — |
| 44 | `src/application/use-cases/Decompose.ts:99` | `a.tasks` | 入参校验——**非台账** | 不改 | — |
| 45 | `src/application/use-cases/Decompose.ts:106` | `normalizePlanTasks(a.tasks)` | 入参创作路径——**非台账** | 不改 | — |
| 46 | `src/application/use-cases/Decompose.ts:120` | `a.tasks !== undefined` | 入参 key 集合比对——**非台账** | 不改 | — |
| 47 | `src/application/use-cases/Decompose.ts:122` | `(a.tasks as unknown[]).map(...)` | 入参 key 提取——**非台账** | 不改 | — |
| 48 | `src/application/use-cases/Decompose.ts:169` | `...((a.tasks as unknown[] \| undefined) ?? [])` | RTM 覆盖输入并集——**非台账** | 不改 | — |
| 49 | `src/application/use-cases/AmendTaskAcceptance.ts:53` | `snapshot.tasks.find(t => t.id === taskId)` | 任务存在性 + 越权校验 | `get(taskId)` | t9 |
| 50 | `src/application/use-cases/AmendTaskAcceptance.ts:61` | `ledger.tasks.find(x => x.id === taskId)` | `acceptance` 改写（`task-amended` mutate 内） | `mutate` | t9 |
| 51 | `src/application/use-cases/AmendTaskAcceptance.ts:67` | `result.changed.tasks === undefined \|\| …length === 0` | 写入结果判定（`REQBOARD_STORE_INCONSISTENT`） | `mutate` 返回值 | t9 |
| 52 | `src/application/use-cases/SubmitArtifact.ts:171` | `a.tasks === undefined ? [] : normalizePlanTasks(a.tasks)` | 计划入参任务表——**非台账** | 不改 | — |
| 53 | `src/application/use-cases/AcceptSheet.ts:230` | `(result.changed.tasks ?? []).map(t => t.id)` | 返工任务 id（裁决写回任务状态） | `mutate` 返回值 | t9 |
| 54 | `src/application/query/QueryState.ts:66` | `clauseReceiveStatus(roots, …, ledger.tasks, …)` | RTM 条款接收状态（读方投影） | `list(boundReq.id)` | t-8d4af7（reader-http） |
| 55 | `src/application/query/QueryState.ts:80` | `ledger.tasks.filter(...)` | 状态 RTM 任务集 | `list(boundReq.id)` | t-8d4af7（reader-http） |
| 56 | `src/application/query/QueryState.ts:106` | `ledger.tasks.filter(...)` | 三级追溯链覆盖统计 | `list(boundReq.id)` | t-8d4af7（reader-http） |
| 57 | `src/application/query/QueryStageDetail.ts:183` | `ledger.tasks.filter(t => t.requirementId === req.id)` | 拆分阶段任务 DAG | `list(req.id)` | t-8d4af7（reader-http） |
| 58 | `src/application/query/QueryStageDetail.ts:192` | `req.plan?.tasks ?? []` | 计划任务表回显——**非台账** | 不改 | — |
| 59 | `src/application/query/QueryStageDetail.ts:206` | `ledger.tasks.filter(...)` | 实施阶段执行记录视图 | `list(req.id)` | t-8d4af7（reader-http） |
| 60 | `src/application/query/QueryRequirementToken.ts:43` | `for (const t of ledger.tasks)` | 快照缺口检测（token 追溯） | `list(req.id)` | t-8d4af7（reader-http） |
| 61 | `src/application/query/QueryRequirementToken.ts:56` | `for (const t of ledger.tasks)` | token 执行行投影 | `list(req.id)` | t-8d4af7（reader-http） |

**计数核对**：台账相关 51（第 1–24、26–40、42、49–51、53–57、59–61 行）+ 非台账 10（第 25、41、43–48、52、58 行）= 61 ✅

---

## 2. 顺序契约打点位置（t12 / TC-8.11）

**纪律**：运行期 `taskStore.mutate` 必须先于 `repo.mutate`；反序 = 「需求已验收但任务未完成」悬空态（decomposition.md 硬顺序纪律 ②、interfaces.md I-11、architecture.md「一致性模型」）。

| 锚点 | 站点（文件:行号） | 改造前 | 改造后 | 打点 |
|---|---|---|---|---|
| ① 主锚点 | `MoveTask.ts:85` | `await deps.repo.mutate('task-moved', …)` —— **同一 mutate 内既改任务（:86）又 applyTaskRollup 改需求（:155-161）** | 拆两段：`await deps.taskStore.mutate(reqId, …)`（承接 :86-160 全部任务写）→ **再** `await deps.repo.mutate('requirement-rolled-up', …)`（只跑 :155-161 `applyTaskRollup`） | 在两调用处注入序列探针，断言执行序为 `['taskStore','repo']`（TC-8.11 直接判据） |
| ② 跨函数锚点 | `ExecuteTask.ts:290` `repo.mutate('subtask-ran')`、`ExecuteTask.ts:336` `repo.mutate('subtask-completed')`、`ExecuteTask.ts:350` `repo.mutate('subtask-failed')` | 三处 `repo.mutate` **只写任务**（`return { tasks: [t] }`） | 三处全部改 `taskStore.mutate`；需求侧 rollup 不由本文件承担 | — |
| ③ 跨函数顺序验证点 | `AdvanceChain.ts:243-244`（`runSelection` 分派：`RUN_SUBTASK` → `ExecuteTask`；`ROLLUP` → `rollupStep`）与 `AdvanceChain.ts:226`（`rollupStep` 的 `repo.mutate('advance-rollup')`） | 任务写与需求写在同/异 mutate 中混排 | `RUN_SUBTASK`（`taskStore.mutate`）必须先于 `ROLLUP`（`repo.mutate('advance-rollup')`） | 断言序列中 `taskStore` 索引 < `advance-rollup` 索引 |
| ④ 自动链任务写锚点 | `AdvanceChain.ts:137`（`advance-open-parent` 改任务）、`AdvanceChain.ts:174`（`advance-finalize-parent` 改任务）、`AdvanceChain.ts:326`（`subtask-rollback` 改任务） | 任务写在 `repo.mutate` 内 | 三处改 `taskStore.mutate`；随后 `AdvanceChain.ts:226` 需求 rollup 才可写 | 同上序列断言 |

**要求**：t12 的顺序契约必须有**运行期打点证据**（记录调用次序的断言），不接受口头声明或静态 grep。

---

## 3. 同文件串行顺序（t9 → t11 → t12）

**结论：本成员在 `src/application/use-cases/` 上严格串行 t9 → t11 → t12，任两张卡不得并行改同一文件。**

| 文件 | t9（读方改造 C：改经 taskStore） | t11（Decompose 写队列） | t12（ExecuteTask/MoveTask 读队列 + 顺序契约） |
|---|---|---|---|
| `Decompose.ts` | 站点 #42（幂等守卫改 `list`） | 站点 #42 复检 + **新增写路径接线**（见 §4 风险） | — |
| `ExecuteTask.ts` | 站点 #34–#40 | — | #34/#35（父卡与 ready 取自队列）、#37–#39（写经 taskStore） |
| `MoveTask.ts` | 站点 #1–#5 | — | #6 + §2 锚点①（拆两段 + 打点） |
| `AdvanceChain.ts` | 站点 #12–#22（读 + 内部写全部改 taskStore） | — | #18/#19（ready 日志）与 §2 锚点③④ |

**次序理由**：
1. t9 先把四文件的**读点**统一换到 `taskStore`（含 `repo.mutate` 回调内的同步读点抽到 mutate 外）；
2. t11 只动 `Decompose.ts`（+ 见 §4），必须在 t9 之后——否则 t9 会覆盖 t11 的写路径改动；
3. t12 只动 `ExecuteTask.ts` / `MoveTask.ts`，且引入**顺序契约**（把单次 `repo.mutate` 拆成两次调用），必须在 t9 的读改造与 t11 的写接线都稳定后进行。

**跨成员边界**：`src/application/query/` 站点 #54–#61 归 reader-http 的 t-8d4af7（task-12）；本成员不碰。t9 卡描述写的是「用例层全部改经 taskStore」，其验收 TC-8.8/8.10 的落点分别在 `internal/rollup.ts`（reader-http）与 `use-cases/TaskTree.ts`（本成员）——**rollup 那一半不在本成员写域**，需在 t9 验收时由 Lead 合并两侧证据。

---

## 4. 跨写域越界风险（需 Lead 裁决，勿自行扩范围）

**t11 的验收目标（`reqboard_decompose` 后生成 `queue.json`、台账不新增任务）无法仅靠 `src/application/use-cases/Decompose.ts` 达成。**

- `Decompose.ts:189` 只是**调用** `landPlanTasks(deps, {…})`（import 于 `Decompose.ts:21`）；
- **任务真正写入台账的位置在 `src/application/internal/plan-landing.ts:76`**（`deps.repo.mutate('task-created', …)`），落库动作是 `plan-landing.ts:121` `ledger.tasks.push(...records)`，随后 `plan-landing.ts:141` `applyTaskRollup` 改需求；
- 且该落库编排有**第二个调用方** `src/application/internal/confirm-settle.ts:276`（「计划批准即落库」路径）——若只改 `Decompose.ts`，批准路径仍会写台账 `tasks`（v9 台账已无该键 → 静默丢任务）。
- `src/application/internal/` 属 reader-http 写域（task-12 / t-8d4af7）。

**三个候选处置（请 Lead 选定）**：
1. 把 `internal/plan-landing.ts` 纳入本成员写域（t11 改它，reader-http 让出），改 `landPlanTasks` 内 `repo.mutate` 为 `taskStore.createMany`；
2. 保持写域不变，由 reader-http 在 t-8d4af7 内改 `plan-landing.ts`，本成员只在 `Decompose.ts` 传参/收 `queue_file`；
3. 新增一张卡专门承接 `plan-landing.ts` + `confirm-settle.ts` 两处调用方的队列化。

**在裁决前，t11 不实施 src/ 改动。**

### 4.1 幂等断言落点（纪律 ②，t11 验收）
- 幂等键 = `TaskRecord.id`；`TaskStore.createMany` 契约已定「已存在 id 跳过、不覆盖」（interfaces.md I-1）。
- 断言点：`Decompose.ts:189` 连续两次调用（或 §4 处置后的落库点），第二次后 `docs/requirements/<REQ>/queue.json` 的 **mtime 不变** + 任务数不变；台账落盘 JSON 无 `"tasks"` 键。

---

## 5. 同步 → 异步改造点（t9/t12 必须显式处理）

`repo.mutate` 的回调是**同步契约**（返回 `LedgerChange`，`await` 会让模块无法被 esbuild/vite 解析，见 `plan-landing.ts:155-157` 注释），而 `taskStore.*` 都是 Promise。因此**回调内的任务读点不能原地 `await`**，必须二选一：改走 `taskStore.mutate`（回调同步、入参即 `tasks` 数组），或把读点**提到 mutate 之前**（先 `list`/`get` 再进 `repo.mutate`）。

位于 `repo.mutate` 回调内、需按此处理的站点（**若就地 await 会静默破坏写路径**）：

| 站点 | 所在 mutate |
|---|---|
| `MoveTask.ts:86, 90, 95, 160` | `MoveTask.ts:85` `'task-moved'` |
| `SubmitVerification.ts:177` | `SubmitVerification.ts:172` `'requirement-updated'` |
| `AdvanceChain.ts:139, 141, 177, 329` | `AdvanceChain.ts:137 / :174 / :326` |
| `ReportTask.ts:134` | `ReportTask.ts:130` `'requirement-updated'` |
| `AmendTaskAcceptance.ts:61` | `AmendTaskAcceptance.ts:60` `'task-amended'` |
| `MoveRequirement.ts:50` | `MoveRequirement.ts:44` `'requirement-moved'` |
| `ExecuteTask.ts:291, 337, 351` | `ExecuteTask.ts:290 / :336 / :350` |
| `Decompose.ts:70` 读 → 落库写 | 读点已在 mutate 外（`:70`），落库写见 §4 |

---

## 6. 变更历史

- 2026-09-27 - 初始版本（task-11 只读调研，reader-uc / w-3936d77f 的 teammate）：
  grep 命中 61 条（use-cases 53 + query 8）逐条登记；台账相关 51 / 非台账 10；
  顺序契约打点锚点 ①`MoveTask.ts:85`（含 :155-161）②`ExecuteTask.ts:290/336/350` ③`AdvanceChain.ts:243-244` vs `:226` ④`AdvanceChain.ts:137/174/326`；
  同文件串行 t9→t11→t12；登记 §4 跨写域风险（`internal/plan-landing.ts:76/121`，含第二调用方 `internal/confirm-settle.ts:276`）。
