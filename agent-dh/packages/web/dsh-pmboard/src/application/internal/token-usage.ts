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
