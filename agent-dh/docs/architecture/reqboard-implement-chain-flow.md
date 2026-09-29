---
id: reqboard-implement-chain-flow
title: 实施自动链（父卡/子卡）执行流程与缺陷落点
summary: implementing 阶段 autoRun 自动链的真实调用链（入口→选择器→子卡执行→凭证门→收尾/暂停）、2026-09-27 REQ-260927123256-196b 卡链实测暴露的缺陷 D14/D15/D16 的定位与修复，以及任务/链级工具面契约（reqboard_task_run/task_tree/task_status/task_move，REQ-260927144541-0481）与兼容收尾（别名等价 / 旧键兼容 / 回归判定，t8）。
type: architecture
status: living
updated: 2026-09-27
owners: [session-b71bb246, session-9649f3da-188e-427b-a657-d7eaa76b6cbe]
tags: [reqboard, implementing, auto-chain, flow, defects]
---

# 实施自动链（父卡/子卡）执行流程与缺陷落点

> **这一页解决什么**：把 implementing 阶段「谁触发链 → 选哪张卡 → 子卡怎么跑 → 什么算完工 → 失败怎么停」
> 画成一张可对照的图，并记录 2026-09-27 REQ-260927123256-196b 实测暴露的缺陷。
> 与 [需求流水线节点流程图](reqboard-pipeline-flow.md) 的分工：那边讲七节点全流程，本页只下钻**实施自动链**。

## 一、实现流程（按代码实际执行顺序）

```
[入口] 三条（差异见 D14）
 ① 工具：reqboard_task_run(task_id)            exec.agent = 调用窗口 agent ✅
 ② 看板：POST .../req/autorun {on:true}        ctx.deps.advance(id) —— 原缺 agent ❌
 ③ 启动恢复：scheduleStartupScan → scanAndResume(deps) —— 原缺 agent ❌
        │
        ▼
advanceRequirement(deps, requirementId, exec)
  ├ 单飞锁 inflight / advance.lockAt（15min stale 可接管）
  ├ req.autoRun !== true        → stopped=not_autorun（不跑）
  ├ 终态(accepting/archived/…)  → stopped=terminal
  ├ deps.jobs 可用 → 投递后台 driveChain；否则**同步兼容路径** driveChain（本实例走这条）
  └ driveChain 循环 ≤ advanceMaxStepsPerCall(=20)：
        selectAdvanceEvent(tasks, reqId, maxParallelParents=3)
          1) 某 in_progress 父卡子卡全 done/canceled → FINALIZE_PARENT
          2) 某 in_progress 父卡有 ready 子卡(todo 且依赖 done) → RUN_SUBTASK
          3) 无在跑父卡 & 有 ready 顶层卡 → OPEN_PARENT（懒展开子卡链）
          4) 全部父卡收口 → ROLLUP（需求进 accepting）
        │
        ├ OPEN_PARENT : todo→in_progress + expandSubtasks(dev/integrate/review/test)
        ├ RUN_SUBTASK : executeSubtask(...)
        │     ├ generateSubtaskScript → engine.start({ script, parent: exec.agent, signal })
        │     │     缺 exec.agent → 引擎读 request.parent.session 抛 start_failed ❌（D14）
        │     ├ run.result → parseSubtaskOutput → t.lastRun + t.lastReport(filesChanged/completed)
        │     ├ 成功路径：assertDoneEvidence
        │     │     └ 子卡：checkSubtaskEvidence
        │     │          ① lastRun.ok ② valueNonEmpty
        │     │          ③ lastReport 非空 ④ filesChanged 非空
        │     │          ⑤ 有文件 mtime ≥ claimedAt（**按 deps.docs(process.cwd()) 解析**）❌（D15）
        │     │          ⑥ packages/pages 构建新鲜度
        │     │     └ 父卡：子卡全 done + 四重证据；收尾时 lastReport 取子卡汇总
        │     └ 失败：rollbackSubtask(in_progress→todo, attempt+1) + pauseRequirement(autoRun=false, pausedReason) + alert
        └ FINALIZE_PARENT : 汇总子卡 lastReport → 父卡 done
```

**关键口径**：子卡凭证门要求「链自己认领之后改过的文件」（`mtime ≥ claimedAt`）——这是 D15 的根因，
也决定了「先手工完成、后被链认领」的卡永远过不了门。

## 二、缺陷落点（2026-09-27 实测）

| # | 落点 | 一句话 | 证据（实测） | 修复 |
|---|---|---|---|---|
| D14 | 入口②③ | 看板「继续」/启动恢复调链**不传 agent 句柄**，子卡恒 `start_failed: Cannot read properties of undefined (reading 'session')` | advance-log 04:49:17；[index.ts:434](../../packages/web/dsh-pmboard/src/index.ts)、[startup-scan.ts](../../packages/web/dsh-pmboard/src/application/internal/startup-scan.ts) 原缺 exec | ✅ 已修：[agent-handle.ts](../../packages/web/dsh-pmboard/src/application/internal/agent-handle.ts) 兜底解析绑定窗口在线 agent（`agents` 未装配时保持原行为）；解不到时给可读原因。`tests/advance-agent-handle.test.ts` 4 项 |
| D15 | 子卡凭证门 | 汇报路径写 `agent-dh/packages/...`，凭证门按 `process.cwd()`(=…/agent-dh) 解析 → 判「文件不存在」 | advance-log 04:51/05:10/05:28；PID 80558 cwd=agent-dh；[FileDocRepository.ts](../../packages/web/dsh-pmboard/src/adapters/FileDocRepository.ts) | ✅ 已修：[report-path.ts](../../packages/web/dsh-pmboard/src/application/internal/report-path.ts) 归一解析（原样 → 去 workspaceRoot basename 前缀）+ 提示词明确禁止 git 根前缀。`tests/report-path.test.ts` 7 项 |
| D16 | 运行期 | tsx 直载不热更新：`RunStatusTool`/`QueryRunStatus` 13:29 修好，13:14 启动的进程仍报 `getRequirement is not a function` | PID 80558 启动 13:14:38；两文件 mtime 13:29:49 | 改完 pmboard 源码必须重启 DSH（`scripts/start.sh`） |
| D17 | 横切 | 双机制竞跑：批准计划即 `autoRun=true` 自动开跑（confirm-settle），同时轻档路由让窗口手工改同一批卡 → 卡被两套机制同时认领 | 04:45:09 OPEN_PARENT；文件 04:46:13–46:51 被手工改；[confirm-settle.ts](../../packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts) | 待裁定（P1）：autoRun 开着的需求，轻档窗口不应再手工改同一批卡 |

> **D17 追加（2026-09-27，REQ-260927144541-0481 实测）**：这条冲突不只是"谁认领"的竞争，它会让**轻档手工卡路结构性走不通**——
> 轻档窗口把一张计划卡推到 in_progress 即触发懒展开（feature 卡落 4 张 dev/integrate/review/test 子卡），而子卡转 done
> 必须持有**真实 workflow run 证据**（`lastRun.ok`，全仓只由 `executeSubtask` 写入），父卡收尾又要等子卡全 done，
> 另有 60 秒批量关闭节流。于是"活已经手工干完"也无法通过手工推卡收口：唯一收口机制是自动链把子卡重跑一遍
> （8 父卡 × 4 子卡 ≈ 32 次子卡 run）。用户裁定：本次以**代码交付为准**，台账由人处理。

## 三、复现与判定

```bash
# D14：看板「继续」缺 agent → 修复前恒 start_failed
node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/advance-agent-handle.test.ts
# D15：路径归一
node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/report-path.test.ts
```

## 四、任务/链级工具面（2026-09-27，REQ-260927144541-0481）

> **这一节解决什么**：把"父卡管交付、子卡管执行"在**工具面**上说清楚——调用方不必读源码就知道自己在推进
> 哪条链、这张卡是父卡还是子卡、还差哪几张。需求级工具（create / submit / move / ask_confirm /
> clear_pause / decompose）不在本节范围。

| 工具 | 角色 | 关键契约 |
|---|---|---|
| `reqboard_task_run` | **唯一链入口**（投递式，立即返回） | 参数 `task_id`（父卡）或 `requirement_id`，至少给一个；返回 `job_id / run_id / running / next_ready / chain`；**副作用：调用即写 `req.autoRun=true`**（已在工具描述里显式声明，不再是隐式行为） |
| `reqboard_task_execute` | **已弃用别名** | 与 `reqboard_task_run` 同一实现产物（同参数 / 同返回体 / 同 autoRun 副作用），只换工具名——不再是"另跑一套" |
| `reqboard_task_tree` | **只读父子结构** | `parent_id` / `requirement_id`（缺省取本窗口绑定需求）→ 父卡 + 链序子卡（`stageKind / status / dependsOn / lastRunOk / reportSummary / cardDoc`）；无子卡 → `[]` + note（尚未展开） |
| `reqboard_task_status` | 单卡执行态 | 读台账 `lastRun / lastReport`——**不再读卡文档**；`workflow` 键保留（既有消费者契约），内容换为真实 run 摘要 |
| `reqboard_task_move` | 卡片流转 | 非法转移的报错含**当前角色**（父卡 / 子卡 / 存量卡）与**该角色全部合法边**；可选 `acceptance` 当场修订验收标准（只传它 = 仅修订不改状态） |

**为什么值得固化**：①契约脱节（声明 `subtask_executed / blocked / stopped`、实际返回 `job_id / run_id`）在
`additionalProperties:false` 下会把"已投递"变成一条 invalid output 错误——调用方看到的是失败，副作用却已发生；
②死数据源（任务卡里那个状态段落全仓无写入方）会让状态查询永远查不到东西。前者由门禁拦（声明键 ⊇ 返回键 +
参数 DSL 形状 + 全工具 schema 构造），后者由"台账即事实源"根治。

```bash
# 契约门禁（声明键 ⊇ 返回键 + 参数 DSL 形状 + 全工具 schema 构造）
node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts
# 工具面行为（起链与别名 / 父子视图 / 单卡台账态 / 角色报错与验收标准修订）
node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-run-contract.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-ledger.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts
```

实测需求：[REQ-260927144541-0481](../requirements/REQ-260927144541-0481/requirement.md)

## 五、兼容收尾（REQ-260927144541-0481 t8）：别名等价 / 旧键兼容 / 回归判定

> **这一节解决什么**：工具面收口后，"老调用方还能不能照旧用"必须有一条可复跑的判据；同时把**本需求引入的红**
> 与**分诊在库的预存在红**分清，避免下一轮误判（父卡验收口径：**除预存在红外全绿**）。

### 5.1 别名等价：`reqboard_task_execute` ≡ `reqboard_task_run`

同一 factory 产物，`parameters` / `output.schema` / `timeoutMs` 逐字一致；`execute` 为同源实现的新闭包
（工厂每次构建都会新建，**语义一致但不是同一根引用**，别拿引用相等当判据）：

```bash
# 同 deps 构建两工具后逐项比对（探针脚本，一次性）
node_modules/.bin/tsx /tmp/alias-probe.mts
# → parameters_identical=true output_schema_identical=true timeoutMs_identical=true
#   两工具声明键集合完全一致（12 键）：success/task_id/requirement_id/status/job_id/run_id/
#   running/next_ready/chain/parent_status/error/code
```

行为等价另有 `tests/task-run-contract.test.ts` TC-3 兜底：别名同样写 `autoRun`、同样返回 `status=dispatched` + `job_id/run_id`。

### 5.2 旧键兼容清单（老调用方不退化）

| 旧键 / 旧名 | 现状 | 依据 |
|---|---|---|
| 工具名 `reqboard_task_execute` | **保留**（删除会让存量调用方硬断，decision D-1 选 A），描述标"已弃用" | `tests/task-run-contract.test.ts` TC-3 |
| `reqboard_task_status.workflow` | **保留**（既有消费者契约），内容换为真实 run 摘要 `at/ok/stopReason/valueNonEmpty` | `tests/task-status-ledger.test.ts` TC-8（有 run）/ TC-9（无 run 时缺省、不伪造） |
| `task_move` 的 `task_card` / `subtasks_created` / `version` | 声明与返回同时在位（此前 `additionalProperties:false` 会把它们判成 invalid output） | `tests/output-contract.test.ts`、`tests/tools-schema.test.ts` |
| `reqboard_task_run` 旧声明键 `subtask_executed / blocked / stopped` | **不再声明也不再返回**——这三个键从未真实返回过，留着只是描述与行为脱节 | `tests/task-run-contract.test.ts` FR-2 |

### 5.3 回归结果（2026-09-27 本机实跑）

```bash
# ① 父卡点名的三条既有链路
node_modules/.bin/vitest run \
  packages/web/dsh-pmboard/tests/advance-chain.test.ts \
  packages/web/dsh-pmboard/tests/run-status-tool.test.ts \
  packages/web/dsh-pmboard/tests/task-transition-guard.test.ts
# → 3 passed：advance-chain 8 / run-status-tool 4 / task-transition-guard 5

# ② 本需求全部工具面契约与门禁（9 文件）
node_modules/.bin/vitest run \
  packages/web/dsh-pmboard/tests/advance-chain.test.ts \
  packages/web/dsh-pmboard/tests/run-status-tool.test.ts \
  packages/web/dsh-pmboard/tests/task-transition-guard.test.ts \
  packages/web/dsh-pmboard/tests/task-run-contract.test.ts \
  packages/web/dsh-pmboard/tests/task-tree.test.ts \
  packages/web/dsh-pmboard/tests/task-status-ledger.test.ts \
  packages/web/dsh-pmboard/tests/task-move-role.test.ts \
  packages/web/dsh-pmboard/tests/output-contract.test.ts \
  packages/web/dsh-pmboard/tests/tools-schema.test.ts
# → 9 passed / 104 tests passed

# ③ decompose-tools：5 项红，经干净 HEAD 对照确认为**预存在红**（非本需求引入）
git worktree add --detach /tmp/pmboard-head HEAD
#   干净 HEAD 需符号链接 node_modules（本仓 profile 用 tsx 直载，vitest 从工作区根解析依赖）
node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/decompose-tools.test.ts
# → 工作区 5 failed | 23 passed；HEAD 复跑同样 5 failed | 23 passed（逐条同名）
```

**判定**：① 三条既有链路全绿；② 本需求契约门禁全绿；③ `decompose-tools` 的 5 项红在 HEAD（改动前）逐一复现，
属**测试与 `reqboard_task_move` 返回契约的既有脱节**，不记在本需求账上（父卡验收口径即"除预存在红外全绿"）。

预存在红清单（5 项，逐条同名）：
`reqboard_decompose` 幂等守卫报错码顺序（期望 `REQBOARD_ALREADY_DECOMPOSED`，实得 `REQBOARD_TASKS_REQUIRED`）、
`task_move→in_progress` 未回 `task_card.acceptance`、`task_move` done 未回 `blockers/warning`、
未绑定窗口报错码（期望 `REQBOARD_NOT_BOUND_TO_WINDOW`，实得 `REQBOARD_NO_BOUND_REQ`）、
`task_move` 返回缺 `requirement_status`。

**复跑口径提醒**：判定"某红是不是本次引入"，一律以**同一测试文件在 HEAD 与工作区的失败集合是否逐条一致**为准，
不看单次运行总数（全仓当前有 26 个失败文件属其他工作线的预存在红，混在一起看会误判）。

### 5.4 接口联调样例（请求 → 期望 → 实际）

真工具面 + 内存端口（`tests/application/harness.ts`，`job-1` 为注入的后台端口桩返回）逐条实跑：

```bash
node_modules/.bin/tsx /tmp/integration-probe.mts   # 一次构建 5 个工具、8 条用例（含错误路径）
```

| # | 请求样例 | 期望响应 | 实际响应 |
|---|---|---|---|
| I-1 | `reqboard_task_run{task_id:"t-p"}` | `success=true` / `status=dispatched` / `job_id,run_id` 字符串 / `autoRun=true` | ✅ `job_id="job-1"`、`run_id="run-…"`、`autoRun=true`、`chain={done:0,total:2}` |
| I-1b | `reqboard_task_run{requirement_id:"REQ-000001"}` | 与 I-1 同形 | ✅ 键集合逐字一致（10 键，sorted 相等） |
| I-1c | `reqboard_task_run{}`（未绑定） | `success=false` + `REQBOARD_NO_BOUND_REQ` | ✅ 同 |
| I-1d | `reqboard_task_run{requirement_id:"REQ-999999"}`（跨窗口） | `success=false` + `REQBOARD_NOT_BOUND_TO_WINDOW` | ✅ 同 |
| I-2 | `reqboard_task_execute{task_id:"t-p"}` | 与 I-1 同键 + 同写 autoRun | ✅ `status=dispatched`、`job_id="job-1"`、`autoRun=true` |
| I-3 | `reqboard_task_tree{requirement_id:"REQ-000001"}` | 父卡 + 链序子卡（依赖关系透出） | ✅ `parents=1`、子卡 `[t-s1, t-s2(dependsOn:t-s1)]`、`lastRunOk` 可读 |
| I-4 | `reqboard_task_status{task_id:"t-s1"}` | 读台账 `lastRun`；`workflow` 旧键保留 | ✅ `run.ok=true` / `workflow={at,ok,stopReason,valueNonEmpty}` |
| I-5 | `reqboard_task_move{task_id:"t-p", to:"in_progress"}` | `from=todo` / `to=in_progress` | ✅ `version=2`、`task_card.doc_path=docs/requirements/REQ-000001/tasks/t-p.md` |

**结论**：8 条联调逐条命中期望；错误路径返回结构化 `code`（不静默当成功）；别名与主入口返回同形、同副作用。

## 参考

- 流水线全流程：[reqboard-pipeline-flow.md](reqboard-pipeline-flow.md)
- 文档路径契约：[reqboard-doc-path-contract.md](reqboard-doc-path-contract.md)
- 实测需求：[REQ-260927123256-196b](../requirements/REQ-260927123256-196b/requirement.md)
