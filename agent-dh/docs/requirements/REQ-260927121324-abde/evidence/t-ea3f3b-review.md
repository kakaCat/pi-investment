# t-ea3f3b 复核记录（父卡 t-15c076「看板任务流转/建卡改卡带写时快照」· 阶段 review）

- 复核时间：2026-09-27（本轮执行内）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `daa4169e`（branch `main`）· 测试工作目录 `packages/web/dsh-pmboard`
- 验收标准（本卡）：**对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据**
- 复核对象（t4 交付面 = 研发子卡 t-726c22 落盘的 `src/http/routers/tasks.ts` 三入口，diff 52 insertions / 19 deletions，仅此一个文件）：
  - `:118` 开工：`openExecution(task, { id: newExecutionId(), sessionId, trigger: actor === 'system' ? 'auto' : 'manual', at }, snapshotOf(sessionId))`
  - `:131` 收尾：`closeExecutions(task, { at, outcome: isRollbackOrCancel(to) ? 'cancelled' : 'succeeded' }, snapshotOf(sessionId))`
  - `:89` / `:142` / `:186` 派生推进：`applyTaskRollup(ledger, { now, commentId, snapshot: rollupSnapshot(sessionId) }, reqId)`（建卡 / 流转 / 改卡三入口）
  - `:39` `sessionIdOf` / `:47` `snapshotOf` / `:52` `rollupSnapshot`：会话码解析与快照取值单点化
- 设计依据（比对基线）：
  - `requirement.md` FR-4 / FR-5 / FR-6
  - `design/interfaces.md` §写路径助手（L13-37）、§执行快照助手（L68-104，尤其调用点表 L98-104）、§HTTP 入口（L106-120）、§错误与降级语义（L131-139）、§兼容性矩阵（L141-149）
  - `design/architecture.md` §收敛点 2（L93-100）、§唯一性纪律（L109-112）、§数据流（L114-135）、§逐条功能点实现要点 FR-4/5/6（L163-168）、§不做什么（L190-196）
  - `design/backend.md` §逐文件改动（任务执行）（L48-57）、§自动链与无会话路径（L59-68）
  - 父卡任务卡 `tasks/t-15c076.md`「得到什么结果」「实施方案」
- 复核方式：**只读复核 + `git diff` 逐行比对 + 独立复跑验收命令 + `tsc` 过滤**（不采信上游自述；联调记录 §3 仅作交叉参考）

---

## 0. 设计基线（判定依据）

| 依据 | 位置 | 关键约定 |
|---|---|---|
| 需求 | FR-4（requirement.md L198-205） | 看板 `tasks.ts` 在产生执行记录的同一步写 `tokenUsage.start`（当次会话四桶投影） |
| 需求 | FR-5（L207-213） | 任务离开执行段写 `end`；仅 start/end 同会话且均 projection 才产 `delta`，否则缺省（缺失 ≠ 0） |
| 需求 | FR-6（L215-220） | 持会话上下文的 rollup 调用点传 `snapshot` 提供者；无会话路径不传 |
| 接口 | interfaces L101 | 看板 `tasks.ts` 输入会话 = `body.sessionId`（可缺）；开工/收尾 `snap = sessionId ? ctx.deps.tokenSnapshot?.(sessionId) : undefined` |
| 接口 | interfaces L80-88 | `openExecution(task, spec, snap?)` / `closeExecutions(task, opts, snap?)`；snap=undefined → 只落/闭合记录，不写 token 字段 |
| 接口 | interfaces L111-112 | `POST /task/create`、`POST /task/update` 新增**可选** `sessionId?`，仅影响触发的 rollup 带快照；响应无变化 |
| 接口 | interfaces L110/L120 | `POST /task/move` 已有 `sessionId?`；响应形状不变 |
| 架构 | architecture L62/L93-100 | 任务执行收敛点 = 执行快照助手；调用方不得自行 `executions.push` |
| 架构 | architecture L109-112 | 唯一性纪律：`executions.push(` 与 `execution.tokenUsage` 写只允许出现在 `application/internal/token-usage.ts` |
| 架构 | architecture L119-124 | 开工 spec=`{ id, sessionId?, trigger, at }`；snap=undefined → 只落记录不写 token（原子性：抛错则状态/记录/快照三者都不落） |
| 后端 | backend L54 | `tasks.ts` 的 push → `openExecution`、收尾循环 → `closeExecutions`；**sessionId 缺省时不写 snap** |
| 后端 | backend L65-66 | 无窗口码路径明确不传 `snapshot`，保证「无会话不伪造」 |
| 父卡方案 | tasks/t-15c076.md L19 | `:110-118` 统一同一提供者，无会话不伪造；三入口同一口径 |

---

## 1. 逐条复核结论（设计 → 实现 → 判定）

| # | 设计点（出处） | 实测实现 | 结论 |
|---|---|---|---|
| R1 | 看板开工经**执行快照唯一入口**落记录 + 写 start（FR-4；interfaces L101；backend L54） | `tasks.ts:118-122` 调 `openExecution(task, {id,sessionId,trigger,at}, snapshotOf(sessionId))`；原 `task.executions.push(...)` 已删除（diff `-1/+6`） | **无偏离** |
| R2 | 看板收尾经**执行快照唯一入口**闭合全部 running + 写 end/delta（FR-5；interfaces L101；backend L54） | `tasks.ts:131-135` 调 `closeExecutions(task, {at, outcome: isRollbackOrCancel(to) ? 'cancelled' : 'succeeded'}, snapshotOf(sessionId))`；原 `for (const exec of ...)` 循环删除 | **无偏离** |
| R3 | 开工/收尾**字段映射等价**（interfaces L72-79；architecture L119-124） | 旧 push 的 `{id, sessionId, trigger: actor==='system'?'auto':'manual', startedAt: at, outcome: 'running'}` 由 `openExecution` 逐字段还原（`at→startedAt`、`outcome` 缺省 running）；收尾 `endedAt/outcome` 逐字保留，未新增 `error` | **无偏离**（原 push 分支已被整段替换，无残留） |
| R4 | `/task/create` 与 `/task/update` 新增**可选** `sessionId` 请求字段（interfaces L111-112） | `:59`（create）与 `:163`（update）新增 `const sessionId = sessionIdOf(body)`；`:39` `sessionIdOf` = `normalizeText(body.sessionId,'sessionId',128) || undefined` | **无偏离** |
| R5 | 三处触发 rollup 的入口补 `snapshot` 提供者（FR-6；architecture L167；backend L54） | `:89-93`（create）、`:142-146`（move）、`:186-190`（update）三处 `applyTaskRollup` 的 ctx 均带 `snapshot: rollupSnapshot(sessionId)` | **无偏离** |
| R6 | 三入口**统一同一提供者**、有会话才给、无会话不伪造（父卡方案 L19；backend L65-66） | 会话码解析唯一（`sessionIdOf`）、快照取值唯一（`snapshotOf`）、rollup 提供者唯一（`rollupSnapshot`）；`sessionId===undefined` 时三处均返回 `undefined`（`rollup.ts:62` `snap: ctx.snapshot?.(req)` ⇒ 不结算不带快照） | **无偏离** |
| R7 | 响应形状不变（interfaces L108/L110/L120） | `handleTaskCreate` 仍 `ok(res, record)`；`handleTaskMove`/`handleTaskUpdate` 仍 `ok(res, result.changed.tasks[0])`；diff 未触碰返回体 | **无偏离** |
| R8 | 错误码/语义面不变（requirement §接口；接口表 L110-116） | diff 未触碰 `notFound` / `asActor` / `asTaskStatus` / `normalizeText` 异常路径与 `transitionTask` 调用；联调 D-4a..f（404 / 400 / 403）与本卡验收命令独立通过 | **无偏离** |
| R9 | 唯一性纪律：`tasks.ts` 不得出现 `executions.push(` / `tokenUsage` 写（architecture L109-112） | `grep -nE "tokenUsage|executions\\.push" src/http/routers/tasks.ts` → **无输出（exit=1）**；执行记录增改只经 `openExecution`/`closeExecutions` | **无偏离** |
| R10 | 无会话不落执行记录属**既有契约**（interfaces L101 输入会话「可缺」；非本卡缺口） | `startsExecutionSegment(to) && sessionId` 条件**未被改动**（HEAD 同形）；无会话时 `executions:[]`、不认领、`snapshotOf(undefined)=undefined` 不写任何 token 字段 | **无偏离**（与联调 B-3/B-4/D-1 一致） |
| R11 | `sessionId` 解析语义：缺省/空串 → `undefined`；非字符串 → `400 invalid_input` | 经既有 `normalizeText`（`protocol.ts:1289-1295`）：`undefined/null → ''` → `|| undefined`；非字符串 `bad()` → 400；超 128 字 → 400 | **无偏离** |
| R12 | 父卡验收命令（`tasks/t-15c076.md` L16） | `npx vitest run tests/routes-rollup.test.ts tests/rollup.test.ts` → **2 files / 19 tests passed**；`grep -n "executions.push(" src/http/routers/tasks.ts` → **无输出** | **无偏离** |
| R13 | 类型面：按助手新签名消费（backend L50-54） | `npx tsc --noEmit -p tsconfig.json` 输出中 grep `routers/tasks.ts|internal/token-usage.ts` → **无输出（0 条）** | **无偏离** |
| R14 | 边界：不回填、不改 schema、不动端侧（architecture L190-196） | diff 只含 tasks.ts；无 schemaVersion / client 侧改动 | **无偏离** |

**汇总：14/14 项「无偏离」。**

---

## 2. 观察项（不构成偏离，如实报备）

| # | 观察 | 判定与依据 |
|---|---|---|
| O1 | `interfaces.md L119` 有一句**一般性**表述「会话码取值优先级：请求体 sessionId → 需求的 `sourceSessionId`；都没有则不传」。任务三条路由**未**退回 `req.sourceSessionId`，只取 `body.sessionId`。 | 按 **t4 专属契约**判定：interfaces L101 明确「看板 `tasks.ts` 输入会话 = `body.sessionId`（可缺）」、backend L54「sessionId 缺省时不写 snap」、父卡方案 L19「有 sessionId 才给」——实现与之逐字一致 ⇒ **无偏离**。该优先级在需求路由确有落地（`requirements.ts:115` `sessionId ?? req.sourceSessionId`；`verdicts.ts:108/177` 取 `r.sourceSessionId`），属需求迁移面（t2）。如实声明：L119 的措辞未限定适用面，与任务面专属契约存在**文档措辞落差**（非本卡实施缺陷，建议后续在 L119 补一句「任务面仅取 body.sessionId」）。 |
| O2 | 全量套件（`npx vitest run`，本次 203 files / 2230 tests）有 **27 files / 53 tests failed**。 | **不在本卡调用面**：①无任何测试 import `http/routers/tasks`（`grep -rl "routers/tasks|createTasksRouter" tests` → 0）；②唯一走 `/task/*` 路由的 `tests/routes-rollup.test.ts` **全绿**；③抽样根因均在别处——`tests/decompose-tools.test.ts:443` 断言工具返回的 `requirement_status` 为 `undefined`（工具面契约，非 HTTP 路由），`tests/typecheck.test.ts` 报 `src/application/internal/accept-sheet-rtm-integration.ts(45,9) TS2322`（该文件工作区未改，`git status` 无该文件）。**未做 HEAD 基线对照**（工作区含他卡在途改动，不适合批量覆盖），故只报事实、不宣称「已证预存」，也不作为本卡判定依据。 |

---

## 3. 复核证据（命令与输出摘要）

```
$ git --no-pager diff --numstat -- packages/web/dsh-pmboard/src/http/routers/tasks.ts
52	19	agent-dh/packages/web/dsh-pmboard/src/http/routers/tasks.ts
（diff 全文逐行比对：仅 ① import 执行助手；② sessionIdOf/snapshotOf/rollupSnapshot 三个单点函数；
 ③ create/update 读 sessionId；④ push → openExecution；⑤ 收尾 for → closeExecutions；
 ⑥ 三处 applyTaskRollup 补 snapshot——未触碰任何其他逻辑）

$ grep -nE "openExecution|closeExecutions|snapshotOf|rollupSnapshot|sessionIdOf|applyTaskRollup" src/http/routers/tasks.ts
24:import { applyTaskRollup } ...
25:import { closeExecutions, openExecution } ...
39:  function sessionIdOf(...)      47:  function snapshotOf(...)      52:  function rollupSnapshot(...)
59 / 105 / 163:  const sessionId = sessionIdOf(body)      ← create / move / update 三入口
89 / 142 / 186:  applyTaskRollup({ ... snapshot: rollupSnapshot(sessionId) }, ...)
118: openExecution(...)   121: snapshotOf(sessionId)
131: closeExecutions(...) 134: snapshotOf(sessionId)

$ grep -nE "tokenUsage|executions.push" src/http/routers/tasks.ts
（无输出 → exit=1）

$ grep -n "executions.push(" src/http/routers/tasks.ts
（无输出 → exit=1）

$ npx vitest run tests/routes-rollup.test.ts tests/rollup.test.ts
 ✓ tests/rollup.test.ts (16 tests) 4ms
 ✓ tests/routes-rollup.test.ts (3 tests) 159ms
 Test Files  2 passed (2)      Tests  19 passed (19)

$ npx vitest run tests/ledger-v6-token.test.ts tests/token-usage.test.ts tests/execution-snapshot-helpers.test.ts
 ✓ tests/token-usage.test.ts (11 tests)
 ✓ tests/execution-snapshot-helpers.test.ts (14 tests)
 ✓ tests/ledger-v6-token.test.ts (8 tests)
 Test Files  3 passed (3)      Tests  33 passed (33)

$ npx tsc --noEmit -p tsconfig.json | grep -E "routers/tasks.ts|internal/token-usage.ts"
（无输出 → 0 条 error）
```

（复核为只读操作，未改动任何源码；本记录即本卡唯一新增文件。）
