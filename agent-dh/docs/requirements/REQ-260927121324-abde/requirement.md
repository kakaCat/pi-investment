---
req_id: REQ-260927121324-abde
title: 修复 pmboard 任务执行 token 快照丢失（beginExecutionToken 无调用方）
category: feature
status: brainstorming
sides: backend
---

# REQ-260927121324-abde: 节点级 Token 统计写路径整体收口

> 台账立项名（REQ 名）：修复 pmboard 任务执行 token 快照丢失（beginExecutionToken 无调用方）

## 本版修订摘要（v2 · 2026-09-27 12:27，按用户确认门意见扩写）

| 项 | v1（立项稿） | v2（本版） |
|---|---|---|
| 范围 | 只修任务执行 start 快照丢失，两条路径 | 节点级 token 统计**全部写路径**收口 |
| 需求迁移路径 | 只提「批准计划→实施 两处 + 看板确认推进」 | 全量 12 条路径盘点，含看板「移动」「验收通过/退回」两条**绕过收敛点**的直接赋值 |
| 任务执行产生点 | 只提 agent 路径（看板一句带过） | 四处产生点：agent 流转 / 看板流转 / 自动链父卡开工 / 自动链子卡执行 |
| 派生推进 rollup | 未提 | FR-6：能取快照就结算，取不到诚实不传 |
| 结构性守卫 | 无 | FR-8：执行快照收敛到唯一助手，漏写即红灯 |
| FR 条数 | 6 | 9（G2 行首格式，RTM 已解析 9/9） |
| 档位 | 轻档 | **重档**（L3 单向升级，不可逆） |

> **范围说明（2026-09-27 用户在确认门裁定）**：立项名保留，但本轮不再只修「任务执行 start 快照丢失」这一条回归，
> 而是把**节点级 token 统计的全部写路径**一次收口——需求状态迁移、任务执行开工/完工、派生推进三条写路径
> 都按写时快照落账，缺失一律如实降级。

用户报「pm 插件 token 统计出现问题」。核对台账与接口后确认：**不是读数错，是写数缺链**——
任务执行（ExecutionRecord）的 `tokenUsage.start` 在 2026-09-26 之后再也没有写入过，
于是 `endExecutionToken` 因缺 start 永远算不出 delta，任务级消耗全部退化成「无快照」；
与此同时还有若干需求迁移路径漏传快照、两处看板路径干脆绕过迁移收敛点，以及读路径把「压根没写」误报为正常。

## 背景与现象（可复核）

1. `GET /dashboard/api/reqboard/requirements/REQ-260927100007-b8ba/token` →
   `implementing` 行既无 `buckets`（无快照），`executions` 也是空数组；「🔨 实施」节点在 Token tab 上完全空白。
2. 同一响应的 `degraded: false`——缺口存在却不报警（扫描见根因 R3）。
3. 单测红灯：`cd packages/web/dsh-pmboard && npx vitest run tests/ledger-v6-token.test.ts tests/token-usage.test.ts`
   → **3 failed | 16 passed**（失败全部落在「写时快照：任务执行」三例）。

台账实证（`.dsh-data/dsh-reqboard.json`，2026-09-27 复核；`execution.startedAt` 按 UTC 日聚合）：

| 日期（UTC） | 有 start（manual） | 无 start（manual） | 无 start（trigger=auto） |
|---|---|---|---|
| 09-22 | 20 | 0 | 4 |
| 09-23 | 21 | 0 | 2 |
| 09-24 | 8 | 0 | 92 |
| 09-25 | 61 | 0 | 0 |
| 09-26 | 0 | 24 | 3 |
| 09-27 | 0 | 30 | 0 |

这是**两条独立的缺口**，本需求都覆盖：

- **手动路径（09-26 起归零）**：最后一条带 start 的手动执行是 `2026-09-25T17:07:11Z`（t-6734bf），
  09-26 起为 0 —— 即 `MoveTask.ts` 重写时丢掉 `beginExecutionToken` 的回归（R1）。
- **自动路径（09-22 起长期无快照）**：`trigger='auto'` 的执行由自动链/看板自动流转产生，
  **从未接过快照**（对应 R1 表里 `AdvanceChain.ts:141` / `ExecuteTask.ts:222` 两行）——
  所以 09-24 的 92 条不是同一次回归，而是本需求要一并收口的"另一半"。

## 根因（代码级核实）

### R1 任务执行写路径漏快照（回归）

- 提交 `80e79118` 删除了旧 `MoveTask.ts`（211 行），它是当时**唯一**调用 `beginExecutionToken` 的地方：
  `git grep -n beginExecutionToken 80e79118^ -- packages/web/dsh-pmboard/src` → `MoveTask.ts:98`。
- 提交 `daa4169e` 为补回 agent 侧流转工具重写了 `MoveTask.ts`，只保留
  「push 执行记录 / 收尾改 outcome」的骨架，漏掉 `captureSnapshot` + `beginExecutionToken` / `endExecutionToken`。
- 现状：`src` 内 `beginExecutionToken` **只有定义、没有调用方**（死代码）。
- 同形缺口还有三处执行记录产生点（同样是「push 执行记录但不记快照」）：

  | 执行记录产生点 | 位置 | start | end |
  |---|---|---|---|
  | agent 任务流转 | `src/application/use-cases/MoveTask.ts:108` | ❌ | ❌（`:115-123` 只改 outcome） |
  | 看板任务流转 | `src/http/routers/tasks.ts:90` | ❌ | ❌（`:97-104`） |
  | 自动链父卡开工 | `src/application/use-cases/AdvanceChain.ts:141` | ❌ | ❌（`:169-171`） |
  | 自动链子卡执行 | `src/application/use-cases/ExecuteTask.ts:222` | ❌ | ❌（`:255-258`） |

- `reqboard_task_report`（`ReportTask.ts:123/136`）**是**写 end 的，但因 start 恒缺，`endExecutionToken`
  算不出 delta → 任务级消耗全部退化成「无快照」。

### R2 需求状态迁移：漏快照 + 两处绕过收敛点

REQ-b545fe 已把需求迁移收敛到 `transitionRequirement`（`src/application/internal/token-usage.ts:139`），
但**收敛点的 `snap` 是可选参数**，于是仍有调用方不传；更有两处**根本没走收敛点**：

| # | 路径 | 位置 | 现状 |
|---|---|---|---|
| 1 | agent `reqboard_move` | `MoveRequirement.ts:54` | ✅ 传 snap |
| 2 | agent 确认产物即推进 | `ConfirmArtifact.ts:198` | ✅ |
| 3 | agent 立项 | `CaptureRequirement.ts:68` | ✅ |
| 4 | 弹框确认通用推进 | `confirm-settle.ts:176` | ✅ |
| 5 | 弹框批准计划 → 实施（正常分支） | `confirm-settle.ts:278` | ❌ 未传 snap |
| 6 | 弹框批准计划 → 实施（收尾兜底分支） | `confirm-settle.ts:304` | ❌ 未传 snap |
| 7 | 看板一键确认产物即推进 | `http/routers/requirements.ts:270` | ❌ 未传 snap |
| 8 | 看板「移动」按钮 | `http/routers/requirements.ts:111-115` | ❌ **直接 `req.status = to`**，绕过收敛点 |
| 9 | 看板「验收通过 / 退回返工」 | `http/routers/verdicts.ts:106-112` | ❌ **直接 `r.status = to`**，绕过收敛点 |
| 10 | 看板逐项裁决（含 failed 自动回退） | `http/routers/verdicts.ts:170-172` | ❌ `applyVerdicts` 未传 snap |
| 11 | 验收归档 / 弹框裁决打回 | `AcceptSheet.ts:104` / `:213` | ✅ |
| 12 | 派生推进 rollup | `rollup.ts:58`（`ctx.snapshot` 可选） | 半：`SubmitVerification.ts:216`、`plan-landing.ts:141`、`tasks.ts:110` 传；`MoveTask.ts:127`、`tasks.ts:66/157`、`AdvanceChain.ts:205`、`pm-capture-root.ts:133` 不传 |

后果是「离开节点结算」与「进入节点快照」双缺，`byStage` 少掉节点 key；**人从看板点按钮推进的需求尤其明显**。
典型：批准计划 → 实施的两条分支都不带快照，于是 `decomposing` 与 `implementing` 两个节点一起消失。

### R3 读路径漏报降级

`QueryRequirementToken.hasUnavailableSnapshot`（`src/application/query/QueryRequirementToken.ts:33-46`）
只认 `source === 'unavailable'`；对「事件压根没有 `tokenSnapshot`（undefined）」判为正常 →
`degraded` 误报 `false`。而后者恰恰是**最常见的缺口形态**（写路径漏写，而不是取不到）。

## 边界

### 做什么

1. **需求迁移写路径收口（FR-1/FR-2/FR-3）**——所有需求状态迁移（含看板「移动」`POST /req/move` 与
   「验收通过/退回」`POST /req/verify/*` 两条直接赋值路径）统一经 `transitionRequirement`，
   凡有会话上下文必须带写时快照；批准计划 → 实施的两个分支与看板确认推进补齐快照。
2. **任务执行写路径收口（FR-4/FR-5）**——四处执行记录产生点（agent 任务流转 / 看板任务流转 /
   自动链父卡开工 / 自动链子卡执行）开工写 `start`、完工写 `end`；同会话且两端 projection 才产 `delta`。
3. **派生推进带快照（FR-6）**——能拿到会话上下文的 rollup 调用点都传快照提供者；
   拿不到的（启动对账、纯 `system` 无人会话路径）诚实地不传，不伪造。
4. **读路径如实降级（FR-7）**——「事件无快照（undefined）」与「快照 unavailable」同等计入 `degraded`。
5. **结构性守卫 + 回归（FR-8/FR-9）**——执行快照只有一个写入口；单测覆盖 agent 与看板两个入口，漏写即红灯。

### 不做什么

1. **不回填历史数据、不改台账 schemaVersion（保持 8）**——会话投影是累计计数器，历史差值不可考，
   回填只能是编造；历史需求继续显示「无快照 / 部分数据不可用」是**正确语义**。
2. **不改 token 统计口径**——仍是「同会话累计值差值」的近似归因，跨需求共享会话的已知偏差保留；
   不做按请求/按工具的精确计费口径（那是另一个需求）。
3. **不动 DSH 侧读路径**——`SessionProbeAdapter.tokenTotals`（tokenUsage 投影解析）已验证可用，本次不改；
   也不在本需求内升级 DSH 版本。
4. **不改 Token tab 的视觉与信息层级**——客户端已能如实渲染「无快照」与 `degraded` 提示，本次只补上游数据
   （端侧声明：backend）。
5. **不修 Dive armed 自动驱动机制本身**——「需求从立项到归档全自动推进」不在本需求内；本次只保证写路径不漏账。

### 边界理由

- 第 1–3 条是同一根因的三种形态（写路径各写各的、漏一个就静默），必须一起修：
  只修 agent 路径，看板路径与自动链仍会留下同形缺口，第四次重演只是时间问题。
- 第 4 条决定用户**能不能看见**缺口：数据修好了但缺失仍显示「一切正常」，等于没修。
- 第 5 条是防止再次静默回归的唯一机械防线——本缺陷的全部证据都来自既有单测与台账，
  没有测试就只会再被静默引入一次。

## 产品定义

### 一句话目标

让 PM 看板的节点级 Token 统计**要么给出可信的数字，要么明确说"这段不可算"**——
不再出现「节点空白、任务明细为空、总量少算，却显示一切正常」。

### 核心价值

1. **成本可归因**：需求各流程节点与其任务明细的消耗重新可见，需求级总量不再系统性少算。
2. **缺失可识别**：快照缺失与「确实没花」严格区分，页面以「无快照 / 部分数据不可用」如实呈现。
3. **写路径有守卫**：所有写入口收敛到少数几个收敛点，任何新增路径漏写快照都会被单测当场拦下。

### 与现状的区别

现状：`beginExecutionToken` 是死代码，任务执行只有运行区间（甘特图能用）、没有消耗；
看板「移动 / 验收」两条路径绕过迁移收敛点；`degraded` 对「压根没写快照」这一最常见缺口误报为正常。
修复后：三条写路径（需求迁移 / 任务执行 / 派生推进）都按写时快照落账，缺失一律降级上报，
既有单测从红转绿并锁死行为。

## 用户与角色

| 角色 | 谁 | 在本需求里做什么 |
|---|---|---|
| 看板使用者（人） | 打开需求详情「🪙 Token」tab 的人 | 看到各节点与任务明细有数；真有缺失时看到「无快照 / 部分数据不可用」，而不是空白却显示正常 |
| 窗口 agent | 运行 `reqboard_task_move` / `reqboard_task_report` / `reqboard_move` 的会话窗口 | 推进任务/需求时自动写入写时快照，无需额外动作 |
| 看板操作者（人） | 在看板上点任务状态、移动节点、确认产物、验收通过/退回的人 | 从看板走的每条路径同样把快照落账 |
| 维护者 | 改 dsh-pmboard 的开发者 | 新增写路径必须过统一收敛点与快照助手，漏写会被单测拦下 |

## 功能点

**FR-1: 需求状态迁移统一经收敛点并带写时快照**

全部需求状态迁移必须经 `transitionRequirement`，禁止用例/路由直接给 `req.status` 赋值；
调用方有会话上下文时必须传 `snap`（离开节点结算 + 新事件带快照）。
验收：`grep -rn "req.status = \|r.status = " packages/web/dsh-pmboard/src/application packages/web/dsh-pmboard/src/http`
只剩收敛点内部一处；迁移后新事件的 `tokenSnapshot.source === 'projection'`，离开节点累加进 `byStage`。

**FR-2: 批准计划 → 实施与看板确认推进不丢快照（离开 + 进入双端）**

`confirm-settle.ts` 两个分支（`:278`/`:304`）与 `http/routers/requirements.ts:270` 的确认即推进都必须带快照，
使「拆分」节点的离开结算与「实施」节点的进入快照同时具备。
验收：新走一条 拆分→实施 的需求，其 `/token` 响应 `byStage` 同时含 `decomposing` 与 `implementing`，
且 `statusHistory` 中 `implementing` 事件的 `tokenSnapshot.source === 'projection'`
（对照现状 REQ-260927100007-b8ba 的 implementing 事件无快照）。

**FR-3: 看板验收/裁决路径同源带快照**

看板 `POST /req/verify/pass|rework` 与 `POST /req/verdicts`（含 failed 自动回退）改经收敛点迁移并带快照，
不再直接赋值；取不到会话上下文时诚实不传（该段显示「无快照」）。
验收：看板退回返工后 `accepting` 节点有值或如实标「无快照」，状态事件与 `tokenSnapshot` 一致；
`npx vitest run tests/verdicts-and-rework.test.ts tests/accept-verdicts-snapshot.test.ts` 通过。

**FR-4: 任务开工写 start 快照（四处执行记录产生点同源）**

`MoveTask.ts`（agent）、`http/routers/tasks.ts`（看板）、`AdvanceChain.ts`（自动链父卡开工）、
`ExecuteTask.ts`（自动链子卡执行）在 push 执行记录的同一步写入 `tokenUsage.start`（执行会话累计四桶投影）。
验收：`npx vitest run tests/ledger-v6-token.test.ts` 的「开工写 start」用例通过
（`executions[0].tokenUsage.start.totals` 等于当次快照）；真实会话开工一张卡后查台账，
该执行 `tokenUsage.start.source === 'projection'`；`git grep -n beginExecutionToken packages/web/dsh-pmboard/src`
能看到调用方（不再是死代码）。

**FR-5: 任务完工与中途汇报写 end 与 delta**

任务离开执行段（agent 流转 / 看板流转 / 自动链收尾 / 子卡完成）或中途 `reqboard_task_report` 刷新时写 `end`；
**仅当 start 与 end 同会话且均为 projection** 时产出 `delta`，否则 delta 缺省（显示「无快照」而非 0）。
验收：单测「完工写 end 与 delta」通过（snap 2 → snap 5 得 delta=B(3)）；「快照不可得」用例通过
（start/end 标 unavailable，delta 缺省）；对同一张卡分别用看板按钮与 `reqboard_task_move` 走一遍
in_progress → done，两次都能在 `/token` 的 `executions` 里看到该卡的非空 delta（或如实的无快照标记）。

**FR-6: 派生推进（rollup）能取快照就结算，取不到诚实不传**

`applyTaskRollup` / `applyPickupAdvance` 的调用点凡持会话上下文（`MoveTask`、看板任务建卡/改卡、
`AdvanceChain`、`pm-capture-root` 接管推进）都传 `snapshot` 提供者；启动对账等无会话路径不传。
验收：由任务完成触发的 `implementing → accepting` 派生推进，`implementing` 节点在 `byStage` 中有值；
`npx vitest run tests/rollup-snapshot.test.ts` 通过；无会话的启动对账路径不产生伪造快照（该节点保持「无快照」）。

**FR-7: 快照缺失如实降级**

状态事件完全没有 `tokenSnapshot`（undefined）与写了但取不到（`source === 'unavailable'`）一样，
都要让 Token 视图 `degraded === true`；任务执行缺 `start`/`end` 同理。
验收：`GET /dashboard/api/reqboard/requirements/REQ-260927100007-b8ba/token` 的 `degraded` 由当前的 `false` 变为 `true`；
新增单测断言「事件缺 tokenSnapshot → degraded true」「执行记录缺 start/end → degraded true」。

**FR-8: 执行快照写路径收敛到唯一助手（结构性守卫）**

任务执行的 `start` / `end` / `delta` 只由统一助手写入（与需求侧 `transitionRequirement` 对称），
任何新增/改动的执行记录产生点都必须经它；绕过即单测红灯。
验收：`grep -rn "tokenUsage" packages/web/dsh-pmboard/src` 的写点只出现在助手内；
把任一调用点的快照写入注释掉，token 单测立即失败（人工验证后可还原）。

**FR-9: 回归守护**

修复后既有 token 单测全绿，并补一条覆盖「写路径漏快照即红灯」的断言，防止同类回归再次静默。
验收：`cd packages/web/dsh-pmboard && npx vitest run tests/ledger-v6-token.test.ts tests/token-usage.test.ts tests/token-transition-helper.test.ts tests/token-fallback.test.ts`
→ 0 failed。

## 数据契约

**不新增字段、不改版本**（`REQBOARD_SCHEMA_VERSION` 保持 `8`）；本需求只改**谁写、写不写**。

| 字段 | 类型 / 取值 | 必填性 | 语义 |
|---|---|---|---|
| `StatusEvent.tokenSnapshot` | `{ sessionId?, at, totals, source: 'projection' \| 'unavailable' }` | 可选 | 进入该节点的写时快照；缺省 = 当时未取到 → 「无快照」，禁止补 0 |
| `ExecutionRecord.tokenUsage.start` / `.end` | 同上 | 可选 | 执行开工 / 完工两次快照 |
| `ExecutionRecord.tokenUsage.delta` | `TokenBuckets` | 可选 | 仅两端均为 projection 且同会话时产出；不可算即缺省 |
| `RequirementRecord.tokenUsage.byStage` | `Partial<Record<StageKey, TokenBuckets>>` | 可选 | 离开节点结算的增量聚合 |
| `RequirementRecord.tokenUsage.totals` | `TokenBuckets` | 可选 | 恒等于 `Σ byStage`（写路径单点重算） |

不变式（不得破坏）：缺失 ≠ 0（`undefined` 表示「不知道」，`0` 表示「确实没花」）；
delta 只在两端 projection + 同会话时产出；`totals = Σ byStage`，读路径另有「节点无快照时用其执行差值兜底」的既有口径。

读路径补充：`RequirementTokenStageRow.buckets` 缺省 = 该节点无快照；
`RequirementTokenView.degraded` = 存在不可得**或缺失**快照。

## 接口（对外入口）

| 入口 | 谁调用 | 输入 | 输出 / 错误语义 |
|---|---|---|---|
| `reqboard_task_move`（agent 工具） | 会话窗口 | `task_id` / `to` / `reason` | 写 start/end；错误码不变（`REQBOARD_HUMAN_GATE` 等） |
| `reqboard_task_report`（agent 工具） | 会话窗口 | `task_id` / `summary` / `completed` / `files_changed` / `next_step` | 刷新 running 执行的 end/delta |
| `reqboard_move`（agent 工具） | 会话窗口 | `requirement_id` / `to` / `reason` | 迁移带快照；五道人工门仍由收敛点拦 |
| `POST /dashboard/api/reqboard/task/move` | 看板 | `{ id, to, actor?, sessionId?, reason? }` | 带 sessionId 时同源写 start/end |
| `POST /dashboard/api/reqboard/req/move` | 看板 | `{ id, to, actor?, reason? }` | 改走收敛点 + 快照 |
| `POST /dashboard/api/reqboard/req/artifact/confirm` | 看板 | `{ id, kind }` | 确认即推进时带快照 |
| `POST /dashboard/api/reqboard/req/verify/pass\|rework` | 看板 | `{ id, note?, confirm_override? }` | 改走收敛点 + 快照 |
| `POST /dashboard/api/reqboard/req/verdicts` | 看板 | `{ id, version, verdicts[] }` | 逐项裁决同源带快照 |
| `GET /dashboard/api/reqboard/requirements/:id/token` | 看板 / 会话 | — | `RequirementTokenView`（byStage / totals / degraded），形状不变 |

## 迁移与兼容

- **无 schema 迁移、无历史回填**：旧台账（v5~v8）原样可载入；修复只影响**修复之后**发生的迁移与执行。
- **回滚**：改动集中在 host 侧写路径与一处读路径判定；回滚 = 还原代码，已写入的快照是既有字段，无需清理。
- **兼容**：缺省字段语义不变（`undefined` = 无快照），客户端无需改动、无需同步发版。
- **发布**：host 半改动必须发版（`scripts/restart-with-build.sh`）；验收证据取线上接口返回，不只贴单测输出。

## 验收标准（整体）

1. `cd packages/web/dsh-pmboard && npx vitest run tests/ledger-v6-token.test.ts tests/token-usage.test.ts tests/token-transition-helper.test.ts tests/token-fallback.test.ts` → 0 failed。
2. 在真实窗口里开工一张任务卡 → `/requirements/:id/token` 的 implementing 下钻出现该卡且有非空 delta。
3. 走完一条 拆分 → 实施 的需求：`byStage` 同时含 `decomposing` 与 `implementing`。
4. 对一个确实缺快照的历史需求（如 REQ-260927100007-b8ba）打开 Token tab：节点行显示「无快照」，
   顶部出现「部分节点/执行无快照」提示（`degraded=true`），总量与明细不再自相矛盾。
5. 看板路径单独复核：从看板移动任务 / 退回返工一次，对应节点与执行行有数或如实「无快照」。

## 依赖与约束

- 依赖：DSH `tokenUsage` 会话投影 + `SessionProbeAdapter.tokenTotals`（现状可用，强依赖）。
- 约束：「缺失 ≠ 0」的语义、同会话才相减的口径、`transitionRequirement` / `transitionTask` 作为收敛点的纪律都不得破坏。
- 约束：不回填历史数据，不改台账 schemaVersion（保持 8）。

## 档位与升级记录

- 本节点路由为**轻档**（初始判断：一条回归 + 两处漏传，改动面小、无新决策点）。
- 用户 2026-09-27 在确认门裁定「把节点级 token 统计整体纳入」，范围扩写为
  **三条写路径 + 读路径降级 + 结构性守卫**，并出现 ≥2 个新决策点
  （执行快照收敛点的形状；自动链/启动对账等无会话路径的降级边界）。
- 按 L3「出现第二个未定决策即停手并升级」，本需求**由轻档单向升级为重档**，
  后续按重档交付（完整设计文档 + 拆分计划 + 验收材料）。升级不可逆。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t2 |
| FR-2 | ✅ 已接收 | t2 |
| FR-3 | ✅ 已接收 | t2 |
| FR-4 | ✅ 已接收 | t1、t3、t4、t5 |
| FR-5 | ✅ 已接收 | t1、t3、t4、t5、t8 |
| FR-6 | ✅ 已接收 | t1、t3、t4、t5 |
| FR-7 | ✅ 已接收 | t8、t6、t9 |
| FR-8 | ✅ 已接收 | t1、t7 |
| FR-9 | ✅ 已接收 | t8、t10 |

> 无未接收条款（9 条全部有落点）。

<!-- reqboard:marks:end -->
