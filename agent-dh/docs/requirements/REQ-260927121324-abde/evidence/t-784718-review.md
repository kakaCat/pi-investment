# t-784718 复核记录（REQ-260927121324-abde · 父卡 t-00bed8「自动链任务执行与接手推进改经执行助手并带快照」· 阶段 review）

> 验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据。
> 总判定：**核心设计落点 13/13 全部落位，无阻断性偏离、无需返工**；另有 **2 条偏离**（D-1 设计内部口径不一致、D-2 未登记行为改动）+ **3 条观察项**，均不阻断本卡验收，但 D-1/D-2 需在文档/RTM 侧收口。

## 0. 复核对象与设计基线（R-013 标注来源）

**设计基线**（均为 REQ-260927121324-abde）：
- requirement.md FR-4 / FR-5 / FR-6；
- design/architecture.md L163-168（FR-4/FR-6 实现要点）、L109-112（唯一性纪律）、L116-135（数据流）；
- design/backend.md L48-57（逐文件改动·任务执行）、L59-68（自动链与无会话路径）；
- design/interfaces.md L90-94（错误与降级语义）、L96-104（调用点表）；
- 任务卡 tasks/t-00bed8.md L15-19（得到什么结果 / 实施方案）。

**实现**（工作区根 = /Users/yunpeng/pi-investment/agent-dh）：
- packages/web/dsh-pmboard/src/application/use-cases/AdvanceChain.ts
- packages/web/dsh-pmboard/src/application/use-cases/ExecuteTask.ts
- packages/web/dsh-pmboard/src/application/internal/token-usage.ts（t1 契约，本卡复用）
- packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts
- packages/web/dsh-pmboard/src/index.ts

---

## 1. 逐条复核结论（设计 → 实现 → 判定）

| # | 设计点（出处） | 实测实现 | 结论 |
|---|---|---|---|
| R1 | 自动链父卡开工改经执行助手（FR-4；backend L55；interfaces L102） | `AdvanceChain.ts:151-161`：`sessionKey = safeWindowKey(deps, exec) ?? req.sourceSessionId`；`openExecution(parent, {id, trigger:'auto', at:now, …(sessionKey?{sessionId}:{})}, snapshotForWindow(deps, sessionKey))`；原 `parent.executions.push(...)` 已删除 | **无偏离** |
| R2 | 自动链父卡收尾改经执行助手（FR-5；backend L55；interfaces L102） | `AdvanceChain.ts:191-193`：`sessionKey = safeWindowKey(deps, exec) ?? parentReq?.sourceSessionId`；`closeExecutions(parent, {at:now, outcome:'succeeded'}, snapshotForWindow(...))`；旧 `for(...) e.endedAt=e.outcome=...` 循环已删除 | **无偏离** |
| R3 | rollup 补 snapshot 提供者（FR-6；architecture L167；backend L55） | `AdvanceChain.ts:229-233`：`applyTaskRollup(ledger, {now, commentId, snapshot: snapshotProviderFor(deps, safeWindowKey(deps, exec))}, requirementId)` | **无偏离** |
| R4 | 自动链子卡开工改经执行助手，born-failed 不写 start（FR-4；interfaces L93；backend L55） | `ExecuteTask.ts:150` 解析 sessionKey；`:267-277` `openExecution(t, {id, trigger:'auto', at:startedAt, …(sessionKey?{sessionId}:{}), …(outcome.ok?{}:{outcome:'failed', error})}, snapshotForWindow(...))`；助手 `token-usage.ts:156/159`：failed 时写 `endedAt=at` 且**不调** `beginExecutionToken` | **无偏离** |
| R5 | 自动链子卡成功收尾（FR-5；backend L55） | `ExecuteTask.ts:305`：`closeExecutions(t, {at:doneAt, outcome:'succeeded'}, snapshotForWindow(deps, sessionKey))`；旧 for 循环已删除 | **无偏离** |
| R6 | 自动链子卡失败收尾 + error 落账（FR-5；backend L55；architecture L131-134） | `ExecuteTask.ts:317`：`closeExecutions(t, {at:failedAt, outcome:'failed', error:reason}, snapshotForWindow(deps, sessionKey))` | **无偏离** |
| R7 | 会话码 safeWindowKey 解析，`'system'` 视为无会话（FR-4；backend L56/L63-64） | 助手 `token-usage.ts:216-224`：缺 agent / `'system'` / 抛错 → `undefined`；子卡路径 `input.windowKey='system'` 不再落 `sessionId`（条件展开）；父卡 `trigger='auto'` 与旧记录字段等价（旧 push 本就无 sessionId） | **无偏离** |
| R8 | 解析不到 → 退 `req.sourceSessionId`，再无则诚实不写（architecture L164；interfaces L102 父卡） | 父卡 `AdvanceChain.ts:151/192` ✓ 与 interfaces L102 逐字一致；子卡 `ExecuteTask.ts:150` 用 `req?.sourceSessionId`（符合 architecture L164，与 interfaces L103 字面不一致 → **见 D-1**） | 父卡 **无偏离**；子卡 **D-1** |
| R9 | `snap=undefined` → 只落/闭合记录、不写 token 字段（interfaces L92；FR-4/6 缺口语义） | 助手 `token-usage.ts:159`（`outcome==='running' && snap!==undefined`）与 `:182`（`snap!==undefined` 才 `endExecutionToken`）；`snapshotForWindow:207-210` 空/缺码 → undefined | **无偏离** |
| R10 | 接手推进（派生推进）带快照提供者（FR-6；backend L67-68；architecture L167） | `pm-capture-root.ts:135-137`：`snapshotProviderFor(deps.useCaseDeps(), windowKey)` → `applyPickupAdvance(ledger, d.id, {now, commentId, snapshot})` | **无偏离**（写法差异见 O-2） |
| R11 | 启动对账明确不传 snapshot（FR-6；backend L65-66；architecture L168） | `index.ts:167`：`const ctx: RollupContext = { now, commentId }`（**无** snapshot）；`applyPickupReconcile / applyTaskRollup` 共用该 ctx，推进行为不变 | **无偏离** |
| R12 | 唯一性纪律：src 内 `executions.push(` / `tokenUsage` 写点只在助手（architecture L109-112） | `grep -rn "executions.push(" src/application src/http` → 仅 `token-usage.ts:113`（注释）+ `:160`（唯一写点）；`tokenUsage` 赋值 grep → 仅 `QueryRequirementToken.ts:108`（读判定，非写） | **无偏离**（字面差异见 O-1） |
| R13 | 错误语义不变：助手不抛、非法状态由 `transitionTask` 拦（interfaces L91） | `openExecution`/`closeExecutions` 无 throw；`AdvanceChain` 保留 `transitionTask`/`assertDoneEvidence` 与既有 step 语义；`ExecuteTask` 保留错误码（`REQBOARD_SUBTASK_GATE` 等）与返回形状，diff 未触碰 `reject`/`return` 路径 | **无偏离** |

---

## 2. 偏离清单

### D-1（设计内部口径不一致 → 实现选 architecture 口径）

- **设计两处冲突**：`design/interfaces.md:103`「自动链子卡 `ExecuteTask`：`safeWindowKey(deps, input.exec)` ?? `input.windowKey`（`'system'` 视为无）」——即 system 驱动时**不落快照**；`design/architecture.md:164`「自动链父卡/子卡用 `safeWindowKey(deps, exec)`（解析不到则**退 `req.sourceSessionId`**，再不行不写）」。
- **实现取值**：`ExecuteTask.ts:150` 用 `safeWindowKey(deps, input.exec) ?? req?.sourceSessionId`，即 **architecture 口径**；联调证据 I-4d 明确断言了该回落（`evidence/t-00bed8-integrate.md`：「需求 sourceSessionId=session-req-fallback → 会话码回落需求绑定窗口，start/end/delta 齐备」）。
- **结论**：**实现与 architecture 一致，对 interfaces 表格字面构成偏离**。行为差异仅在「exec=system 且需求已有 sourceSessionId」一处：interfaces 口径留空，architecture 口径把该执行消耗归到需求绑定窗口。属**设计文档内部矛盾**，不是实现错误；**建议把 interfaces.md:103 更正为 `?? req.sourceSessionId`（或注明以 architecture 为准）**，代码无需返工（文档收口属 t10 范围）。
- 依据：`ExecuteTask.ts:150`；`architecture.md:164`；`interfaces.md:103`；`t-00bed8-integrate.md` I-4d。

### D-2（实现含未在本卡设计与计划中登记的行为改动）

- 当前工作区 `ExecuteTask.ts`（本卡复核对象）的 diff 中夹带 2 处非本卡计划改动：

  1. **路径口径修复**：`buildSubtaskPrompt` 增加 `workspaceRoot` 契约（`:74-105`）、产出过 `normalizeArtifactPath`（`:213-225`）。→ **已由 t-030788 任务卡汇报 2 登记**（`tasks/t-030788.md:56/65`），属另一父卡交付，非本卡范围。
  2. **`claimedAt` 取值改为 workflow 开工时刻**：`:173` 新增 `const startedAt = deps.clock.now()`（置于 `deps.workflow.start` 之前）、`:264` `t.claimedAt = startedAt`（原为 run 结束后的 `ranAt`）。→ **本需求全部文档无落点**（grep `claimedAt` 仅命中 evidence 与 data-model 字段表，无「开工时刻取 workflow 前」条目）。
- **结论**：**对本卡实施方案（`tasks/t-00bed8.md:19`）构成范围偏离**，但功能正确，且是自动链能跑通的必要修复——`support.ts:124` `const since = task.claimedAt ?? task.createdAt` 是 done 凭证门的比对基准，`claimedAt`=run 结束时刻会让子代理写入文件的 mtime 恒早于 since，子卡恒不过门（`advance-log.md` 多次实测复现：`t-86bafa` 06:32、`t-784718` 06:44 均报「改动文件不存在或 mtime 早于开工时刻」）。**不阻断本卡验收；需在 RTM/任务卡登记改动归属**（记入 t-030788 的卡链修复或单列附带修复项）。
- 依据：`git diff`（ExecuteTask.ts hunk `:167-173` / `:260-278`）；`support.ts:124`；`advance-log.md`；`tasks/t-030788.md:56`。

---

## 3. 观察项（不阻断，不影响本卡契约）

- **O-1 卡面验收命令字面与设计口径不符**：`tasks/t-00bed8.md:15` 写「`grep -rn "executions.push(" src/application src/http` 无输出」；实测输出 2 行，均在唯一写点文件内（`token-usage.ts:113` 注释 + `:160` 写点）。architecture L109-112 要求的正是「写点只在助手内」，故按设计判为**通过**；卡面措辞宜改为「除助手外无输出」。
- **O-2 pm-capture-root 用 `snapshotProviderFor` 而非 backend L68 的 `() => captureSnapshot(...)`**：interfaces L102-104、architecture L167 与 `tasks/t-00bed8.md:19` 均写 `snapshotProviderFor`，实现取该统一入口；`windowKey` 非空时两种写法等价（`snapshotProviderFor` 仅在空串时多一层 `sourceSessionId` 回落，与 D-1 同口径）。**非偏离**。
- **O-3 自动链快照行为缺「留存」测试**：`tests/advance-chain.test.ts` 与 `tests/execute-task.test.ts` 对 `tokenUsage`/`snapshot` **零断言**（grep 无命中），本卡快照语义目前只有联调探针（已删）与 `evidence/t-00bed8-integrate.md` 记录；设计指定的 `tests/rollup-snapshot.test.ts`（T-13/T-14）与 `tests/execution-token-guard.test.ts`（T-18）**尚不存在**（属 t8/t7）。FR-8 的唯一性纪律当前由人工 grep 保障，待 t7 落机械守卫。

---

## 4. 复跑证据（本次复核实测，2026-09-27）

    $ cd packages/web/dsh-pmboard
    $ npx vitest run tests/advance-chain.test.ts tests/execute-task.test.ts        # 卡面验收命令
     ✓ tests/advance-chain.test.ts (8 tests) / ✓ tests/execute-task.test.ts (11 tests)
     Test Files 2 passed (2) / Tests 19 passed (19)

    $ npx vitest run tests/ledger-v6-token.test.ts tests/token-usage.test.ts tests/token-transition-helper.test.ts tests/token-fallback.test.ts
     Test Files 4 passed (4) / Tests 25 passed (25)                                # 需求「验收标准（整体）」第 1 条

    $ npx vitest run tests/execution-snapshot-helpers.test.ts tests/token-usage.test.ts tests/ledger-v6-token.test.ts tests/rollup.test.ts tests/routes-rollup.test.ts
     Test Files 5 passed (5) / Tests 52 passed (52)                                # 写路径收敛回归

    $ npx vitest run tests/capture-hook.test.ts tests/rollup.test.ts
     Test Files 2 passed (2) / Tests 47 passed (47)                                # 接手推进装配可用

    $ grep -rn "executions.push(" src/application src/http
    src/application/internal/token-usage.ts:113  （注释）
    src/application/internal/token-usage.ts:160  （唯一写点 openExecution 内）

    $ grep -rnE "tokenUsage \?\?=|tokenUsage =" src/application src/http | grep -v internal/token-usage.ts
    src/application/query/QueryRequirementToken.ts:108   （仅读取 tokenUsage.totals）

    $ grep -rn "beginExecutionToken" src/
    src/application/internal/token-usage.ts:86   （定义）
    src/application/internal/token-usage.ts:159  （openExecution 内真实调用方，不再是死代码）

    $ git diff --stat -- src/application/use-cases/AdvanceChain.ts src/application/use-cases/ExecuteTask.ts src/wiring/pm-capture-root.ts src/index.ts src/application/internal/token-usage.ts
     token-usage.ts +132 / AdvanceChain.ts ~50 / ExecuteTask.ts ~88 / index.ts ~8 / pm-capture-root.ts ~6

    $ git diff -- src/application/use-cases/AdvanceChain.ts
     仅 5 处：import 5 个助手 · openParent 改 openExecution · finalizeParent 改 closeExecutions ·
             rollupStep 补 snapshot 提供者 · runSelection 下传 exec。无其他改动。

---

## 5. 结论

- **t5「自动链任务执行与接手推进改经执行助手并带快照」13 条设计落点（R1–R13）全部到位，无阻断性偏离、无需返工**：父卡开工/收尾、子卡开工/收尾（含 born-failed 不写 start 与失败带 error 闭合）、rollup 快照提供者、`safeWindowKey` 解析与 `'system'` 视为无会话、`snap=undefined` 不写 token 字段、接手推进带提供者、启动对账不传 snapshot、唯一性纪律、错误语义不变，逐条与 requirement FR-4/5/6 + architecture + backend + interfaces + 任务卡一致。
- **2 条偏离均在文档侧**：D-1（interfaces L103 与 architecture L164 自相矛盾，实现选 architecture，建议修 interfaces 文本）；D-2（`claimedAt` 取 workflow 开工时刻的修复未登记，归属待确认，建议补 RTM/任务卡）。两者都不改变本卡契约，不阻断父卡验收。
- **3 条观察项**：O-1 卡面验收措辞、O-2 提供者写法、O-3 自动链快照行为待 t7/t8 补留存测试。

复核人：实施子代理（t-784718）；时间：2026-09-27 14:47 (+08:00)
