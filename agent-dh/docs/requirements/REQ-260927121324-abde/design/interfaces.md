---
req_id: REQ-260927121324-abde
title: 节点级 Token 统计写路径收口 · 接口设计
stage: design
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8
---

# 接口设计（REQ-260927121324-abde）

**结论（可证伪，一句话）**：本次只**新增 4 个内部助手函数**、给 2 个 HTTP 入口加可选 `sessionId` 入参、
给 3 处既有调用点补 `snap` 实参；对外 HTTP 响应形状、Agent 工具入参、错误码一律不变。

## 写路径助手（内部接口） <!-- serves: FR-1, FR-4, FR-5, FR-8 -->

全部位于 `src/application/internal/token-usage.ts`（**唯一 token 写模块**）。

```ts
/** 取一次快照；端口抛错也不阻断主流程（已存在）。 */
export function captureSnapshot(deps: UseCaseDeps, windowKey: string): TokenSnapshot

/** 解析窗口码 → 快照；窗口码缺失/空串 → undefined（诚实不传，不伪造）。新增。 */
export function snapshotForWindow(deps: UseCaseDeps, windowKey: string | undefined): TokenSnapshot | undefined

/** 从 exec 解析执行会话窗口码；解析不到（无 exec / 端口抛错）→ undefined。新增。 */
export function safeWindowKey(deps: UseCaseDeps, exec: unknown): string | undefined

/** 派生推进快照提供者（FR-6）：优先显式窗口码，退回 req.sourceSessionId；都无 → undefined。新增。 */
export function snapshotProviderFor(
  deps: UseCaseDeps,
  windowKey?: string,
): (req: RequirementRecord) => TokenSnapshot | undefined
```

- **参数**：`deps` 用例依赖；`windowKey` 执行会话码（可缺省）；`exec` 工具/链调用方句柄（可缺省）。
- **返回**：`TokenSnapshot`（`source` 为 `projection` 或 `unavailable`）或 `undefined`。
- **错误语义**：**永不抛**。会话不可得 → `unavailable`；连会话码都没有 → `undefined`。
  二者都表示「不可算」，区别在于是不是「试过了但拿不到」。

## 需求迁移收敛点 <!-- serves: FR-1, FR-2, FR-3, FR-6 -->

```ts
// 已存在，签名不变
export interface TransitionOpts {
  at: number
  actor: ActorRef              // { kind: 'agent'|'human'|'system', sessionId? }
  reason?: string
  snap?: TokenSnapshot         // 有会话上下文必须传；无 → 不结算不带快照
  allowIllegalTransition?: boolean  // 仅迁移/回填可用
}
export function transitionRequirement(req: RequirementRecord, to: RequirementStatus, opts: TransitionOpts): void
```

**调用契约（本需求收紧）**：

| 调用方 | 位置 | 现状 → 目标 |
|---|---|---|
| agent `reqboard_move` | `MoveRequirement.ts:54` | 已传 snap（不动） |
| 弹框确认通用推进 | `confirm-settle.ts:176` | 已传 snap（不动） |
| 弹框批准计划 → 实施（正常） | `confirm-settle.ts:278` | ❌ 未传 → 补 `captureSnapshot(deps, d.windowKey)` |
| 弹框批准计划 → 实施（兜底） | `confirm-settle.ts:304` | ❌ 未传 → 同上 |
| 看板确认即推进 | `requirements.ts:270` | ❌ 未传 → 补 `ctx.deps.tokenSnapshot?.(windowKey)`，actor 带 sessionId |
| 看板「移动」 | `requirements.ts:111` | ❌ 直接赋值 → 改经收敛点 + 快照 |
| 看板「验收通过/退回」 | `verdicts.ts:106` | ❌ 直接赋值 → 改经收敛点 + 快照 |
| 看板逐项裁决（含 failed 回退） | `verdicts.ts:170` | 已有形参未传 → 补第 8 实参 `snap` |
| 失败处置退回上游/取消 | `HandleFailure.ts:87/109` | ❌ 直接赋值 → 改经收敛点 + `req.sourceSessionId` 快照 |
| 派生推进 rollup | `rollup.ts:58` | 半（调用点未全传）→ FR-6 补齐提供者 |

## 执行快照助手 <!-- serves: FR-4, FR-5, FR-8 -->

```ts
/** 开工：push 一条 running 执行记录 + 写 start 快照。**唯一入口**，调用方不得自行 executions.push。 */
export interface OpenExecutionSpec {
  id: string                        // deps.ids.execution() / newExecutionId()
  sessionId?: string
  trigger: 'manual' | 'auto'
  at: number
  outcome?: 'running' | 'failed'    // 缺省 running；born-failed 不写 start
  error?: string
}
export function openExecution(task: TaskRecord, spec: OpenExecutionSpec, snap?: TokenSnapshot): ExecutionRecord

/** 收尾：闭合该任务全部 running 执行 + 写 end/delta。**唯一入口**。返回闭合条数。 */
export interface CloseExecutionsOpts { at: number; outcome: 'succeeded' | 'cancelled' | 'failed'; error?: string }
export function closeExecutions(task: TaskRecord, opts: CloseExecutionsOpts, snap?: TokenSnapshot): number

/** 中途刷新：给最近一条指定会话的 running 执行写 end/delta（不改 outcome）。返回是否命中。 */
export function refreshRunningExecution(task: TaskRecord, snap: TokenSnapshot, sessionId?: string): boolean
```

- **返回**：`openExecution` 返回新落的 `ExecutionRecord`；`closeExecutions` 返回闭合条数；`refresh` 返回 boolean。
- **错误语义**：不抛；非法状态由 `transitionTask` 负责拦截，快照助手只做「落账」。
- **不写条件**：`snap === undefined` → 只落/闭合执行记录，不写 token 字段（读路径按缺失降级）。
- **born-failed 决策**：`outcome==='failed'` 的执行（引擎/凭证门当场失败，没有可测执行段）**不写 start**，
  避免用事后快照冒充起点；该执行在读路径按缺失降级。

**调用点（四处产生点 → 助手）**

| 产生点 | 输入会话 | 开工 | 收尾 |
|---|---|---|---|
| agent `MoveTask.ts` | `windowKey`（真实 agent 会话） | `openExecution(..., snapshotForWindow(deps, windowKey))` | `closeExecutions(..., snapshotForWindow(deps, windowKey))` |
| 看板 `tasks.ts` | `body.sessionId`（可缺） | `snap = sessionId ? ctx.deps.tokenSnapshot?.(sessionId) : undefined` | 同左 |
| 自动链父卡 `AdvanceChain.openParent` | `safeWindowKey(deps, exec)` ?? `req.sourceSessionId` | `openExecution(..., snap)` | `closeExecutions(..., snap)`（finalizeParent） |
| 自动链子卡 `ExecuteTask` | `safeWindowKey(deps, input.exec)` ?? `input.windowKey`（`'system'` 视为无） | `openExecution(..., snap)` | `closeExecutions(..., snap)` |
| 中途汇报 `ReportTask.ts:136` | `windowKey` | — | `refreshRunningExecution(task, snap, windowKey)` |

## HTTP 入口 <!-- serves: FR-2, FR-3, FR-4, FR-6 -->

| 方法与路径 | 请求体变化 | 行为变化 | 响应变化 |
|---|---|---|---|
| `POST /dashboard/api/reqboard/task/move` | 已有 `sessionId?` | 开工/完工经执行助手写 start/end | 无（仍返回任务记录） |
| `POST /dashboard/api/reqboard/task/create` | **新增可选** `sessionId?` | 建卡触发的 rollup 带快照提供者 | 无 |
| `POST /dashboard/api/reqboard/task/update` | **新增可选** `sessionId?` | 改卡触发的 rollup 带快照提供者 | 无 |
| `POST /dashboard/api/reqboard/req/move` | **新增可选** `sessionId?` | 改经 `transitionRequirement` + 快照 | 无 |
| `POST /dashboard/api/reqboard/req/artifact/confirm` | 无 | 确认即推进带快照、actor 带 sessionId | 无 |
| `POST /dashboard/api/reqboard/req/verify/pass\|rework` | 无 | 改经 `transitionRequirement` + 快照 | 无 |
| `POST /dashboard/api/reqboard/req/verdicts` | 无 | `applyVerdicts` 调用补 `snap` | 无 |
| `GET /dashboard/api/reqboard/requirements/:id/token` | — | 读路径 `degraded` 判定加严 | 形状不变；`degraded` 可能由 false 变 true |

- 会话码取值优先级：请求体 `sessionId` → 需求的 `sourceSessionId`；都没有则不传（该段显示「无快照」）。
- **形状不变**是硬约束：端侧 `RequirementTokenView` / `RequirementTokenStageRow` / `TokenExecutionRow` 不改字段。

## Agent 工具入口 <!-- serves: FR-1, FR-4, FR-5, FR-6 -->

| 工具 | 入参变化 | 行为变化 | 错误码变化 |
|---|---|---|---|
| `reqboard_task_move` | 无 | 开工写 start、收尾写 end/delta（经执行助手） | 无（`REQBOARD_HUMAN_GATE` 等不变） |
| `reqboard_task_report` | 无 | 刷新 running 执行的 end/delta（`refreshRunningExecution`） | 无 |
| `reqboard_move` | 无 | 迁移带快照（已具备，保持不变） | 无 |
| `reqboard_submit` / `reqboard_decompose` | 无 | 派生推进带快照 | 无 |

## 错误与降级语义 <!-- serves: FR-1, FR-4, FR-5, FR-7, FR-8 -->

| 场景 | 语义 | 证据位置 |
|---|---|---|
| 会话端口抛错 | `captureSnapshot` 兜底 `source='unavailable'`，不阻断主流程 | `token-usage.ts:30-36` |
| 无会话上下文 | `snap=undefined`，不写快照；读路径 `degraded=true` | 本设计 FR-4/FR-6 |
| 非法状态迁移 | `transitionRequirement` / `transitionTask` 抛错 → `repo.mutate` 回滚，零副作用 | `token-usage.ts:151-153` |
| 快照写入失败（不可得） | delta 缺省，绝不用 0 / 单端累计冒充 | `endExecutionToken` |
| 读路径存在缺失 | `RequirementTokenView.degraded = true` | `QueryRequirementToken` |

## 兼容性矩阵 <!-- serves: FR-2, FR-3, FR-4, FR-6, FR-7 -->

| 维度 | 旧 → 新 | 兼容策略 |
|---|---|---|
| 台账 schema | v8 → v8 | 无迁移、无回填；旧记录可选字段缺失照常载入 |
| HTTP 请求体 | 无 `sessionId` → 可选 `sessionId` | 缺省 = 旧行为（不写快照，诚实降级） |
| HTTP 响应体 | 形状不变 | 端侧无需发版 |
| Agent 工具入参 | 不变 | 窗口 agent 无感 |
| 旧代码载入新台账 | — | 未知可选字段被忽略，无破坏 |
