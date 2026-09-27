# 读方站点清单·看板/路由/工具/门禁（task-10 只读先行）

> **卡**：task-10（owner: reader-http，窗口 w-3936d77f）
> **目的**：t7/t8/t10 改造前，把「谁在读台账 tasks」变成可核对的机器清单——避免改漏一处导致看板空白（本需求最高风险）。
> **纪律**：本卡只读 `src/`，未修改任何 src 文件；唯一产出即本文件。
> **基准**：`packages/web/dsh-pmboard/`，扫描时点 2026-09-27。

---

## 0. 复现命令与计数（验收锚点）

```bash
# 与 task-10 description 逐字一致（宽模式，含裸 .tasks）
grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks\|\.tasks' \
  src/http/ src/tools/ src/application/internal/ src/application/query/ \
  src/application/dive/ src/application/gate/ | wc -l
# → 77

# 唯一文件数
grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks\|\.tasks' \
  src/http/ src/tools/ src/application/internal/ src/application/query/ \
  src/application/dive/ src/application/gate/ | cut -d: -f1 | sort -u | wc -l
# → 29
```

**清单条数 = 77 = grep 实际命中数**（下表 S-01..S-77 逐行对应，无增无减）。

分类计数（合计 77，见每行「类」列）：

| 类 | 含义 | 条数 | 是否本次迁移目标 |
|---|---|---|---|
| **A** | 台账任务直读/直写（`ledger.tasks` / `snap.tasks` / `snapshot().tasks`） | **54** | ✅ 必须改经 taskStore |
| **B** | `mutate` 返回值回读（`result.changed.tasks`，即 `LedgerChange.tasks`） | **11** | ✅ 必须由 taskStore 写返回值替代 |
| **C** | 纯函数入参 `view.tasks`（`AdvanceView`） | **5** | ❌ 函数内部不改，改造其在调用方 |
| **D** | 纯函数入参 `input.tasks`（门禁入参） | **3** | ❌ 函数内部不改，改造其在调用方 |
| **E** | 计划任务表 `plan.tasks`（**非台账任务**） | **4** | ❌ 不迁移——改错此 4 处会让计划展示/拆分文档读空 |

> **写域裁定（2026-09-27 Lead 变更，见 §3.0）**：S-31~S-39、S-51~S-53、S-66 共 **13 条已划归 reader-uc（task-13）**。
> **reader-http 实际负责 = 77 − 13 = 64 条**（A 47 / B 6 / C 5 / D 3 / E 3）。
> 下表 77 行**保持全量不减**（这是只读调研的完整性证据），每行「类」列后以 `→UC` 标注归属。

> **类 E 的重要意义**：宽模式 grep 把 `req.plan?.tasks` 一并命中。若按字面「见 `.tasks` 就改」，
> 这 4 处会被误改成队列读取 → `requirements.ts:182` 的「已批准计划 N 个任务」恒为 0、
> `confirm-settle.ts:236`（批准计划→落库编排）直接失去数据源。**必须显式排除。**

### 目标调用速查（「目标调用」列的取值集合）

| 目标调用 | 适用 |
|---|---|
| `await taskStore.get(taskId)` | 按 id 取单卡（不存在 → undefined） |
| `await taskStore.listByRequirement(reqId)` | 取某需求全部任务（无队列 → `[]`，非错误） |
| `await taskStore.readQueue(reqId)` | 取队列全量（含 `edges/layers/ready`）；无文件 → undefined |
| `await taskStore.createMany(reqId, tasks)` | 批量落库（幂等：已存在 id 不覆盖） |
| `await taskStore.mutate(reqId, fn)` | 需求维度变更任务（原子写） |
| `taskStore.mutate(...)` 返回值 | 替代 `result.changed.tasks`（B 类） |
| 不迁移 | E 类（`plan.tasks`）/ C、D 类（纯函数内部） |

**⚠️ 方法名以 task-9 落地为准**（`src/application/ports.ts` / `QueueTaskStore.ts`，属 queue-core 写域，本卡只读）。
若端口方法与 design/interfaces.md I-1 有出入，以落地实现为准并回填本表。

---

## 1. 站点全表（S-01 – S-77）

| # | 站点（文件:行号） | 当前取值表达式 | 消费语义 | 目标调用 | 类 |
|---|---|---|---|---|---|
| S-01 | `src/http/routers/requirements.ts:182` | `plan.tasks.length` | 需求详情评论文案「已批准计划 N 个任务」 | **不迁移**（`RequirementRecord.plan.tasks`，计划任务表） | E |
| S-02 | `src/http/routers/requirements.ts:343` | `ledger.tasks.find(t => t.id === id)` | 给指定任务追加评论；找不到 → 404「任务 {id}」 | `await taskStore.get(id)`（取 requirementId）→ `taskStore.mutate(reqId, fn)` 写 comments | A |
| S-03 | `src/http/routers/requirements.ts:350` | `result.changed.tasks[0]?.id` | 响应体 `target`（req/task 评论共用 id 回执） | `taskStore.mutate(...)` 返回 `tasks[0].id` | B |
| S-04 | `src/http/routers/verdicts.ts:198` | `(result.changed.tasks ?? []).map(t => t.id)` | 验收裁决响应 `rework_tasks`（返工卡 id 列表） | `taskStore.mutate(...)` 返回的返工卡 | B |
| S-05 | `src/http/routers/verdicts.ts:200` | `(result.changed.tasks ?? []).length` | 响应 note 文案「生成 N 张返工任务」 | 同上（S-04 的同批返回值） | B |
| S-06 | `src/http/routers/stages.ts:46` | `ledger.tasks.map(t => ({ ...t }))` | **`GET /state` 全量任务数组**（看板首屏/甘特主数据源） | 跨需求队列聚合；**TaskStore 无 listAll → 契约缺口（见 §3.1）**；出口须剥离 `layer` | A |
| S-07 | `src/http/routers/stages.ts:49` | `readyTasks(ledger.tasks, r.id).map(t => t.id)` | 每需求 ready 任务 id 列表（client 调度提示） | `await taskStore.listByRequirement(r.id)` 后**仍用 `readyTasks(...)`**（保序，勿用 `queue.ready`） | A |
| S-08 | `src/http/routers/stages.ts:95` | `ledger.tasks.filter(t => t.requirementId === req.id)` | 需求摘要 `tasksDone/tasksActive/tasksTotal/percentage` | `await taskStore.listByRequirement(req.id)` | A |
| S-09 | `src/http/routers/stages.ts:137` | `for (const t of ledger.tasks)` | 会话进度锚点：按 `executions[].sessionId` 反查关联需求 | 全量队列任务（**同 S-06 缺口**） | A |
| S-10 | `src/http/routers/stages.ts:153` | `ledger.tasks.filter(t => t.requirementId === target.id)` | 会话进度条 total/done/active/byStatus + 任务列表 | `await taskStore.listByRequirement(target.id)` | A |
| S-11 | `src/http/routers/stages.ts:222` | `{ tasks: ledger.tasks }` | `assembleStageDetail` 入参（节点详情） | 先 `await taskStore.listByRequirement(id)`，再把 `{ tasks }` 传入（assembler 为**同步**，见 §4） | A |
| S-12 | `src/http/routers/stages.ts:245` | `{ tasks: ledger.tasks }` | `assembleStageOverview` 入参（全流程一览） | 同 S-11 | A |
| S-13 | `src/http/routers/stages.ts:279` | `{ tasks: ledger.tasks }` | `assembleRequirementToken` 入参（token 去向） | 同 S-11 | A |
| S-14 | `src/http/routers/stages.ts:286` | `ledger.tasks.filter(t => t.requirementId === req.id).flatMap(t => t.executions.map(e => e.sessionId))` | 注入窗口集合（injection `sharePct` 计算） | `await taskStore.listByRequirement(req.id)` 后同表达式 | A |
| S-15 | `src/http/routers/stages.ts:321` | `assembleRequirementMarks({ docs }, req, ledger.tasks)` | 需求侧接收标记（逐条条款「谁接了」） | `await taskStore.listByRequirement(req.id)` | A |
| S-16 | `src/http/routers/tasks.ts:86` | `assertDagAcyclic([...ledger.tasks, record], requirementId)` | 人工建卡前 DAG 环校验 | 进 `repo.mutate` 前 `await taskStore.listByRequirement(requirementId)`；环校验在回调内对该数组做（见 §4） | A |
| S-17 | `src/http/routers/tasks.ts:87` | `ledger.tasks.push(record)` | 看板人工建卡落库 | `await taskStore.createMany(requirementId, [record])` | A |
| S-18 | `src/http/routers/tasks.ts:107` | `ledger.tasks.find(t => t.id === id)` | task_move：定位任务 + 状态转移 + 执行段开闭 + rollup | `await taskStore.get(id)` 取 requirementId → `await taskStore.mutate(reqId, fn)` | A |
| S-19 | `src/http/routers/tasks.ts:149` | `result.changed.tasks[0]` | task_move 后取 movedTask（触发 RTM 同步 `syncRTMYamlWithSnapshot`） | `taskStore.mutate(...)` 返回值 | B |
| S-20 | `src/http/routers/tasks.ts:157` | `result.changed.tasks[0]` | **task_move 响应体**（逐字节相等验收点） | 同上；出口须剥离 `layer` | B |
| S-21 | `src/http/routers/tasks.ts:165` | `ledger.tasks.find(t => t.id === id)` | task_update：改卡字段（title/phase/dependsOn/blocked…） | `await taskStore.get(id)` → `await taskStore.mutate(reqId, fn)` | A |
| S-22 | `src/http/routers/tasks.ts:176` | `assertDagAcyclic(ledger.tasks, task.requirementId)` | 改 dependsOn 后的环校验 | 队列任务数组（同 S-16） | A |
| S-23 | `src/http/routers/tasks.ts:193` | `result.changed.tasks[0]` | **task_update 响应体** | `taskStore.mutate(...)` 返回值；剥离 `layer` | B |
| S-24 | `src/http/routes.ts:123` | `ledger.tasks.some(t => t.id === id)` | `mintId('task')` 任务 id 冲突去重 | `await taskStore.get(id) !== undefined`；**站点在 `src/http/routes.ts`，不在 t7 文件清单与 task-12 写域（见 §3.2）** | A |
| S-25 | `src/tools/RunStatusTool/RunStatusTool.ts:116` | `deps.repo.snapshot().tasks.filter(t => t.requirementId === requirementId)` | `queryRunStatus` 的 `getTasks` 回调（run 摘要/nextReady） | `await deps.taskStore.listByRequirement(requirementId)`（回调**已是 async**，无裂变） | A |
| S-26 | `src/tools/AdvanceTool/AdvanceTool.ts:87` | `snap.tasks.find(t => t.id === taskId)` | `task_id` 反查 requirementId + 窗口绑定校验 | `await deps.taskStore.get(taskId)` | A |
| S-27 | `src/tools/AdvanceTool/AdvanceTool.ts:131` | `selectAdvanceEvent({ tasks: after.tasks }, …)` | 投递后选下一批 ready（输出 `next_ready`） | `{ tasks: await deps.taskStore.listByRequirement(requirementId) }` | A |
| S-28 | `src/tools/AdvanceTool/AdvanceTool.ts:144` | `after.tasks.find(t => t.id === taskId)?.status` | 输出 `parent_status` | `(await deps.taskStore.get(taskId))?.status` | A |
| S-29 | `src/tools/TaskStatusTool/TaskStatusTool.ts:80` | `snapshot.tasks.find(t => t.id === args.task_id)` | 单卡状态 + `lastRun`/`lastReport`/`workflow` 摘要（逐字节相等验收点） | `await deps.taskStore.get(args.task_id)` | A |
| S-30 | `src/application/internal/capture-section.ts:107` | `ledger.tasks.filter(t => t.requirementId === implementingReq.id && isInProgressTask(t))` | 注入文本「当前任务执行中」段落 | `await taskStore.listByRequirement(implementingReq.id)`；`ledger` 入参来源见 §3.1/§4 | A |
| S-31 | `src/application/internal/plan-landing.ts:79` | `ledger.tasks.map(t => t.id)` | 落库前 id 去重集合 | 进 mutate 前预取队列任务；`taskStore.createMany` 幂等跳过重复 | A |
| S-32 | `src/application/internal/plan-landing.ts:120` | `assertDagAcyclic([...ledger.tasks, ...records], req.id)` | 拆分落库前 DAG 环校验 | 队列任务 + 新 `records` | A |
| S-33 | `src/application/internal/plan-landing.ts:121` | `ledger.tasks.push(...records)` | **拆分落库唯一写入点**（看板 DAG 来源，最高风险） | `await taskStore.createMany(req.id, records)` | A |
| S-34 | `src/application/internal/plan-landing.ts:149` | `result.changed.tasks` | `LandedTaskRef[]` 投影（返回体 + decomposition.md） | `taskStore.createMany(...)` 返回值 | B |
| S-35 | `src/application/internal/plan-landing.ts:178` | `(result.changed.tasks ?? []).find(x => x.id === c.id)` | decomposition.md §1 RTM 覆盖对照表行 | 同上（S-34 的同批返回值） | B |
| S-36 | `src/application/internal/plan-landing.ts:189` | `(result.changed.tasks ?? []).find(x => x.id === c.id)` | decomposition.md §2 任务清单表格行 | 同上 | B |
| S-37 | `src/application/internal/plan-landing.ts:200` | `(result.changed.tasks ?? []).find(x => x.id === c.id)` | 任务卡骨架生成（title/context/acceptance/scope…） | 同上 | B |
| S-38 | `src/application/internal/plan-landing.ts:204` | `(result.changed.tasks ?? []).find(x => x.id === depId)` | 任务卡「上游产出摘要（dependsSummary）」dep 标题 | 同上 | B |
| S-39 | `src/application/internal/plan-landing.ts:248` | `syncRequirementMarks(deps, r0, snap.tasks)` | 拆分后回写需求接收标记（文档留痕） | `await taskStore.listByRequirement(requirementId)` | A |
| S-40 | `src/application/internal/verdicts.ts:62` | `ledger.tasks.some(t => t.id === tid)` | 返工卡 id 冲突重试（≤50 次） | `taskStore.mutate` 内用队列任务（mutate 前预取） | A |
| S-41 | `src/application/internal/verdicts.ts:86` | `ledger.tasks.push(task)` | 返工卡物化写入 | `await taskStore.mutate(reqId, ts => [...ts, task])` | A |
| S-42 | `src/application/internal/verdicts.ts:127` | `applySheetVerdicts(sheet, verdicts, actor, nowTs, ledger.tasks)` | 验收单逐项裁决（纯 domain 函数入参） | 队列任务数组（预取） | A |
| S-43 | `src/application/internal/verdicts.ts:187` | `reworkSpecsFor(sheet, ledger.tasks)` | 由验收单推导返工规格（纯 domain 入参） | 队列任务数组（预取） | A |
| S-44 | `src/application/internal/rtm-yaml.ts:87` | `snap.tasks.filter(t => t.requirementId === reqId).map(toTaskLike)` | `LedgerReader.tasksOf` **同步回调**（RTM YAML 覆盖度） | 预取任务注入；`syncRTMYamlWithSnapshot` 需改签名/变异步（**4 个调用点含他人写域**，见 §4/§3.5） | A |
| S-45 | `src/application/internal/content-gate-triad.ts:59` | `input.tasks.filter(t => t.requirementId === input.requirementId)` | 需求级任务卡三要素门禁 | **内部不改**；调用方传队列任务 | D |
| S-46 | `src/application/internal/content-gate-triad.ts:81` | `input.tasks.find(t => t.id === input.taskId)` | 单卡三要素门禁 | 同上 | D |
| S-47 | `src/application/internal/verification-doc-writer.ts:38` | `snap.tasks.filter(t => t.requirementId === reqId && t.status !== 'canceled')` | 回填 `verification.md` 的验收项/文件完整性 | `await ports.taskStore.listByRequirement(reqId)`（函数**已 async**）；调用方 2 处（1 处他人写域） | A |
| S-48 | `src/application/internal/lazy-expand.ts:63` | `ledger.tasks.some((t) => t.parentId === parent.id)` | 子卡链幂等判据（已有子卡则不展开） | `taskStore.mutate` 内用队列任务（预取） | A |
| S-49 | `src/application/internal/lazy-expand.ts:102` | `ledger.tasks.push(child)` | 子卡链落库（父卡开工时展开） | `await taskStore.mutate(reqId, ts => [...ts, child])` | A |
| S-50 | `src/application/internal/rework-update.ts:25` | `ledger.tasks.find(t => … && t.title === plan.title)` | 重新批准计划后按标题就地更新既有父卡 | `taskStore.mutate` 内用队列任务（预取） | A |
| S-51 | `src/application/internal/confirm-settle.ts:236` | `fresh?.plan?.tasks ?? []` | 批准计划后取计划任务表构造 `draft` | **不迁移**（`plan.tasks`） | E |
| S-52 | `src/application/internal/confirm-settle.ts:267` | `deps.repo.snapshot().tasks.filter(t => t.requirementId === d.requirementId && t.status !== 'canceled')` | 幂等判据：该需求是否已落库（`REQBOARD_ALREADY_DECOMPOSED`） | `await deps.taskStore.listByRequirement(d.requirementId)` | A |
| S-53 | `src/application/internal/confirm-settle.ts:309` | `deps.repo.snapshot().tasks.filter(t => …).length` | catch 分支：判断落库是否已生效（决定是否仍推进） | `await deps.taskStore.listByRequirement(d.requirementId)` | A |
| S-54 | `src/application/internal/advance-select.ts:26` | `view.tasks.filter(…)`（`topLevelTasks`） | 顶层卡筛选（**纯函数**，`AdvanceView` 入参） | **内部不改**；调用方（AdvanceTool/AdvanceChain）喂队列任务 | C |
| S-55 | `src/application/internal/advance-select.ts:31` | `view.tasks.filter(…)`（`openSubtasks`） | 同需求非取消子卡 | 同上 | C |
| S-56 | `src/application/internal/advance-select.ts:43` | `view.tasks.filter(t => t.status === 'done')`（`depsDone`） | 依赖是否全 done | 同上 | C |
| S-57 | `src/application/internal/advance-select.ts:49` | `view.tasks.filter(t => t.parentId === parentId)`（`subtasksOf`） | 父卡名下子卡 | 同上 | C |
| S-58 | `src/application/internal/advance-select.ts:104` | `view.tasks.some(…)`（`hasOpenWork`） | 区分「已终态」与「死锁停滞」 | 同上 | C |
| S-59 | `src/application/internal/agent-handle.ts:34` | `snap.tasks.find((t) => t.id === parentId)` | 解析子卡派发的 agent 句柄（按父卡找绑定窗口） | `await deps.taskStore.get(parentId)`；**函数需变异步 → 3 处 use-cases 调用方**（见 §4/§3.5） | A |
| S-60 | `src/application/internal/failure-handling.ts:42` | `ledger.tasks.find((x) => x.id === subtaskId)` | 子卡失败回退（in_progress→todo + attempt+1 + revisions） | `await taskStore.get(subtaskId)` 取 reqId → `taskStore.mutate(reqId, fn)` | A |
| S-61 | `src/application/internal/support.ts:86` | `ledger.tasks.filter(t => t.requirementId === reqId && …)` | `rollupBlockersOf`：rollup 阻塞清单（幽灵卡死告警） | 队列任务（`LedgerView` 参数去 tasks → 改签名，见 §3.5） | A |
| S-62 | `src/application/internal/support.ts:138` | `ledger.tasks.find((t) => t.id === task.parentId)` | `assertDoneEvidence`：子卡链基准（父卡 createdAt，D17 修复桩） | 同上（**被 3 处 use-cases 在 mutate 内调用**，跨写域） | A |
| S-63 | `src/application/internal/support.ts:169` | `subtasksOf(ledger.tasks as readonly TaskRecord[], task.id)` | `assertDoneEvidence`：父卡收尾门（未 done 子卡） | 同上 | A |
| S-64 | `src/application/internal/support.ts:184` | `findRecentAgentDoneTask(ledger.tasks, task.id, …)` | `assertDoneEvidence`：60s 批量关闭节流 | 同上 | A |
| S-65 | `src/application/internal/task-completeness.ts:20` | `req.plan?.tasks ?? []` | `taskCompletenessGap`：计划有卡而台账 0 卡（拒进实施） | **不迁移**（`plan.tasks`；注意同函数 22 行的 `tasks` 形参在 use-cases 写域，见 §5） | E |
| S-66 | `src/application/internal/rollup.ts:45` | `viewOf: { requirements, tasks: ledger.tasks, triages }` | `applyTaskRollup`/`applyPickupAdvance` 决策视图（R2/R3 需求状态推导） | `viewOf(ledger, tasks)` —— 签名须加 `tasks` 参数；**被路由/用例广泛调用** | A |
| S-67 | `src/application/internal/content-gate-wiring.ts:351` | `input.tasks.find(t => t.id === input.taskId)` | `doneEvidenceAnchorFailure`（`DoneAnchorInput` 纯入参） | **内部不改**；调用方传队列任务 | D |
| S-68 | `src/application/query/QueryState.ts:66` | `ledger.tasks` | `clauseReceiveStatus`：条款接收状态（`reqboard_status` 输出） | `await taskStore.listByRequirement(boundReq.id)` | A |
| S-69 | `src/application/query/QueryState.ts:80` | `ledger.tasks.filter(t => t.requirementId === boundReq.id && t.status !== 'canceled')` | `generateStatusRTM` 入参 | 同上 | A |
| S-70 | `src/application/query/QueryState.ts:106` | `ledger.tasks.filter(t => …)` | `checkFullTraceability` 入参（三级追溯链） | 同上 | A |
| S-71 | `src/application/query/QueryStageDetail.ts:183` | `ledger.tasks.filter(t => t.requirementId === req.id)` | DecomposeStageBody：落库任务 DAG + 与计划对照 | `Pick<LedgerView,'tasks'>` 改本地 `{ tasks }`；调用方预取队列任务 | A |
| S-72 | `src/application/query/QueryStageDetail.ts:192` | `req.plan?.tasks ?? []` | DecomposeStageBody `planTasks`（计划任务表） | **不迁移** | E |
| S-73 | `src/application/query/QueryStageDetail.ts:206` | `ledger.tasks.filter(t => t.requirementId === req.id)` | ImplementStageBody：每任务执行记录 + 按窗口分组 | 同 S-71 | A |
| S-74 | `src/application/query/QueryRequirementToken.ts:43` | `ledger.tasks`（`hasSnapshotGap` 内） | 快照缺口判定（`Pick<LedgerView,'tasks'>` 入参，**同步私有函数**） | 入参改 `{ tasks }`；调用方预取 | A |
| S-75 | `src/application/query/QueryRequirementToken.ts:56` | `ledger.tasks`（`executionRows` 内） | 执行记录 token 行（`executionRows` 输出） | 同上 | A |
| S-76 | `src/application/dive/idle-capture-actions.ts:28` | `ledger.tasks.find(t => t.requirementId === requirement.id && isInProgressTask(t))` | `addressSectionFor`：注入地址段的「当前任务」（**同步函数，入参 `ReqboardLedger`**） | 入参改收队列任务数组（或变异步）；调用方 `dive/session-driver.ts`（本写域内） | A |
| S-77 | `src/application/gate/handlers/h3-inject.ts:41` | `deps.repo.snapshot().tasks.find(t => t.requirementId === requirement.id && isInProgressTask(t))` | 闸门 H3 注入「作答后所处阶段」的当前任务（**同步函数 `withAddress`**） | `H3InjectDeps` 增 `taskStore`，预取任务传入；`withAddress` 变异步（调用点在同文件 `h3-inject.ts:39`） | A |

### 机器原样命中附录（与上表一一对应，供计数复核）

```
src/http/routers/requirements.ts:182 | plan.tasks.length
src/http/routers/requirements.ts:343 | ledger.tasks.find(t => t.id === id)
src/http/routers/requirements.ts:350 | result.changed.tasks[0]?.id
src/http/routers/verdicts.ts:198 | result.changed.tasks
src/http/routers/verdicts.ts:200 | result.changed.tasks
src/http/routers/stages.ts:46 | ledger.tasks.map(t => ({ ...t }))
src/http/routers/stages.ts:49 | readyTasks(ledger.tasks, r.id)
src/http/routers/stages.ts:95 | ledger.tasks.filter(t => t.requirementId === req.id)
src/http/routers/stages.ts:137 | for (const t of ledger.tasks)
src/http/routers/stages.ts:153 | ledger.tasks.filter(t => t.requirementId === target.id)
src/http/routers/stages.ts:222 | assembleStageDetail(..., { tasks: ledger.tasks }, ...)
src/http/routers/stages.ts:245 | assembleStageOverview(..., { tasks: ledger.tasks }, ...)
src/http/routers/stages.ts:279 | assembleRequirementToken(req, { tasks: ledger.tasks })
src/http/routers/stages.ts:286 | ledger.tasks.filter(...).flatMap(t => t.executions.map(e => e.sessionId))
src/http/routers/stages.ts:321 | assembleRequirementMarks({ docs }, req, ledger.tasks)
src/http/routers/tasks.ts:86 | assertDagAcyclic([...ledger.tasks, record], requirementId)
src/http/routers/tasks.ts:87 | ledger.tasks.push(record)
src/http/routers/tasks.ts:107 | ledger.tasks.find(t => t.id === id)
src/http/routers/tasks.ts:149 | result.changed.tasks[0]
src/http/routers/tasks.ts:157 | result.changed.tasks[0]
src/http/routers/tasks.ts:165 | ledger.tasks.find(t => t.id === id)
src/http/routers/tasks.ts:176 | assertDagAcyclic(ledger.tasks, task.requirementId)
src/http/routers/tasks.ts:193 | result.changed.tasks[0]
src/http/routes.ts:123 | ledger.tasks.some(t => t.id === id)
src/tools/RunStatusTool/RunStatusTool.ts:116 | deps.repo.snapshot().tasks.filter(...)
src/tools/AdvanceTool/AdvanceTool.ts:87 | snap.tasks.find((t) => t.id === taskId)
src/tools/AdvanceTool/AdvanceTool.ts:131 | selectAdvanceEvent({ tasks: after.tasks }, ...)
src/tools/AdvanceTool/AdvanceTool.ts:144 | after.tasks.find((t) => t.id === taskId)?.status
src/tools/TaskStatusTool/TaskStatusTool.ts:80 | snapshot.tasks.find(t => t.id === args.task_id)
src/application/internal/capture-section.ts:107 | ledger.tasks.filter(...)
src/application/internal/plan-landing.ts:79 | ledger.tasks.map(t => t.id)
src/application/internal/plan-landing.ts:120 | assertDagAcyclic([...ledger.tasks, ...records], req.id)
src/application/internal/plan-landing.ts:121 | ledger.tasks.push(...records)
src/application/internal/plan-landing.ts:149 | (result.changed.tasks ?? []).map(...)
src/application/internal/plan-landing.ts:178 | (result.changed.tasks ?? []).find(...)
src/application/internal/plan-landing.ts:189 | (result.changed.tasks ?? []).find(...)
src/application/internal/plan-landing.ts:200 | (result.changed.tasks ?? []).find(...)
src/application/internal/plan-landing.ts:204 | (result.changed.tasks ?? []).find(...)
src/application/internal/plan-landing.ts:248 | syncRequirementMarks(deps, r0, snap.tasks)
src/application/internal/verdicts.ts:62 | ledger.tasks.some(t => t.id === tid)
src/application/internal/verdicts.ts:86 | ledger.tasks.push(task)
src/application/internal/verdicts.ts:127 | applySheetVerdicts(..., ledger.tasks)
src/application/internal/verdicts.ts:187 | reworkSpecsFor(sheet, ledger.tasks)
src/application/internal/rtm-yaml.ts:87 | snap.tasks.filter(...)
src/application/internal/content-gate-triad.ts:59 | input.tasks.filter(...)
src/application/internal/content-gate-triad.ts:81 | input.tasks.find(...)
src/application/internal/verification-doc-writer.ts:38 | snap.tasks.filter(...)
src/application/internal/lazy-expand.ts:63 | ledger.tasks.some((t) => t.parentId === parent.id)
src/application/internal/lazy-expand.ts:102 | ledger.tasks.push(child)
src/application/internal/rework-update.ts:25 | ledger.tasks.find(...)
src/application/internal/confirm-settle.ts:236 | fresh?.plan?.tasks
src/application/internal/confirm-settle.ts:267 | deps.repo.snapshot().tasks.filter(...)
src/application/internal/confirm-settle.ts:309 | deps.repo.snapshot().tasks.filter(...)
src/application/internal/advance-select.ts:26 | view.tasks.filter(...)
src/application/internal/advance-select.ts:31 | view.tasks.filter(...)
src/application/internal/advance-select.ts:43 | view.tasks.filter(...)
src/application/internal/advance-select.ts:49 | view.tasks.filter(...)
src/application/internal/advance-select.ts:104 | view.tasks.some(...)
src/application/internal/agent-handle.ts:34 | snap.tasks.find(...)
src/application/internal/failure-handling.ts:42 | ledger.tasks.find(...)
src/application/internal/support.ts:86 | ledger.tasks.filter(...)
src/application/internal/support.ts:138 | ledger.tasks.find(...)
src/application/internal/support.ts:169 | subtasksOf(ledger.tasks as readonly TaskRecord[], task.id)
src/application/internal/support.ts:184 | findRecentAgentDoneTask(ledger.tasks, ...)
src/application/internal/task-completeness.ts:20 | req.plan?.tasks ?? []
src/application/internal/rollup.ts:45 | { requirements, tasks: ledger.tasks, triages }
src/application/internal/content-gate-wiring.ts:351 | input.tasks.find(...)
src/application/query/QueryState.ts:66 | ledger.tasks
src/application/query/QueryState.ts:80 | ledger.tasks.filter(...)
src/application/query/QueryState.ts:106 | ledger.tasks.filter(...)
src/application/query/QueryStageDetail.ts:183 | ledger.tasks.filter(...)
src/application/query/QueryStageDetail.ts:192 | req.plan?.tasks ?? []
src/application/query/QueryStageDetail.ts:206 | ledger.tasks.filter(...)
src/application/query/QueryRequirementToken.ts:43 | for (const t of ledger.tasks)
src/application/query/QueryRequirementToken.ts:56 | for (const t of ledger.tasks)
src/application/dive/idle-capture-actions.ts:28 | ledger.tasks.find(...)
src/application/gate/handlers/h3-inject.ts:41 | deps.repo.snapshot().tasks.find(...)
（77 行）
```

---

## 2. 字节相等回归风险点（t7/t8 验收靠这节）

> 验收方式（TC-8.1~TC-8.7）：**迁移前对读方产出快照 → 迁移后重跑同样请求 → 断言 JSON 逐字节相等**。
> 只断言 HTTP 200 不算通过。

| # | 风险 | 命中站点 | 纪律 |
|---|---|---|---|
| R-1 | **`layer` 字段泄漏（最高）**：`QueueTask = TaskRecord & { layer }`；把队列任务对象直接返回/展开，响应会**多一个 `layer` 键** | S-06（`{...t}`）、S-20、S-23（原样返回 task 对象）；S-19/S-29/S-03 只取字段故安全 | 出口处剥离 `layer`（`const { layer: _l, ...task } = t`）。**更优解：让 TaskStore 对外返回 `TaskRecord`（内部剥离 layer），把剥离收敛在端口边界一处** |
| R-2 | **`/state` 全量任务数组顺序**：迁移前是台账单数组的**插入顺序**（跨需求交错）；迁移后逐需求读 queue.json 再拼接 → 全局顺序必变 | S-06、S-09 | 需 lead 裁定（见 §3.1）：TaskStore 加 `listAll()` + 稳定排序（`createdAt asc, id asc`）；或明确接受顺序变化并重新基线（与 TC-8.1「与迁移前一致」冲突，须显式改口径） |
| R-3 | **`ready` 顺序**：`readyTasks(tasks, rId)`（`shared/protocol.ts:1393`）按 tasks 数组顺序输出；队列 `ready` 由 `computeReady` 输出，**顺序未必一致** | S-07 | 改造后**继续用 `readyTasks(队列任务, rId)`**，不要直接用 `queue.ready`——否则 `/state.ready[*]` 数组顺序变化 |
| R-4 | **每需求内 `tasks` 数组元素顺序**：若 `listByRequirement` 按 `layer`/拓扑序返回，会改变每需求内任务顺序 | S-08、S-10、S-11、S-12、S-13、S-14、S-71、S-73 | **`listByRequirement` 必须按队列文件 `tasks` 原始数组顺序返回**；迁移写 `queue.tasks` 时按台账源顺序（**不得拓扑重排**，`layers` 仅派生视图） |
| R-5 | **读回补默认值**：若 QueueTaskStore 读回时补 `statusHistory: []` 之类默认值，会**新增键**导致 JSON 不等 | 全部 A 类 | 读回**只做 V-1 校验，不补字段**；`undefined` 与「键不存在」在 `JSON.stringify` 下等价，不得改写为显式值 |
| R-6 | **写响应回读丢失**：`LedgerChange.tasks` 移除后若忘记回传，`rework_tasks` 变 `[]`、`target` 变 `undefined` | S-03、S-04、S-05、S-19、S-20、S-23、S-34~S-38 | 一律用 `taskStore.createMany`/`mutate` 的**返回值**填充，不得回落到 `?? []` 静默兜底 |
| R-7 | **类 E 误改**：把 `req.plan?.tasks` 当台账任务改 → 计划任务表读空（评论文案恒 0、拆分编排失去数据源、decomposition.md 空白） | S-01、S-51、S-65、S-72 | 显式排除，**不得改** |
| R-8 | **`verification.md` / RTM YAML 文本**：这两处是落盘文本产物，字段缺失会体现在 diff 而非 JSON | S-47（`verification.md`）、S-44（`rtm-implementing.yml`） | 迁移后重生成并 diff 前后文件（`docs/requirements/<REQ>/verification.md`、`rtm-implementing/*.yml`） |

**基线快照建议（t7/t8 执行时）**：对 S-06（`GET /state`）、S-11/S-12（stage/stages）、S-13（token）、S-15（marks）、S-25~S-29（4 个工具的 execute 返回）在**迁移前**先落一份 JSON 快照到 `tmp-diag/`，迁移后逐字节 diff。

---

## 3. 契约缺口与写域边界（**需 lead 裁定，勿自行扩范围**）

### 3.0 写域裁定：3 个文件已划归 reader-uc（2026-09-27 Lead 变更）★

Lead 裁定（实测「计划落点写错」）：从 `src/application/internal/` **排除 3 个文件**，整段划给 reader-uc（task-13）：

- `src/application/internal/plan-landing.ts`
- `src/application/internal/confirm-settle.ts`
- `src/application/internal/rollup.ts`

**我复核并确认该裁定的必要性（证据在本清单内）**：`plan-landing.ts:76` 是 `repo.mutate('task-created')`、
`:121` 是 `ledger.tasks.push(...records)` —— 这是**全仓唯一真正往台账写任务的地方**，且有**两个调用方**
（`use-cases/Decompose.ts:189` 拆分、`confirm-settle.ts:276` 计划批准即落库）。
若把这一条写路径按人切开，v9 台账（已无 `tasks` 键）下不是报错而是**任务静默消失**。**同意整段归一人。**

本清单中被划走的 13 条站点（**reader-http 不得改**，其改造与验收归 reader-uc）：

| 站点 | 位置 | 类 | 说明 |
|---|---|---|---|
| S-31 | `plan-landing.ts:79` | A | 落库 id 去重集合 |
| S-32 | `plan-landing.ts:120` | A | 拆分 DAG 环校验 |
| **S-33** | **`plan-landing.ts:121`** | A | **全仓唯一真正写台账任务点**（`ledger.tasks.push`） |
| S-34 | `plan-landing.ts:149` | B | `LandedTaskRef` 投影 |
| S-35 | `plan-landing.ts:178` | B | decomposition.md §1 表格 |
| S-36 | `plan-landing.ts:189` | B | decomposition.md §2 表格 |
| S-37 | `plan-landing.ts:200` | B | 任务卡骨架 |
| S-38 | `plan-landing.ts:204` | B | 任务卡上游摘要 |
| S-39 | `plan-landing.ts:248` | A | 拆分后回写需求接收标记 |
| S-51 | `confirm-settle.ts:236` | E | 计划任务表（本就不迁移） |
| S-52 | `confirm-settle.ts:267` | A | 已落库幂等判据 |
| S-53 | `confirm-settle.ts:309` | A | 落库是否已生效（catch 分支） |
| S-66 | `rollup.ts:45` | A | `viewOf` 决策视图（`applyTaskRollup`） |

> **对 t7/t8/t10 的连带影响**：S-34~S-38（B 类）与 S-66 一旦由 task-13 改签名，
> **本写域的路由会立即打红**（`tasks.ts:89-95/142-147/186-191` 调 `applyTaskRollup`；
> `verdicts.ts:179-182` 调 `applyVerdicts` → `applySheetVerdicts`）。**t7 开工前必须与 reader-uc 对齐
> `applyTaskRollup` 的新签名**，否则编译不过。此点同 §3.5。

### 3.1 TaskStore 端口缺「全量列举」

S-06（`/state.tasks`，看板首屏）、S-09（会话进度锚点）需要**跨全部需求**的任务集合。
design/interfaces.md I-1 的 TaskStore 只有 `get` / `listByRequirement` / `readQueue` / `mutate` / `createMany` / `subscribe`，
**没有 `listAll()`**（architecture.md 明确「启动不预读全部 82 个需求」，但 `handleState` 是**显式全量**请求，
按需加载全部仍不可避免）。**缺口：**
- (a) 给 TaskStore 增 `listAll(): Promise<readonly TaskRecord[]>`（走 cache，逐需求懒加载）并规定稳定排序；或
- (b) 由 t7 在路由层遍历需求 id 逐个 `listByRequirement` 拼接（82 次调用，需自带排序与缓存）。
> 该端口属 **queue-core 写域（`src/application/ports.ts`）**，我不得改。请 lead 决定 (a)/(b) 并同步 task-9。

### 3.2 S-24 落在写域之外

`src/http/routes.ts:123`（`mintId` 任务 id 去重）在 grep 范围 `src/http/` 内、也在 t7 验收的
「grep 无 `ledger.tasks`」口径内，但 **t7 文件清单只列 `src/http/routers/{stages,tasks,requirements,verdicts}.ts`**，
task-12 写域也只写 `src/http/routers`。**`src/http/routes.ts` 无人认领** → 不改则 (1) 建卡 id 不再查重（可能撞 id）
(2) TC-8.12 全仓残留静态检查无法归零。
> 请 lead 裁定：扩 task-12 写域到 `src/http/routes.ts`（含组合根装配 `taskStore` 注入 RouterCtx），或另派卡。

### 3.3 `RouterCtx` 缺 `taskStore`（与 3.2 同批）

`src/http/routers/shared.ts:16` 的 `RouterCtx.store: JsonLedgerRepository`，无 `taskStore`。
t7 必须扩接口，而**注入点在组合根 `src/http/routes.ts:130` 的 `ctx` 构造**（= 3.2 的写域外文件）。两者必须同批改，否则 t7 改完路由无法编译。

### 3.4 `UseCaseDeps` 缺 `taskStore`

`src/application/ports.ts:454` 的 `UseCaseDeps` 无 `taskStore` → S-25、S-26、S-28、S-29、S-44、S-47、S-52、S-53、S-59、S-60 全部依赖它。属 **task-9 写域**，落地后自动解锁。

### 3.5 跨写域签名裂变（本人不得单方改）

以下文件的**定义**在我的写域（`src/application/internal/`），但**调用方在 reader-uc 写域（`src/application/use-cases/`）**。
签名一变（加 `tasks` 参数或变异步）会立刻打红他人文件：

| 函数（本写域） | 站点 | 调用方（他人写域） |
|---|---|---|
| `support.assertDoneEvidence(deps, windowKey, task, ledger)` | S-62、S-63、S-64 | `use-cases/MoveTask.ts:106`、`ExecuteTask.ts:339`、`AdvanceChain.ts:187` |
| `support.rollupBlockersOf(ledger, reqId, status)` | S-61 | `use-cases/SubmitVerification.ts:274` |
| `rtm-yaml.syncRTMYamlWithSnapshot(...)`（同步，调用点 4 处） | S-44 | `requirements.ts:195/248`、`tasks.ts:154`（本写域）+ `rtm-yaml.ts:136` 的回调被 use-cases/AdvanceChain 等调用 |
| `verification-doc-writer.rewriteVerificationDoc(ports, reqId)` | S-47 | `use-cases/AcceptSheet.ts:225` |
| `agent-handle.ensureAgentHandle(deps, parentId, subtaskId, exec)`（同步） | S-59 | `use-cases/{AdvanceChain,ExecuteTask}.ts` 等 |

> **建议方案（请 lead 与 reader-uc 确认）**：给这些函数**加 `tasks` 入参**而非改用异步 taskStore——
> 由调用方（use-cases）负责 `await taskStore.listByRequirement(...)` 后传入。
> 这样「本写域函数保持同步」+「异步只发生在路由/工具/用例边界」，裂变面最小。
> 若改成 `taskStore` 注入，则 use-cases 内 `repo.mutate` 回调的同步契约会被打破（见 §4 头条）。

### 3.6 `handleState` 的 SSE 事件源（不在 77 命中内，但同批必改）

`src/http/routers/stages.ts:65-80` 的 `handleEvents` 订阅的是 `store.subscribe`（台账 revision）。
迁移后**任务变更不再经台账** → 看板实时刷新（任务状态变化）会静默失灵。
> t7 应一并把任务变更订阅切到 `taskStore.subscribe`（`TaskChange`，interfaces.md I-1）。
> 该站点不含 `.tasks` 字面量，故不在 77 行清单内——**这是清单外的高风险点**。

---

## 4. async 改造点

### 4.0 核心约束（决定所有改法）

`ReqboardRepository.mutate(reason, fn: (ledger) => LedgerChange | undefined)` 的回调是**同步契约**
（`src/application/ports.ts:60`；`plan-landing.ts:156-157` 明文：「repo.mutate 的回调是同步契约…在里面 await 会让整个模块无法被 esbuild/vite 解析」）。

⇒ **所有在 `repo.mutate` 回调内读 `ledger.tasks` 的站点，都不能就地改成 `await taskStore.*`**，必须先取后进。

**在 mutate 回调内的命中**：S-16、S-17、S-18、S-21、S-22、S-40、S-41、S-42、S-43、S-48、S-49、S-50、S-31、S-32、S-33、S-60；
以及经 `rollup.ts#viewOf`（S-66）间接读 tasks 的调用方。

**推荐改法**（顺序契约 = interfaces.md I-11 / TC-8.11）：

```
1) const reqId = ...                                   // 由入参或 await taskStore.get(id) 得到
2) const tasks = await taskStore.listByRequirement(reqId)   // 进 mutate 前预取
3) await taskStore.mutate(reqId, ts => …)              // ① 先写任务（原子）
4) await repo.mutate(reason, ledger => …)              // ② 后写需求（引用 2) 的 tasks 做纯判定）
```

代价：打破「任务+需求同笔原子」——**架构已接受两步非原子**（architecture.md「一致性模型」：
「任务写成功、需求状态写失败：允许；需求状态写成功、任务写失败：不允许（顺序固定先任务后需求）」）。

### 4.1 同步函数 → 需改签名/变异步

| 站点 | 函数与现状 | 裂变面 |
|---|---|---|
| S-44 | `rtm-yaml.ts:87` `LedgerReader.tasksOf` **同步回调**；`syncRTMYamlWithSnapshot`（rtm-yaml.ts:154）**同步** | **4 个调用点**：`requirements.ts:195`、`requirements.ts:248`、`tasks.ts:154`（本写域）+ `rtm-yaml.ts:136`（回调被 use-cases 调用 → 他人写域） |
| S-47 | `rewriteVerificationDoc` **已 async**（verification-doc-writer.ts:23），仅需 `ports` 增 `taskStore` | 2 个调用点：`verdicts.ts:186`（本写域）+ `use-cases/AcceptSheet.ts:225`（他人写域） |
| S-76 | `idle-capture-actions.ts:28` `addressSectionFor` **同步**，入参 `ReqboardLedger` | 调用方 `src/application/dive/session-driver.ts`（**本写域**，可自改） |
| S-77 | `h3-inject.ts:41` `withAddress` **同步**，`H3InjectDeps` 只有 `repo` | 调用点同文件 `h3-inject.ts:39`；但 **`H3InjectDeps` 的构造在链装配处（组合根，本写域外）** |
| S-59 | `agent-handle.ts:34` `ensureAgentHandle` **同步** | 3 处 use-cases（他人写域）→ 见 §3.5 |
| S-61~S-64 | `support.ts` 四个函数 **同步**，且被 use-cases 在 mutate 内调用 | 见 §3.5 |
| S-66 | `rollup.ts:45` `viewOf(ledger)` **同步** | `applyTaskRollup`/`applyPickupAdvance`/`applyPickupReconcile` 被路由 + use-cases 广泛调用；**建议只加 `tasks` 形参，不改异步** |

### 4.2 同步 assembler/纯函数 → **不要**变异步，改由调用方预取

| 站点 | 现状 | 处理 |
|---|---|---|
| S-11、S-12 | `assembleStageDetail` / `assembleStageOverview` **都是同步**（`QueryStageDetail.ts:323/338`），内部 `buildBody` 同步（S-71/S-73） | stages.ts:221/244 已是 async → 先 `await taskStore.listByRequirement(id)`，再 `store.read(ledger => assembleStageDetail(…, { tasks }, …))` |
| S-13、S-74、S-75 | `assembleRequirementToken` **同步**（`QueryRequirementToken.ts:78`），私有 `hasSnapshotGap`/`executionRows` 同步 | stages.ts:279 先 await 取任务再传入；S-75 的 `nodeTokensOf`（stages.ts:299）本就是同步纯函数，入参改队列任务 |
| S-27、S-58 | `advance-select.ts` 全为**纯函数**（`AdvanceView` 入参） | **不改函数**；`AdvanceTool.ts:131` 与 `AdvanceChain`（他人写域）喂队列任务 |
| S-45、S-46、S-67 | `content-gate-triad.ts` / `content-gate-wiring.ts` 门禁为**纯入参** | **不改函数**；调用方（`content-gate-wiring.ts` 内的编排 / use-cases）喂队列任务 |

### 4.3 无裂变（已是 async）

- 路由层：`stages.ts` / `tasks.ts` / `requirements.ts` / `verdicts.ts` 全部 handler `async`，包 `await` 无裂变。
- `RunStatusTool.ts:116`：`getTasks` 回调本身 `async () => …`（RunStatusTool.ts:115），直接改 await 即可。
- `AdvanceTool.ts` / `TaskStatusTool.ts`：`execute` 均 `async`。
- `plan-landing.ts` / `confirm-settle.ts` / `QueryState.ts`：所在函数均 `async`。

---

## 5. 非命中但相关（不在 77 行清单内，供 t7/t8/lead 交叉核对）

| 项 | 位置 | 说明 |
|---|---|---|
| 工具经 use-cases 间接读写任务 | `tools/TaskReportTool` → `use-cases/ReportTask.ts`；`tools/{TaskTree,TaskExecute,TaskMove,Move,Status,Decompose}Tool` → 各自 use-case | 工具壳内无 `.tasks` 字面量，故不进 77 行。t8 验收「TaskReportTool 写回落到队列且 lastReport 已写」实由 **use-case** 完成（reader-uc 写域） |
| `MoveRequirement.ts:39/50` | `taskCompletenessGap(req, snap.tasks, to)` / `(req, ledger.tasks, to)` | **`src/application/use-cases/`**，不在本卡 grep 范围（属 reader-uc / task-11 清单） |
| `handleEvents` SSE | `stages.ts:65-80` | 见 §3.6 |
| `LedgerView.tasks` / `LedgerChange.tasks` 定义 | `application/ports.ts:31` / `:41` | 78 行清单的**类型根**：两处字段删除会同时打红 S-61~S-64（`ledger: LedgerView` 形参）、S-66 等。属 task-9 写域 |
| `RouterCtx` / `ReqboardRouteDeps` | `http/routers/shared.ts:16`、`http/routes.ts:28` | 需增 `taskStore`（§3.3） |
| `readyTasks` / `assertDagAcyclic` / `subtasksOf` | `shared/protocol.ts:1393/1360/1429` | 保留复用（队列任务同构，R-3 明确要用 `readyTasks` 保序）；属 queue-core 写域，本卡不改 |

---

## 6. 三个最担心的风险点（报 Lead 用）

1. **R-1 `layer` 字段泄漏 + R-4 数组顺序**：`QueueTask = TaskRecord & { layer }` 且顺序由队列文件顺序决定。
   任一处理不当，`/state` 与各工具输出都会**逐字节不等**——而 TC-8.1~TC-8.7 正是拿逐字节相等当验收，
   这类差异不会报错、只会静默漂移（正是本需求"改漏一处界面空白"的同类失效）。
2. **`repo.mutate` 同步回调 + `taskStore` 异步**的正面冲突（§4.0）：命中 16 个站点，且**必须打破
   任务+需求的同笔原子**、改为「先 taskStore.mutate 后 repo.mutate」。这是 t7 里唯一会改动**事务边界**的地方，
   写错顺序即静默丢数据（违反 I-11 顺序契约）。
3. **S-24（`http/routes.ts:123`）与 `RouterCtx` 缺 `taskStore` 在写域之外**（§3.2/§3.3）：
   不改则 (a) 建卡 id 不再查重 (b) TC-8.12 全仓残留无法归零 (c) t7 改完路由无法编译（注入点在组合根）。
   需 lead 先裁定写域/端口，我才好动 task-12。

---

## 7. 变更历史

- 2026-09-27 - 初始产出（task-10，reader-http / w-3936d77f）：77 站点全表（A54/B11/C5/D3/E4）+ 字节相等风险 R-1~R-8 + async 改造点 + 6 项契约缺口。
