# t-fdecb4 复核记录（父卡 t-030788「agent 任务执行与中途汇报改经执行助手」· 阶段 review）

- 复核时间：2026-09-27（本轮执行内）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `daa4169e`（branch `main`）· 测试工作目录 `packages/web/dsh-pmboard`
- 验收标准（本卡）：**对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据**
- 复核对象（t3 交付面 = 研发子卡 t-eaafd0 落盘的 4 个接线点）：
  - `MoveTask.ts:115-119` 开工：`openExecution(task, { id: newExecutionId(), sessionId: windowKey, trigger: 'manual', at }, snapshotForWindow(deps, windowKey))`
  - `MoveTask.ts:132-136` 收尾：`closeExecutions(task, { at, outcome: isRollbackOrCancel(to) ? 'cancelled' : 'succeeded' }, snapshotForWindow(deps, windowKey))`
  - `MoveTask.ts:141-145` 派生推进：`applyTaskRollup(ledger, { now, commentId, snapshot: snapshotProviderFor(deps, windowKey) }, reqId)`
  - `ReportTask.ts:16/123/135` 中途汇报：`refreshRunningExecution(tk, snap, windowKey)`（`snap = captureSnapshot(deps, windowKey)`）
- 设计依据（比对基线）：
  - `requirement.md` FR-4（L198-205）、FR-5（L207-213）、FR-6（L215-220）
  - `design/interfaces.md` §执行快照助手（L68-104，尤其调用点表 L98-104）、§Agent 工具入口（L122-127）、§错误与降级语义（L131-139）
  - `design/architecture.md` §收敛点 2（L93-100）、§唯一性纪律（L109-112）、§数据流（L114-135）、§逐条功能点实现要点 FR-4/5/6（L163-168）
  - `design/backend.md` §逐文件改动（任务执行）（L48-57）
  - 父卡任务卡 `tasks/t-030788.md`「得到什么结果」「实施方案」（L16、L19）
- 复核方式：**只读复核 + `git diff` 逐行比对 + 独立复跑验收命令 + `tsc` 过滤**（不采信上游自述）

---

## 0. 设计基线（判定依据）

| 依据 | 位置 | 关键约定 |
|---|---|---|
| 需求 | FR-4（requirement.md L198-205） | agent `MoveTask.ts` 在 push 执行记录的同一步写入 `tokenUsage.start`（当次会话四桶投影） |
| 需求 | FR-5（L207-213） | 任务离开执行段写 `end`；`reqboard_task_report` 中途刷新也写 `end`；仅两端同会话且均为 projection 才产 `delta`，否则缺省（缺失 ≠ 0） |
| 需求 | FR-6（L215-220） | `MoveTask` 等持会话上下文的 rollup 调用点传 `snapshot` 提供者；无会话路径不传 |
| 接口 | interfaces L100 | agent `MoveTask.ts` 输入会话 = `windowKey`（真实 agent 会话）；开工 `openExecution(..., snapshotForWindow(deps, windowKey))`；收尾 `closeExecutions(..., snapshotForWindow(deps, windowKey))` |
| 接口 | interfaces L104 | 中途汇报 `ReportTask.ts`：`refreshRunningExecution(task, snap, windowKey)` |
| 接口 | interfaces L80-88 | `openExecution(task, spec, snap?)` / `closeExecutions(task, opts, snap?)` / `refreshRunningExecution(task, snap, sessionId?)`；refresh **不改 outcome** |
| 接口 | interfaces L126-127 | `reqboard_task_move` / `reqboard_task_report` 入参与错误码**不变**；响应形状不变 |
| 架构 | architecture L62/L93-100 | 任务执行收敛点 = 上述 3 个执行助手；`beginExecutionToken` 复活（不再是死代码） |
| 架构 | architecture L109-112 | 唯一性纪律：`task.executions` 的增改（`executions.push(`）与 `execution.tokenUsage` 的写只允许出现在 `application/internal/token-usage.ts` |
| 架构 | architecture L119-135 | 开工 spec=`{ id, sessionId?, trigger, at }`；snap=undefined → 只落记录不写 token；delta 三条件（两端 projection + 会话不冲突） |
| 架构 | architecture L167-168 | FR-6：`MoveTask.ts`（agent）补 `snapshot`；启动对账等无会话路径明确不传 |
| 后端 | backend L52-53/L57 | `MoveTask.ts` 的 push → `openExecution`、收尾循环 → `closeExecutions`；`ReportTask.ts:133-138` 循环 → `refreshRunningExecution(tk, snap, windowKey)` |
| 父卡方案 | tasks/t-030788.md L16/L19 | 与后端设计逐字一致 |

---

## 1. 逐条复核结论（设计 → 实现 → 判定）

| # | 设计点（出处） | 实测实现 | 结论 |
|---|---|---|---|
| R1 | 开工落记录 + 写 start（FR-4；interfaces L100；backend L52） | `MoveTask.ts:115-119` 调 `openExecution(task, {id,sessionId:windowKey,trigger:'manual',at}, snapshotForWindow(deps, windowKey))`；原 `task.executions.push(...)` 已删除（diff -1/+6） | **无偏离**（§3.1/§3.2） |
| R2 | 开工 spec 字段等价（interfaces L72-79：id/sessionId/trigger/at/outcome?） | 旧 push 的 `{id, sessionId:windowKey, trigger:'manual', startedAt:at, outcome:'running'}` 由 `openExecution` 逐字段还原（`at→startedAt`、`outcome` 缺省 running），额外写 `start`——正是 FR-4 要补的 | **无偏离**（§3.1；t1 契约测试 `execution-snapshot-helpers.test.ts` 锁定字段映射） |
| R3 | 收尾闭合全部 running + 写 end/delta（FR-5；interfaces L100；backend L53） | `MoveTask.ts:132-136` 调 `closeExecutions(task, {at, outcome: isRollbackOrCancel(to) ? 'cancelled' : 'succeeded'}, snapshotForWindow(deps, windowKey))`；旧 for 循环删除，outcome 映射逐字保留 | **无偏离**（§3.1/§3.4） |
| R4 | 中途汇报刷新（FR-5；interfaces L104；backend L57） | `ReportTask.ts:16` 导入 `refreshRunningExecution`，`:135` 调 `refreshRunningExecution(tk, snap, windowKey)`（`snap` 由 `:123` `captureSnapshot(deps, windowKey)` 得）；旧"尾部反查 + `endExecutionToken`"循环删除 | **无偏离**（§3.1/§3.4） |
| R5 | refresh **不改 outcome**（interfaces L87；FR-5） | 助手 `token-usage.ts:192-201` 只调 `endExecutionToken`（不触碰 outcome）；`ledger-v6-token` 断言刷新后 `e.outcome==='running'` 且 `end/delta` 已写 | **无偏离**（§3.4） |
| R6 | 会话码 = `windowKey` 真实 agent 会话（interfaces L100；architecture L120） | `MoveTask.ts:62` `windowKey = agentIdFromExec(deps, exec)` → `deps.session.windowKey(exec) = exec.agent.id`（缺失即抛 `REQBOARD_AGENT_REQUIRED`）；与设计"agent 用 windowKey"一致（未误用 `safeWindowKey`） | **无偏离**（§3.1） |
| R7 | 派生推进带 snapshot 提供者（FR-6；architecture L167；backend L48-57） | `MoveTask.ts:141-145` `applyTaskRollup(ledger, { now, commentId, snapshot: snapshotProviderFor(deps, windowKey) }, reqId)` | **无偏离**（§3.1） |
| R8 | refresh 会话过滤语义（interfaces L86-87） | 助手按 `e.outcome!=='running' → skip` + `sessionId!==undefined && e.sessionId!==sessionId → skip` 严格匹配；`windowKey` 恒为校验过的非空 id，故与旧循环 `e.sessionId !== windowKey` 语义等价 | **无偏离**（§3.1/§3.4） |
| R9 | 唯一性纪律：`MoveTask.ts`/`ReportTask.ts` 不得再直写（architecture L109-112） | `grep -rn "executions.push("` 两文件 **0 命中**；`grep -nE "tokenUsage"` 两文件 **0 命中**；两文件 token 写入只经助手（§3.2） | **无偏离**（§3.2） |
| R10 | 错误码面不变（interfaces L126-127；requirement L264-265） | diff 未触碰任何 `reject(...)` 路径与文案；独立复跑覆盖 `REQBOARD_HUMAN_GATE`（use-cases.test.ts:167-168）、`REQBOARD_INVALID_INPUT`、`REQBOARD_TASK_NOT_FOUND`、`REQBOARD_NOT_BOUND_TO_WINDOW` 全绿 | **无偏离**（§3.6） |
| R11 | 返回体形状不变（interfaces L120/L126-127） | diff 中 `return { success, task_id, from, to, status, version, ... }` 与 ReportTask 返回对象**零改动** | **无偏离**（§3.1） |
| R12 | delta 不变式：仅两端 projection + 同会话（FR-5；data-model L74-76） | 复用既有 `endExecutionToken`（未改）；`ledger-v6-token` 三例：projection→projection 产 delta=B(3)、unavailable → delta 缺省、跨会话不产 | **无偏离**（§3.4） |
| R13 | `beginExecutionToken` 复活（architecture L16/L62） | `grep -rn beginExecutionToken src/` → 定义（:86）+ 真实调用方 `token-usage.ts:159`（`openExecution` 内）；t3 接线后 agent 路径首次经它落 start | **无偏离**（§3.2） |
| R14 | FR-9 回归：既有 token 单测全绿 | `npx vitest run tests/ledger-v6-token.test.ts tests/token-usage.test.ts tests/token-transition-helper.test.ts tests/token-fallback.test.ts` → 全绿（下 §3.3 父卡口径）；`ledger-v6-token` 由 3 red 转 0 red | **无偏离**（§3.3/§3.4） |
| R15 | 类型面：按新签名消费助手 | `npx tsc --noEmit -p tsconfig.json` 输出中 grep `MoveTask|ReportTask` **无输出**（0 条 error；包内另有 117 条存量 error，全部落在与本卡无关文件） | **无偏离**（§3.5） |

---

## 2. 偏离与观察项

**总判定：t3「agent 任务执行与中途汇报改经执行助手」设计与实现——无偏离（R1–R15 全过，无一条需要返工）。** 下列 4 条为不阻断的观察项（行号漂移 / 路径可达性说明 / 上游设计计数笔误 / 跨卡范围），均不影响本卡契约与父卡验收。

### O-1（文档行号漂移 · 不构成偏离）
设计/父卡引用的是**改动前**行号（`MoveTask.ts:108/:120-123/:127`、`ReportTask.ts:133-138`）；接线后实现落在 `MoveTask.ts:115/:132/:141` 与 `ReportTask.ts:135`。逐字比对语义一致（§3.1），纯 diff 位移。**判定：不构成偏离。**

### O-2（agent 路径 snap 必为 projection|unavailable · 符合设计 · 不构成偏离）
`MoveTask` 的 `windowKey` 先经 `agentIdFromExec` 校验为**非空**真实 agent id（缺失即抛），故 `snapshotForWindow(deps, windowKey)` 在本路径**不会**返回 `undefined`（要么 projection，要么端口异常时 `unavailable`）。这正是 interfaces L100 为 agent 指定的 `snapshotForWindow(deps, windowKey)` 口径；`snap=undefined → 不写 token` 分支由看板（无 `sessionId`）与自动链（`system`/解析不到）路径覆盖，属 t4/t5 范围。**判定：不构成偏离**（口径出处 interfaces L35-37/L92/L100）。

### O-3（设计汇总句计数笔误「4 个助手」· 不属本卡 · 不构成偏离）
`design/interfaces.md:10` / `design/backend.md:18` 的汇总句写"新增 4 个助手"，而逐条定义与实现均为 6 个导出。该矛盾已在 t1 复核 `evidence/t-f9462e-review.md` §2 D-1 记录并建议文档同步时更正，**与本卡（t3 接线）无关**。**判定：不构成偏离。**

### O-4（跨卡范围 · 另三处执行产生点仍直写 `executions.push(` · 不构成 t3 偏离）
`grep -rn "executions.push(" src/` 现命中：`src/http/routers/tasks.ts:90`（t4 / t-15c076）、`src/application/use-cases/AdvanceChain.ts:141` 与 `ExecuteTask.ts:252`（t5 / t-00bed8），以及助手内唯一写点 `token-usage.ts:160`。这三处**不在本卡交付面**（父卡拆分表与联调记录 §4 均已声明）：**判定：不构成 t3 偏离**；诚实提示——FR-8「唯一入口」须待 t4/t5 接线完成后闭合。

---

## 3. 复核证据（命令与输出）

### 3.1 改动面逐行比对（`git diff`）
```
$ cd /Users/yunpeng/pi-investment
$ git diff --stat -- agent-dh/packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts agent-dh/packages/web/dsh-pmboard/src/application/use-cases/ReportTask.ts
 MoveTask.ts  | 28 ++++++++++++++++++----
 ReportTask.ts | 11 ++++-----
 2 files changed, 27 insertions(+), 12 deletions(-)
```
diff 只含 4 处：① import 4 个助手；② push → `openExecution`；③ for 闭合 → `closeExecutions`；④ rollup 补 `snapshot`；⑤ ReportTask 循环 → `refreshRunningExecution`。**未触碰** `reject(...)`、`return {...}`、`transitionTask`、`assertDoneEvidence`、`expandSubtasks` 等既有逻辑。

### 3.2 收敛面静态复核（源码 + grep 独立执行）
```
$ cd packages/web/dsh-pmboard
$ grep -rn "executions.push(" src/application/use-cases/MoveTask.ts src/application/use-cases/ReportTask.ts ; echo "grep-exit:$?"
grep-exit:1                          # 两文件 0 命中
$ grep -nE "tokenUsage" src/application/use-cases/MoveTask.ts src/application/use-cases/ReportTask.ts ; echo "grep-exit:$?"
grep-exit:1                          # 两文件 0 命中（token 字段只在助手内写）
$ grep -nE "openExecution|closeExecutions|snapshotForWindow|snapshotProviderFor|refreshRunningExecution" src/application/use-cases/MoveTask.ts src/application/use-cases/ReportTask.ts
MoveTask.ts:115 openExecution(...)   MoveTask.ts:118 snapshotForWindow(deps, windowKey)
MoveTask.ts:132 closeExecutions(...) MoveTask.ts:135 snapshotForWindow(deps, windowKey)
MoveTask.ts:143 snapshotProviderFor(deps, windowKey)
ReportTask.ts:16  import { captureSnapshot, refreshRunningExecution } ...
ReportTask.ts:135 refreshRunningExecution(tk, snap, windowKey)
$ grep -rn "beginExecutionToken" src/
src/application/internal/token-usage.ts:86   （定义）
src/application/internal/token-usage.ts:159  （openExecution 内真实调用方 → 不再是死代码）
```

### 3.3 父卡验收命令（5 文件口径，独立复跑）
```
$ npx vitest run tests/ledger-v6-token.test.ts tests/task-report.test.ts tests/execution-snapshot-helpers.test.ts tests/token-usage.test.ts tests/application/use-cases.test.ts
 Test Files  5 passed (5)
      Tests  61 passed (61)
   Duration  762ms        # exit 0
```

### 3.4 本卡核心行为（ledger-v6-token 逐例，写时快照：任务执行 3 例由红转绿）
```
$ npx vitest run tests/ledger-v6-token.test.ts --reporter=verbose
 ✓ REQ-a33899 t3 · 写时快照：任务执行 > 开工写 start；完工（canceled）写 end 与 delta
 ✓ REQ-a33899 t3 · 写时快照：任务执行 > 中途汇报刷新 running 执行的 end/delta（进度检查点）
 ✓ REQ-a33899 t3 · 写时快照：任务执行 > 快照不可得 → start/end 记 unavailable，delta 不产出（禁止编造）
 Test Files  1 passed (1)  /  Tests  8 passed (8)   # exit 0
```
三例直接驱动 `executeMoveTask`/`executeReportTask`（真实窗口码 `EXEC`）：断言 `executions[0].tokenUsage.start.totals === B(2)`、完工 `end.totals === B(5)` 且 `delta === B(3)`；汇报后 `outcome === 'running'`；unavailable 时不产 delta。

### 3.5 类型面过滤
```
$ npx tsc --noEmit -p tsconfig.json 2>&1 | tee /tmp/t3_tsc.txt | grep -E "MoveTask|ReportTask"
（无输出）                          # 两文件 0 条 error
$ grep -cE "error TS" /tmp/t3_tsc.txt
     117                            # 全部为与本卡无关文件的存量报错
```

### 3.6 错误码与边界（既有用例覆盖，本卡未改动）
```
tests/application/use-cases.test.ts:167  executeMoveTask({to:'canceled'}) → REQBOARD_HUMAN_GATE
tests/task-report.test.ts               summary 为空 → REQBOARD_INVALID_INPUT（7 tests passed）
```
diff 零触碰这些分支；61 例中相关用例全绿（§3.3）。

---

## 4. 结论

- **t3「agent 任务执行与中途汇报改经执行助手」设计与实现：无偏离。** R1–R15 全部满足设计基线（requirement FR-4/5/6 + interfaces §执行快照助手/调用点表/错误与降级语义 + architecture §收敛点2/唯一性纪律/数据流 + backend §逐文件改动（任务执行）+ 父卡任务卡）：4 个接线点逐字落位，开工写 start、收尾闭合写 end/delta、中途刷新不改 outcome、rollup 带 snapshot 提供者，agent 会话码用真实 `windowKey`，两文件 0 条直写（唯一性纪律成立），错误码与返回形状不变。
- 与设计文本的不一致仅为**行号漂移**（O-1）与**上游设计汇总句计数笔误**（O-3，已在 t1 复核记为 D-1），均不构成实现偏离。
- 观察项 O-2（agent 路径 snap 必为 projection|unavailable）是设计口径的正常推论；O-4（tasks.ts / AdvanceChain.ts / ExecuteTask.ts 仍直写）属 t4/t5 范围，FR-8「唯一入口」待其收口后闭合。
- 复核证据：`git diff` 逐行（2 files / +27 / -12）· 5 files / 61 tests 全绿 · `ledger-v6-token` 8/8（含任务执行 3 例）· `tsc` 两文件 0 error · 收敛面 grep 0 直写。

复核人：实施子代理（t-fdecb4）；时间：2026-09-27
