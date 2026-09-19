# REQ-b545fe 实施计划

## 目标

修复流水线节点 token 统计漏记：把「结算离开节点快照差值 + 新事件带快照」收敛为唯一的状态迁移助手，
全部 5 条状态迁移路径（reqboard_move / ask_confirm 推进 / rollup 派生 / 验收归档 / 验收打回）统一使用，
消除"改了状态但没结算"这一类 bug 的结构性根源。

## 技术设计

### 核心：唯一迁移助手

新增 `internal/token-usage.ts::transitionRequirement`：

```typescript
export interface TransitionOpts {
  at: number
  actor: StatusActor  // { kind: 'agent' | 'human' | 'system', sessionId?: string }
  reason?: string
  snap?: TokenSnapshot  // 可选快照；不传 = 调用方无会话上下文 → 不结算不带快照（诚实）
}

export function transitionRequirement(
  req: RequirementRecord,
  to: RequirementStatus,
  opts: TransitionOpts,
): void {
  // 1. 结算离开节点：快照可得 + entrySnapshotFor 成功 → 累加到 byStage + 更新 totals
  if (opts.snap !== undefined) {
    accumulateStageDelta(req, req.status as StageKey, opts.snap)
  }
  // 2. 迁移状态
  req.status = to
  req.version += 1
  req.updatedAt = opts.at
  req.updatedBy = opts.actor
  // 3. 记录状态事件（带快照 or undefined）
  recordStatus(req, to, opts.at, opts.actor, opts.reason, opts.snap)
}
```

**口径保持**：snap 为 undefined 或 source=unavailable → accumulateStageDelta 返回 false，
该段不记值；recordStatus 允许快照可选，事件无快照 → entrySnapshotFor 失败 → 后续段不可算。
全流程「缺失≠0、不伪造」原则不变。

### rollup 路径：可选快照提供者

`RollupContext` 扩展：

```typescript
export interface RollupContext {
  now: number
  commentId: () => string
  snapshot?: (req: RequirementRecord) => TokenSnapshot | undefined  // 可选快照提供者
}
```

`rollup.ts::advance` 内调用 `transitionRequirement`，snap 从 `ctx.snapshot?.(req)` 获取。

**调用方适配**：
- use-cases（MoveRequirement/MoveTask/Decompose/SubmitVerification）：传 `snapshot: () => captureSnapshot(deps, windowKey)`
- index.ts 启动对账/接手推进：不传（无会话）→ 诚实无快照
- routers/tasks.ts：将 RouterCtx 扩展接入 SessionProbeAdapter，handleTaskMove 有 sessionId 时传 `() => ctx.tokenSnapshot?.(sessionId)`

### verdicts 打回路径

`applyVerdicts` 签名扩展：

```typescript
export function applyVerdicts(
  ledger: ReqboardLedger,
  reqId: string,
  version: number,
  verdicts: readonly VerdictInput[],
  actor: ActorRef,
  nowTs: number,
  commentId: () => string,
  snap?: TokenSnapshot,  // 新增：验收打回时的快照
): ApplyVerdictsResult
```

打回时（r.status accepting→implementing）调用 `transitionRequirement` 而非直接写状态。
唯一调用方 AcceptSheet.ts:190 传 `captureSnapshot(deps, windowKey)`。

### HTTP 路由快照接入（可选，非关键路径）

`ReqboardRouteDeps` 扩展：

```typescript
export interface ReqboardRouteDeps {
  store: ReqboardStore
  now: () => number
  injectionLog?: InjectionLogReadPort
  systemPrompt?: () => unknown
  tokenSnapshot?: (windowKey: string) => TokenSnapshot | undefined  // 新增
  ids?: { ... }
  cwd?: string
}
```

index.ts 插件启动时注入 SessionProbeAdapter：

```typescript
const routeDeps: ReqboardRouteDeps = {
  store,
  now,
  tokenSnapshot: (wk) => {
    try { return sessionProbe?.tokenTotals(wk) } catch { return undefined }
  },
  ...
}
```

routers/tasks.ts `handleTaskMove` 有 `sessionId` 时传给 applyTaskRollup ctx。

## 任务分解

### t1：核心迁移助手（internal/token-usage.ts）

**实施**：
- 新增 `TransitionOpts` 接口与 `transitionRequirement` 函数
- 函数逻辑：snap 存在时调 accumulateStageDelta → 迁移状态（status/version/updatedAt/updatedBy）→ recordStatus(含 snap)
- 导出供全部用例使用

**验收**：
- 单测：构造 req + 递增假快照，调用 transitionRequirement，断言 byStage[oldStage] 累加、status 已改、statusHistory 最后事件带快照
- 单测：snap=undefined 调用，断言不累加 byStage、recordStatus 事件无快照（entrySnapshotFor 自然失败）

### t2：MoveRequirement 改用迁移助手

**实施**：
- MoveRequirement.ts:113-119 替换为 `transitionRequirement(req, to, { at: deps.clock.now(), actor: {kind:'agent', sessionId:windowKey}, reason, snap: captureSnapshot(deps, windowKey) })`
- 删除原地 status/version/updatedAt/updatedBy/recordStatus/accumulateStageDelta 逻辑（全在助手里）

**验收**：
- 回归：既有 move 相关测试（artifact-gates / rollup / plan-mode 等）全绿
- 单测补充：模拟 move 带快照，断言 byStage 累加正确

### t3：AskConfirm 改用迁移助手

**实施**：
- AskConfirm.ts:174-178 替换为 `transitionRequirement(req, to, { at: nowTs, actor: {kind:'human', sessionId:windowKey}, reason: '确认弹框后自动推进', snap: captureSnapshot(deps, windowKey) })`
- 删除原地 status/version/updatedAt/updatedBy/recordStatus 逻辑

**验收**：
- 回归：tests/artifact-gates.test.ts（ask_confirm 推进场景）通过
- 单测补充：模拟 brainstorming→planning 推进，断言 brainstorming 节点 byStage 累加

### t4：rollup 改用迁移助手 + 可选快照提供者

**实施**：
- `RollupContext` 扩展 `snapshot?: (req) => TokenSnapshot | undefined`
- rollup.ts::advance 调用 `transitionRequirement(req, to, { at: ctx.now, actor: {kind:'system'}, reason, snap: ctx.snapshot?.(req) })`
- 删除原地 status/version/updatedAt/updatedBy/recordStatus 逻辑
- 调用方适配：
  - MoveRequirement.ts:127、MoveTask.ts:101、Decompose.ts:239、SubmitVerification.ts:161 传 `snapshot: () => captureSnapshot(deps, windowKey)`
  - index.ts:131、236 不传（无会话，诚实无快照）
  - routers/tasks.ts:65,108 暂不传（t6 接入 HTTP 快照后再传）

**验收**：
- 回归：tests/routes-rollup.test.ts 全绿
- 单测补充：构造 planning→decomposing rollup 推进 + 假快照提供者，断言 planning 节点 byStage 累加；构造无快照提供者，断言不累加

### t5：AcceptSheet 归档 + verdicts 打回改用迁移助手

**实施**：
- AcceptSheet.ts:95-99 accepting→archived 替换为 `transitionRequirement(r, 'archived', { at: nowTs2, actor: {kind:'human', sessionId:windowKey}, reason: '验收通过', snap: captureSnapshot(deps, windowKey) })`
- verdicts.ts::applyVerdicts 签名扩展 `snap?: TokenSnapshot` 参数
- verdicts.ts:132-136 accepting→implementing 替换为 `transitionRequirement(r, 'implementing', { at: nowTs, actor, reason, snap })`
- AcceptSheet.ts:190 调用 applyVerdicts 时传 `captureSnapshot(deps, windowKey)`

**验收**：
- 回归：tests/accept-sheet-tool.test.ts、tests/verdicts-and-rework.test.ts 全绿
- 单测补充：模拟归档 + 打回路径，断言 accepting 节点 byStage 累加

### t6：HTTP 路由快照接入（routers/tasks.ts）

**实施**：
- ReqboardRouteDeps 扩展 `tokenSnapshot?: (windowKey: string) => TokenSnapshot | undefined`
- index.ts 构造 routeDeps 时注入 SessionProbeAdapter：`tokenSnapshot: (wk) => { try { return deps.session.tokenTotals(wk) } catch { return undefined } }`（deps.session 从 plugin ctx 获取）
- routers/tasks.ts::handleTaskMove 读 body.sessionId，传给 applyTaskRollup ctx：`snapshot: body.sessionId ? () => ctx.tokenSnapshot?.(body.sessionId) : undefined`
- 同步更新 t4 routers 调用点

**验收**：
- 单测：模拟 HTTP POST /tasks/:id/move 带 sessionId，mock tokenSnapshot 返回递增快照，断言 rollup 派生推进带快照结算
- 回归：既有 routes 测试通过

### t7：端到端验证 + 文档更新

**实施**：
- 重建 pmboard 客户端：`cd packages/pages/dsh-pmboard && pnpm run build:client`
- 重启插件（让新代码生效）
- 新建测试需求 REQ-test-xxx，模拟全流程：draft→brainstorming（move）→planning（ask_confirm）→decomposing（rollup）→implementing（rollup）→accepting（rollup）→archived（accept_sheet）
- curl `GET /dashboard/api/reqboard/requirements/:id/token`，核对 byStage 键覆盖全部经过节点（draft/brainstorming/planning/decomposing/implementing/accepting）
- 打开需求详情页流程图，目视验证每个节点显示 token 数值（或诚实无快照）
- 更新 docs/architecture/reqboard-token-usage.md §落点：「全部 5 条状态迁移路径统一经 transitionRequirement 结算」

**验收**：
- byStage 包含全部 6 个经过节点的 key（draft/brainstorming/.../accepting）
- 流程图节点全部有 token 或诚实标注「无快照」
- 回归：`pnpm test` 全绿，`pnpm typecheck` 无错，`pnpm run build:client` 成功
- 文档已更新

## 数据层与回滚

- **无 schema 变更**：token-usage.ts 现有字段足够（byStage/totals/updatedAt）
- **无迁移脚本**：历史数据按口径保持「无快照」，不伪造回填
- **回滚**：git revert 本批 commit，重启插件即可；历史已归档需求本就无完整快照，回滚后状态一致

## 风险

1. **rollup 多次推进**：applyTaskRollup 单次可触发多步（planning→decomposing→implementing），
   每步都结算 → 可能一次 mutate 内累加多个节点。已验证：accumulateStageDelta 幂等（重复累加同段不会翻倍），
   且 rollup.ts::applyMoves 循环至稳定、每步都留痕，风险可控。

2. **FakeSession 测试兼容**：既有测试 mock 的 FakeSession 需补 tokenTotals 方法（返回假快照）。
   已验证 tests/ 下 17 个测试文件，token 相关 4 个需适配。

## 排除项

- 不改任何状态机转移规则（assertReqTransition / HUMAN_ONLY_REQ_TRANSITIONS 保持原样）
- 不改 RollupSpec 纯函数决策层（planRollup / planPickupAdvance 等不动）
- 不改 token 口径（四分桶/同会话才相减/负差截断规则不动）
