---
req_id: REQ-260927121324-abde
title: 节点级 Token 统计写路径收口 · 架构设计
stage: design
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9
---

# 架构设计（REQ-260927121324-abde · 节点级 Token 统计写路径收口）

**目标（可证伪，一句话）**：让 dsh-pmboard 的三条 token 写路径——①需求状态迁移、②任务执行开工/完工、
③任务完成后的派生推进——全部经各自唯一收敛点按写时快照落账，缺失（`undefined`）与取不到
（`source='unavailable'`）在读路径一律计入 `degraded=true`；既有 token 单测由 3 red 转 0 red。

**可证伪判据**：`npx vitest run tests/ledger-v6-token.test.ts tests/token-usage.test.ts tests/token-transition-helper.test.ts tests/token-fallback.test.ts` → 0 failed；
且 `grep -rn "req.status = \\|r.status = " src/application src/http` 只剩收敛点一处；
且 `grep -rn "beginExecutionToken" src/` 出现真实调用方（不再是死代码）。

## TL;DR <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 -->

三句话：

1. **写路径收口**：需求迁移只走 `transitionRequirement`（补 5 处漏传/绕过），任务执行快照只走
   `token-usage.ts` 的执行助手（补 4 处从未接过快照的产生点），派生推进的 `snapshot` 提供者补齐。
2. **缺失如实上报**：读路径 `hasUnavailableSnapshot` 扩为「缺失或不可得」，让「压根没写」不再被显示成正常。
3. **机械防回归**：新增源码扫描单测，把「`executions.push` / `tokenUsage` 写点只准出现在助手内」锁死，
   并把四条验收命令接进回归清单。

不改台账 schemaVersion（保持 8）、不回填历史、不改 token 统计口径、不动端侧渲染。

## 设计总览：三条写路径 + 一条读路径 <!-- serves: FR-1, FR-4, FR-6, FR-7 -->

```
                    写时快照 captureSnapshot(deps, windowKey) → TokenSnapshot
                              │   (projection | unavailable；永不抛)
        ┌─────────────────────┼──────────────────────────────┐
        ▼                     ▼                              ▼
 ①需求状态迁移          ②任务执行                   ③派生推进(rollup)
 transitionRequirement   open/close/refreshExecution   RollupContext.snapshot?
 (application/internal/  (application/internal/        (application/internal/
  token-usage.ts:139)     token-usage.ts 新增)          rollup.ts:35)
        │                     │                              │
        ▼                     ▼                              ▼
 accumulateStageDelta   begin/endExecutionToken      transitionRequirement
 + recordStatus(带快照)  → execution.tokenUsage       (带/不带 snap，如实)
        │                     │                              │
        └──────────┬──────────┴──────────────┬───────────────┘
                   ▼                          ▼
           台账 RequirementRecord     台账 TaskRecord.executions
           .tokenUsage.byStage/totals  .tokenUsage.start/end/delta
                   │                          │
                   └────────────┬─────────────┘
                                ▼
                       读路径 QueryRequirementToken
                byStage / executions / totals / degraded（FR-7 扩判定）
```

三条写路径各自的**唯一收敛点**（结构性约束）：

| 路径 | 唯一收敛点 | 位置 | 本需求动作 |
|---|---|---|---|
| 需求迁移 | `transitionRequirement` | `application/internal/token-usage.ts:139` | 全部调用方补 `snap`；消除两处直接赋值 |
| 任务执行 | `openExecution/closeExecutions/refreshRunningExecution` | `application/internal/token-usage.ts`（新增） | 四处产生点改经它；`beginExecutionToken` 复活 |
| 派生推进 | `RollupContext.snapshot?` | `application/internal/rollup.ts:35` | 有会话上下文的调用点补 `snapshot` 提供者 |

> 上表是写路径的**收敛点归属**，不是任务拆分表（任务表 / DAG 属拆分阶段产物，本设计不含）。

## 根因 → 修点对照 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 -->

R1（任务执行漏快照，回归）：`MoveTask.ts` 重写后漏掉 `beginExecutionToken`，且另外三处执行记录产生点
从未接过快照。→ FR-4 / FR-5 / FR-8。

R2（需求迁移漏快照 + 两处绕过收敛点）：`confirm-settle.ts:278/304`、`requirements.ts:270` 未传 `snap`；
`requirements.ts:111` 与 `verdicts.ts:106` 直接 `req.status = to`；`HandleFailure.ts:87/109` 同样直接赋值；
`applyVerdicts` 已有 `snap` 形参但看板调用未传。→ FR-1 / FR-2 / FR-3。

R3（读路径漏报降级）：`hasUnavailableSnapshot` 只认 `source==='unavailable'`，对最常见形态
（事件压根没有 `tokenSnapshot`）判为正常。→ FR-7。

回归防线：本缺陷全部证据来自既有单测与台账，没有机械守卫就会再被静默引入。→ FR-9。

## 写路径收敛点 <!-- serves: FR-1, FR-8 -->

**收敛点 1 · 需求迁移**（已存在，本次补齐调用方）

```ts
// application/internal/token-usage.ts（已存在）
export function transitionRequirement(req: RequirementRecord, to: RequirementStatus, opts: TransitionOpts): void
// opts = { at, actor, reason?, snap?: TokenSnapshot, allowIllegalTransition? }
// 内部：assertReqTransition → accumulateStageDelta(req, from, snap) → 改 status/version/updatedAt
//       → recordStatus(req, to, at, actor, reason, snap)
```

**收敛点 2 · 任务执行快照**（本次新增于同一模块；与收敛点 1 对称）

```ts
// application/internal/token-usage.ts（新增导出）
export function openExecution(task: TaskRecord, spec: OpenExecutionSpec, snap?: TokenSnapshot): ExecutionRecord
export function closeExecutions(task: TaskRecord, opts: CloseExecutionsOpts, snap?: TokenSnapshot): number
export function refreshRunningExecution(task: TaskRecord, snap: TokenSnapshot, sessionId?: string): boolean
```

**收敛点 3 · 派生推进**（已存在，本次补齐 `snapshot` 提供者）

```ts
// application/internal/rollup.ts（已存在）
export interface RollupContext { now; commentId; snapshot?: (req: RequirementRecord) => TokenSnapshot | undefined }
```

**唯一性纪律**：`src/` 内对 `execution.tokenUsage` 的**写**（`??=` / 赋值）与对 `task.executions` 的
**增改**（`executions.push(`）只允许出现在 `application/internal/token-usage.ts`；
对 `req.status` 的写只允许出现在 `transitionRequirement` 内（`domain/legacy` 迁移路径除外）。
两条纪律都由 `tests/execution-token-guard.test.ts` + `tests/requirement-transition-guard.test.ts` 机械断言。

## 数据流（含失败分支） <!-- serves: FR-2, FR-5, FR-7 -->

**任务开工（agent / 看板 / 自动链父卡 / 自动链子卡）**

```
startsExecutionSegment(to=true) 且调用方持有会话上下文
  → snapshotForWindow(deps, windowKey) 或 ctx.deps.tokenSnapshot?.(sessionId)
  → openExecution(task, { id, sessionId?, trigger, at }, snap)
      ├─ snap 可得 → execution.tokenUsage.start = snap；delta 清空
      └─ 无会话上下文（snap=undefined）→ 只落执行记录，不写 start（读路径按缺失降级）
失败分支：`assertDoneEvidence` / 非法转移抛错 → repo.mutate 回滚 → 状态、执行记录、快照三者都不落（原子）
```

**任务完工 / 中途汇报**

```
!startsExecutionSegment(to) 或 reqboard_task_report
  → closeExecutions(task, { at, outcome }, snap) / refreshRunningExecution(task, snap, windowKey)
      ├─ start 与 end 同会话且均为 projection → delta = subBuckets(end, start)
      └─ 任一端缺失 / unavailable / 跨会话 → delta 缺省（禁止用 0 或单端累计冒充）
失败分支：ReportTask 未命中 running 执行 → 不写（返回汇报仍成功；token 是旁路证据，不阻断主流程）
```

**需求迁移**

```
transitionRequirement(req, to, { snap })
  ├─ snap 可得 → accumulateStageDelta(离开节点) → byStage[from] += (snap - entrySnapshotFor(from))
  │              并 recordStatus(to, ..., snap)（进入节点快照）
  └─ snap 缺失 → 不结算、事件不带快照（读路径 degraded=true）
```

**读路径判定（FR-7）**

```
degraded = req.tokenUsage === undefined
        || ∃ 状态事件 e：e.tokenSnapshot 缺失或 source !== 'projection'
        || ∃ 执行 e：运行中（endedAt 缺失）而 start 不可得；或已闭合而 start/end 任一不可得
```

## 逐条功能点实现要点 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 -->

- **FR-1**：`requirements.ts:111`、`verdicts.ts:106` 直接赋值改经 `transitionRequirement`；
  `HandleFailure.ts:87/109` 同改；`HandleFailure` 用 `req.sourceSessionId` 取快照（无则诚实不传）。
  验收 grep 只剩 `token-usage.ts:159` 一处。
- **FR-2**：`confirm-settle.ts:278` 与 `:304` 补 `snap: captureSnapshot(deps, d.windowKey)`；
  `requirements.ts:270`（看板确认即推进）补 `snap: ctx.deps.tokenSnapshot?.(windowKey)` 并给 actor 带 sessionId。
- **FR-3**：`verdicts.ts:170` 的 `applyVerdicts` 调用补第 8 个实参 `snap`；
  `handleVerifyDecision` 改经收敛点并带快照；取不到会话时 `snap=undefined`（该段显示「无快照」）。
- **FR-4**：四处执行产生点改用 `openExecution`；agent 用 `windowKey`、看板用 `body.sessionId`、
  自动链父卡/子卡用 `safeWindowKey(deps, exec)`（解析不到则退 `req.sourceSessionId`，再不行不写）。
- **FR-5**：四处收尾改用 `closeExecutions`；`ReportTask` 改用 `refreshRunningExecution`。
  delta 产出条件不变（同会话 + 两端 projection）。
- **FR-6**：`MoveTask.ts:127`、`tasks.ts:66/110/157`、`AdvanceChain.ts:205`、`pm-capture-root.ts:133`
  补 `snapshot`；`index.ts:166` 启动对账（无会话）**明确不传**，不伪造。
- **FR-7**：`QueryRequirementToken.hasUnavailableSnapshot` → `hasSnapshotGap`，按上文判定式；
  `degraded` 计算随之更新；形状与字段名不变（`RequirementTokenView.degraded` 仍是 boolean）。
- **FR-8**：新增执行助手 + 源码扫描守卫单测（tokenUsage 写点 / executions.push 只准在助手内）。
- **FR-9**：既有 token 单测全绿 + 新增守卫/回归用例；验收命令写进 `docs/architecture/project-manual.md` 或本需求验收材料。

## 四视角落点 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8 -->

- **架构视角**：三层收敛点（需求迁移 / 任务执行 / 派生推进）各一个唯一写入口；本文件即架构落点。
- **接口视角**：[interfaces.md](./interfaces.md) —— 助手函数签名、HTTP 入口、Agent 工具入口、错误码。
- **数据模型视角**：[data-model.md](./data-model.md) —— 字段契约、不变式、degraded 判定、兼容与回滚。
- **测试策略视角**：[test-cases.md](./test-cases.md) —— 覆盖矩阵、用例表（含实际文件）、失败形态与验收命令。
  后端逐文件改动见 [backend.md](./backend.md)；用户视角见 [use-cases.md](./use-cases.md)。

## 迁移与回滚 <!-- serves: FR-7, FR-8 -->

- **schema 无迁移**：`REQBOARD_SCHEMA_VERSION` 保持 `8`；不新增字段、不改字段语义。
- **历史数据不回填**：会话投影是累计计数器，历史差值不可考，回填即编造；旧需求继续显示「无快照 / 部分数据不可用」
  是**正确语义**（`degraded=true`）。
- **灰度**：无开关；host 侧改动集中在写路径，**发布即生效**（`agent-dh/scripts/restart-with-build.sh`）。
- **回滚**：还原代码即可；已写入的快照是既有可选字段，无需清理，旧代码可正常载入（读路径对未知字段宽容）。

## 不做什么（边界） <!-- serves: FR-1, FR-4, FR-6, FR-7 -->

1. 不回填历史、不改 schemaVersion、不新增字段。
2. 不改 token 统计口径（仍是同会话累计值差值近似归因）；跨需求共享会话的已知偏差保留。
3. 不动 DSH 侧 `SessionProbeAdapter.tokenTotals` 与端侧 Token tab 视觉/信息层级。
4. 不修 Dive armed 自动驱动机制本身；只保证写路径不漏账。
5. 设计文档不含任何任务表 / DAG / 拆分计划（归拆分阶段）。

## 风险与缓解 <!-- serves: FR-4, FR-5, FR-7 -->

| 风险 | 缓解 |
|---|---|
| 把「无快照」误写成 `0`（历史教训） | delta 只在两端 projection 同会话时产出；其余一律缺省；单测断言 `delta === undefined` |
| 自动链/启动对账无会话却伪造快照 | `safeWindowKey` 解析不到即返回 `undefined`，不写；单测断言「无会话路径不产生伪造快照」 |
| 新增路径再次漏写快照 | 源码扫描守卫单测：`executions.push(` / `tokenUsage` 写点只准在助手内 |
| degraded 判定过严导致页面噪声 | 只对**真实存在**的事件/执行判缺失，不对「没走过的节点」判缺失；既有 token-endpoint 用例断言全投影数据 `degraded=false` 必须保持 |
