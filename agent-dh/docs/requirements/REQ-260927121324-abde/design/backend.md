---
req_id: REQ-260927121324-abde
title: 节点级 Token 统计写路径收口 · 后端实施设计
stage: design
sides: backend
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9
---

# 后端实施设计（REQ-260927121324-abde · backend）

**端侧声明**：`sides: backend`。改动全部落在 `packages/web/dsh-pmboard/src` 的 host 侧
（application / http / wiring），客户端 `src/client` 不改（Token tab 已能如实渲染缺失与 degraded）。

## 后端改动清单 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 -->

| 模块 | 文件 | 动作 | 关联功能点 |
|---|---|---|---|
| token 写助手 | `src/application/internal/token-usage.ts` | 新增 4 个助手；执行快照唯一写入口 | FR-4, FR-5, FR-6, FR-8 |
| 需求迁移（弹框） | `src/application/internal/confirm-settle.ts` | 两分支补 `snap` | FR-2 |
| 需求迁移（失败处置） | `src/application/use-cases/HandleFailure.ts` | 两处直接赋值改经收敛点 | FR-1 |
| 需求迁移（看板） | `src/http/routers/requirements.ts` | `req/move` 改经收敛点；确认即推进补 `snap` | FR-1, FR-2 |
| 验收（看板） | `src/http/routers/verdicts.ts` | 直接赋值改经收敛点；`applyVerdicts` 补 `snap` | FR-1, FR-3 |
| 任务执行（agent） | `src/application/use-cases/MoveTask.ts` | 改用 `openExecution`/`closeExecutions`；rollup 带快照 | FR-4, FR-5, FR-6 |
| 任务执行（看板） | `src/http/routers/tasks.ts` | 同上；create/update 读可选 `sessionId` | FR-4, FR-5, FR-6 |
| 任务执行（自动链） | `src/application/use-cases/AdvanceChain.ts`、`ExecuteTask.ts` | 改用执行助手；rollup 带快照 | FR-4, FR-5, FR-6 |
| 中途汇报 | `src/application/use-cases/ReportTask.ts` | 改用 `refreshRunningExecution` | FR-5 |
| 派生推进装配 | `src/wiring/pm-capture-root.ts` | 接手推进传快照提供者 | FR-6 |
| 读路径 | `src/application/query/QueryRequirementToken.ts` | `degraded` 判定加严 | FR-7 |
| 守卫单测 | `tests/execution-token-guard.test.ts`、`tests/requirement-transition-guard.test.ts` | 新增 | FR-8, FR-9 |

## 逐文件改动（需求迁移） <!-- serves: FR-1, FR-2, FR-3 -->

1. `confirm-settle.ts:278` 与 `:304`：给 `transitionRequirement` 的 opts 补
   `snap: captureSnapshot(deps, d.windowKey)`（与同文件 `:180` 的通用推进一致）。
2. `requirements.ts`：
   - `handleReqMove` 删除 `req.status/version/updatedAt/updatedBy/recordStatus` 五连写，改调用
     `transitionRequirement(r, to, { at: now(), actor: { kind: actor, ...(sessionId?{sessionId}:{}) }, reason, snap })`；
   - `sessionId` 取值：请求体可选字段 → `r.sourceSessionId`；
   - 确认即推进入口（`:270`）：补 `snap: ctx.deps.tokenSnapshot?.(windowKey)`（`windowKey = confirmed.sourceSessionId`），
     并给 actor 带 `sessionId: windowKey`。
3. `verdicts.ts`：
   - `handleVerifyDecision` 的 `r.status=to; version++; updatedAt; updatedBy; recordStatus(...)` 五连写
     替换为 `transitionRequirement(r, to, { at: now(), actor: { kind:'human', ...(sessionId?{sessionId}:{}) }, reason, snap })`；
   - `handleVerdicts` 的 `applyVerdicts(...)` 补第 8 实参 `ctx.deps.tokenSnapshot?.(r.sourceSessionId)`。
4. `HandleFailure.ts:87` 与 `:109`：改经 `transitionRequirement`；`snap` 用
   `snapshotForWindow(deps, req.sourceSessionId)`（拿不到则 undefined，诚实不传）。

## 逐文件改动（任务执行） <!-- serves: FR-4, FR-5, FR-8 -->

1. `token-usage.ts` 新增 `openExecution` / `closeExecutions` / `refreshRunningExecution`，
   内部调用既有 `beginExecutionToken` / `endExecutionToken`（这两个仍是 token 字段唯一写点）。
2. `MoveTask.ts:108` 的 `task.executions.push(...)` → `openExecution(task, spec, snapshotForWindow(deps, windowKey))`；
   `:120-123` 的关闭循环 → `closeExecutions(task, { at, outcome }, snapshotForWindow(deps, windowKey))`。
3. `tasks.ts:90` 同样替换；`sessionId` 缺省时不写 `snap`。
4. `AdvanceChain.ts:141` / `:169-171` 与 `ExecuteTask.ts:222` / `:255-258`、`:269-271` 同样替换；
   自动链的会话码由 `safeWindowKey(deps, exec)` 解析，解析不到则不写快照。
5. `ReportTask.ts:133-138` 循环 → `refreshRunningExecution(tk, snap, windowKey)`。

## 自动链与无会话路径 <!-- serves: FR-4, FR-6 -->

- `AdvanceChain.driveChain` 持有 `exec`；把窗口码沿 `runSelection → openParent/rollupStep` 下传，
  或在各步骤内 `safeWindowKey(deps, exec)` 现取现用（推荐后者，改动面小）。
- `ExecuteTask` 的 `input.windowKey` 在自动链路径为 `'system'`；`'system'` 不当作真实会话，
  改从 `input.exec` 解析真实窗口码；解析不到 → `snap=undefined`。
- `index.ts:166` 的启动对账 `applyTaskRollup(ledger, ctx)` 与 `pm-capture-root` 中无窗口码的路径：
  **明确不传** `snapshot`，保证「无会话不伪造」。
- `pm-capture-root.ts:133` 的 `onBoundWindowActivity(windowKey)` 有窗口码，传
  `snapshot: () => captureSnapshot(deps.useCaseDeps(), windowKey)`。

## 读路径降级实现 <!-- serves: FR-7 -->

`QueryRequirementToken.ts`：把 `hasUnavailableSnapshot` 替换为 `hasSnapshotGap`（判定式见
[data-model.md](./data-model.md#读路径判定degradedfr-7-唯一变更点)），`assembleRequirementToken` 内
`degraded: usage === undefined || hasSnapshotGap(req, ledger)`。**不改** `byStage`/`executions`/`totals` 装配逻辑
（既有兜底口径保持：节点无快照时用其执行差值合计）。

## 结构性守卫 <!-- serves: FR-8, FR-9 -->

`tests/execution-token-guard.test.ts`（新增）：读 `src/**/*.ts`（排除 `token-usage.ts`），断言
- 不含 `executions.push(`；
- 不含 `tokenUsage ??=` / `.tokenUsage = `（赋值，读引用不算）。

`tests/requirement-transition-guard.test.ts`（新增）：断言 `src/application` 与 `src/http` 内
不含 `req.status = ` / `r.status = `（`domain/legacy/LegacyStatus.ts` 迁移路径不在扫描范围）。

## 发布与验证 <!-- serves: FR-9 -->

- **发布**：host 侧改动必须发版——`bash agent-dh/scripts/restart-with-build.sh`（含 relink + 构建 + 重启）。
- **验证**：先跑单测命令；再在真实窗口开工一张卡，查 `GET /dashboard/api/reqboard/requirements/:id/token`
  的 `implementing.executions` 非空、`degraded` 对缺口需求为 `true`。
- **验收证据**：线上接口返回摘要 + 单测输出摘要（不只贴单测，见需求「验收标准（整体）」）。
