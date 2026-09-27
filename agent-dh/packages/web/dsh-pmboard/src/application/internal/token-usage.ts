/**
 * Token 消耗写路径助手（REQ-a33899 t3）。
 *
 * 口径（唯一实现处，禁止在用例里重算）：
 *   节点消耗 = 「进入该节点的状态事件快照」→「离开该节点时的快照」之差，**同会话才相减**；
 *   任务消耗 = 执行记录 start/end 两次快照之差。
 * 只要任一端缺失或 source=unavailable，就**什么都不记**（UI 显示「无快照」），
 * 绝不用 0 冒充（0 是「确实没花」的合法值，缺失是「不知道」，二者不可混淆）。
 *
 * @module dsh-pmboard/application/internal/token-usage
 */
import type { UseCaseDeps } from '../ports.js'
import { assertReqTransition } from '../../domain/requirement/RequirementStatus.js'
import {
  addBuckets,
  emptyBuckets,
  recordStatus,
  subBuckets,
  type ActorRef,
  type ExecutionRecord,
  type ExecutionTokenUsage,
  type RequirementRecord,
  type RequirementStatus,
  type StageKey,
  type TaskRecord,
  type TokenBuckets,
  type TokenSnapshot,
} from '../../shared/protocol.js'

/** 取一次快照；端口抛错也不阻断主流程（快照是旁路证据，不是闸门）。 */
export function captureSnapshot(deps: UseCaseDeps, windowKey: string): TokenSnapshot {
  try {
    return deps.session.tokenTotals(windowKey)
  } catch {
    return { at: deps.clock.now(), totals: emptyBuckets(), source: 'unavailable' }
  }
}

/**
 * 进入 stage 时的快照：取该阶段最近一条**带可得快照**的状态事件；
 * 找不到 / 不是 projection / 会话不一致 → undefined（该段不可算）。
 */
export function entrySnapshotFor(
  req: RequirementRecord,
  stage: string,
  sessionId: string | undefined,
): TokenSnapshot | undefined {
  const history = req.statusHistory ?? []
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const e = history[i]!
    if (e.status !== stage) continue
    const snap = e.tokenSnapshot
    if (snap === undefined || snap.source !== 'projection') return undefined
    if (sessionId !== undefined && snap.sessionId !== undefined && snap.sessionId !== sessionId) return undefined
    return snap
  }
  return undefined
}

/** byStage 求和 → totals（展示口径单点：totals 永远等于各节点之和）。 */
function recomputeTotals(byStage: Partial<Record<StageKey, TokenBuckets>>): TokenBuckets {
  let t = emptyBuckets()
  for (const v of Object.values(byStage)) {
    if (v !== undefined) t = addBuckets(t, v)
  }
  return t
}

/**
 * 结算「刚离开的 stage」：exit 为离开时刻的快照。
 * 返回 true=确实累加了（两端快照都可得且同会话）；false=该段留「无快照」。
 */
export function accumulateStageDelta(req: RequirementRecord, stage: StageKey, exit: TokenSnapshot): boolean {
  if (exit.source !== 'projection') return false
  const entry = entrySnapshotFor(req, stage, exit.sessionId)
  if (entry === undefined) return false
  const delta = subBuckets(exit.totals, entry.totals)
  const usage = (req.tokenUsage ??= { byStage: {}, totals: emptyBuckets(), updatedAt: exit.at })
  usage.byStage[stage] = addBuckets(usage.byStage[stage] ?? emptyBuckets(), delta)
  usage.totals = recomputeTotals(usage.byStage)
  usage.updatedAt = exit.at
  return true
}

/** 任务执行开工：写 start 快照（delta 待完工时再算）。 */
export function beginExecutionToken(execution: ExecutionRecord, snap: TokenSnapshot): void {
  const usage: ExecutionTokenUsage = (execution.tokenUsage ??= {})
  usage.start = snap
  delete usage.delta
}

/**
 * 任务执行完工（或中途刷新）：写 end；两端都是 projection 且会话不冲突时算 delta，
 * 否则清空 delta（不可算就不给数，禁止用单端累计冒充本次消耗）。
 */
export function endExecutionToken(execution: ExecutionRecord, snap: TokenSnapshot): void {
  const usage: ExecutionTokenUsage = (execution.tokenUsage ??= {})
  usage.end = snap
  const start = usage.start
  const sameSession = start !== undefined
    && (start.sessionId === undefined || snap.sessionId === undefined || start.sessionId === snap.sessionId)
  if (start !== undefined && start.source === 'projection' && snap.source === 'projection' && sameSession) {
    usage.delta = subBuckets(snap.totals, start.totals)
  } else {
    delete usage.delta
  }
}

// ---------------------------------------------------------------------------
// 执行快照收敛助手（REQ-260927121324-abde t1 / FR-4、FR-5、FR-8）
//
// 任务执行的**唯一写入口**：落/闭合执行记录、写 start/end/delta 一律经本组函数，
// 调用方不得自行 `task.executions.push(...)` 或写 `execution.tokenUsage`（结构守卫
// tests/execution-token-guard.test.ts 机械断言）。内部只调 beginExecutionToken /
// endExecutionToken，保证 token 字段的唯一写点不散。
//
// 导出契约（调用方按用途取用，勿在用例里重算）：
//   openExecution(task, spec, snap?)          开工：落执行记录 + 写 start（born-failed 不写）
//   closeExecutions(task, opts, snap?)        收尾：闭合**全部** running + 写 end/delta
//   refreshRunningExecution(task, snap, sid?) 中途刷新：给最近一条同会话 running 刷 end/delta
//   snapshotForWindow(deps, key?)            窗口码 → 快照（缺失/空串 → undefined；取不到 → unavailable）
//   safeWindowKey(deps, exec?)               exec → 窗口码（缺 agent/'system'/抛错 → undefined）
//   snapshotProviderFor(deps, key?)          派生推进的快照提供者（显式窗口码优先，退回 sourceSessionId）
//
// 缺口语义（缺失 ≠ 0）：snap=undefined → 只落/闭合执行记录，**不写任何 token 字段**；
// 有窗口码但取不到 → captureSnapshot 兜底 source='unavailable'，仍如实落账（读路径据此
// 判 degraded）。本组函数**永不抛**（快照是旁路证据，不阻断主流程）。
// ---------------------------------------------------------------------------

/** 开工入参：一条执行记录的最小描述。 */
export interface OpenExecutionSpec {
  /** 执行 id（deps.ids.execution() / newExecutionId()）。 */
  id: string
  sessionId?: string
  trigger: 'manual' | 'auto'
  at: number
  /** 缺省 running；failed = born-failed（引擎/凭证门当场失败，没有可测执行段）。 */
  outcome?: 'running' | 'failed'
  error?: string
}

/**
 * 开工：落一条执行记录并写 start 快照（**唯一入口**）。
 *
 * born-failed（outcome='failed'）**不写 start**——没有可测执行段，用事后快照冒充起点
 * 等于编造；直接以已闭合的终止记录落账（endedAt=at）。
 */
export function openExecution(task: TaskRecord, spec: OpenExecutionSpec, snap?: TokenSnapshot): ExecutionRecord {
  const outcome = spec.outcome ?? 'running'
  const execution: ExecutionRecord = {
    id: spec.id,
    ...(spec.sessionId !== undefined ? { sessionId: spec.sessionId } : {}),
    trigger: spec.trigger,
    startedAt: spec.at,
    outcome,
    ...(outcome === 'failed' ? { endedAt: spec.at } : {}),
    ...(spec.error !== undefined ? { error: spec.error } : {}),
  }
  if (outcome === 'running' && snap !== undefined) beginExecutionToken(execution, snap)
  task.executions.push(execution)
  return execution
}

/** 收尾入参。 */
export interface CloseExecutionsOpts {
  at: number
  outcome: 'succeeded' | 'cancelled' | 'failed'
  error?: string
}

/**
 * 收尾：闭合该任务**全部** running 执行（写 endedAt/outcome，可选 error）并写 end/delta
 * （**唯一入口**）。返回闭合条数；snap=undefined → 只闭合记录、不写 token 字段。
 */
export function closeExecutions(task: TaskRecord, opts: CloseExecutionsOpts, snap?: TokenSnapshot): number {
  let closed = 0
  for (const e of task.executions) {
    if (e.outcome !== 'running') continue
    e.endedAt = opts.at
    e.outcome = opts.outcome
    if (opts.error !== undefined) e.error = opts.error
    if (snap !== undefined) endExecutionToken(e, snap)
    closed += 1
  }
  return closed
}

/**
 * 中途刷新（进度检查点）：给最近一条**同会话** running 执行写 end/delta，**不改 outcome**
 * （仍在跑）。sessionId 缺省 = 不限会话。返回是否命中（未命中不写）。
 */
export function refreshRunningExecution(task: TaskRecord, snap: TokenSnapshot, sessionId?: string): boolean {
  for (let i = task.executions.length - 1; i >= 0; i -= 1) {
    const e = task.executions[i]!
    if (e.outcome !== 'running') continue
    if (sessionId !== undefined && e.sessionId !== sessionId) continue
    endExecutionToken(e, snap)
    return true
  }
  return false
}

/**
 * 窗口码 → 快照：窗口码缺失/空串 → undefined（诚实不传，**不伪造**）。
 * 有窗口码却取不到 → captureSnapshot 兜底 source='unavailable'（「试过了但拿不到」）。
 */
export function snapshotForWindow(deps: UseCaseDeps, windowKey?: string): TokenSnapshot | undefined {
  if (typeof windowKey !== 'string' || windowKey.length === 0) return undefined
  return captureSnapshot(deps, windowKey)
}

/**
 * 从 exec 解析执行会话窗口码：无 exec / 缺 agent / 端口抛错 / `'system'` 哨兵 → undefined
 * （自动链等无真实会话的路径据此诚实不传快照）。**永不抛**。
 */
export function safeWindowKey(deps: UseCaseDeps, exec?: unknown): string | undefined {
  try {
    const key = deps.session.windowKey(exec)
    if (typeof key !== 'string' || key.length === 0 || key === 'system') return undefined
    return key
  } catch {
    return undefined
  }
}

/**
 * 派生推进的快照提供者（FR-6）：优先显式窗口码，退回 `req.sourceSessionId`；都无 → undefined。
 * 供 `applyTaskRollup(ledger, tasks, { snapshot: snapshotProviderFor(deps, windowKey) }, ...)` 使用
 * （REQ-260927202051-f6df D6：`tasks` 为第 2 参；v9 起任务来自 TaskStore，不再取台账 `tasks`）。
 */
export function snapshotProviderFor(
  deps: UseCaseDeps,
  windowKey?: string,
): (req: RequirementRecord) => TokenSnapshot | undefined {
  return (req) => {
    const key = typeof windowKey === 'string' && windowKey.length > 0 ? windowKey : req.sourceSessionId
    return snapshotForWindow(deps, key)
  }
}

/**
 * 需求状态迁移选项（REQ-b545fe t1）。
 */
export interface TransitionOpts {
  /** 迁移时刻 */
  at: number
  /** 操作者（agent/human/system + 可选 sessionId） */
  actor: ActorRef
  /** 迁移理由（可选） */
  reason?: string
  /** 快照（可选；不传 = 调用方无会话上下文 → 不结算不带快照） */
  snap?: TokenSnapshot
  /**
   * 逃生舱（默认 false = 校验收紧）：跳过状态机校验。
   *
   * **只允许"不表示业务流转"的写入使用**——如迁移脚本把历史记录归一到规范状态。
   * 任何业务路径都不得设置它：那正是"非法状态变换"的入口（见下方 transitionRequirement 注释）。
   */
  allowIllegalTransition?: boolean
}

/**
 * 唯一的需求状态迁移助手（REQ-b545fe t1）：结算离开节点 + 迁移状态 + 记录事件带快照。
 * 
 * 全部 5 条状态迁移路径（MoveRequirement/AskConfirm/rollup/AcceptSheet/verdicts）
 * 必须且只能通过此函数迁移需求状态，消除"改了状态但没结算快照"这一类 bug 的结构性根源。
 * 
 * @param req 需求记录（就地修改）
 * @param to 目标状态
 * @param opts 迁移选项（时刻/操作者/理由/快照）
 */
export function transitionRequirement(
  req: RequirementRecord,
  to: RequirementStatus,
  opts: TransitionOpts,
): void {
  const from = req.status as RequirementStatus
  // 0. 状态机校验（纵深防御，2026-09-27 补）：**收敛点必须自己拦**，不能寄望每个调用方
  //    都记得校验。此前本函数直接 `req.status = to` 无任何校验，于是：
  //    事故——confirm-settle 的"批准计划"分支漏了 canReqTransition，而本函数也不校验，
  //    需求便在**计划未落库（台账 0 任务）**的情况下直接进入 implementing，
  //    导致 DAG / 泳道 / 实施覆盖度全空且**零告警**，静默停滞数日。
  //    现在无论哪个调用方漏检，非法/越权流转都会在此抛错。
  if (opts.allowIllegalTransition !== true) {
    assertReqTransition(from, to, opts.actor.kind)
  }
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
