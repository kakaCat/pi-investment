/**
 * 需求 token 消耗读路径（REQ-a33899 t4）。
 *
 * 只做投影：把台账里已落的写时快照装配成 byStage + executions 视图，不重算、不猜数。
 * 缺失语义：**节点无快照时 buckets 为 undefined**（UI 显示「无快照」），
 * 而不是 0——0 表示「确实一次都没花」，两者必须能区分。
 *
 * @module dsh-pmboard/application/query/QueryRequirementToken
 */
import {
  ALL_STAGE_KEYS,
  addBuckets,
  emptyBuckets,
  totalTokens,
  type RequirementRecord,
  type RequirementTokenStageRow,
  type RequirementTokenView,
  type StageKey,
  type TaskRecord,
  type TokenBuckets,
  type TokenExecutionRow,
} from '../../shared/protocol.js'

/**
 * 任务视图（REQ-260927202051-f6df）：token 投影只需要任务数组。
 *
 * 原为 `Pick<TasksView, 'tasks'>` —— 任务在 schema v9 后不再存台账，`LedgerView.tasks` 已移除，
 * 任务唯一来源是队列（TaskStore）。调用方先 `await taskStore.listByRequirement(id)` 再以 `{ tasks }` 传入；
 * 本模块全部函数保持**同步纯投影**，不碰 IO。
 */
export interface TasksView {
  readonly tasks: readonly TaskRecord[]
}

export type { RequirementTokenStageRow, RequirementTokenView, TokenExecutionRow }

// 线上契约类型统一在 shared/protocol（host 装配与 client 渲染共用同一份形状）
/** 某节点是否已有可算快照（有 tokenUsage 且该节点在册）。 */
export function stageBucketsOf(req: RequirementRecord, stage: StageKey): TokenBuckets | undefined {
  const b = req.tokenUsage?.byStage?.[stage]
  return b === undefined ? undefined : b
}

/**
 * 存在快照缺口（**缺失与不可得同等计**，FR-7）：
 *  ① 需求侧：任何一条状态事件缺 tokenSnapshot，或 source 非 projection（unavailable）→ 该节点快照不可知；
 *  ② 任务侧：执行记录运行中（endedAt 缺失）要求 start 可得；已闭合要求 start/end 均为 projection。
 * 只查台账里真实存在的事件与执行——「从未进入的节点」不判缺失，否则每个需求恒为 degraded、信号失效。
 */
function hasSnapshotGap(req: RequirementRecord, view: Pick<TasksView, 'tasks'>): boolean {
  for (const e of req.statusHistory ?? []) {
    if (e.tokenSnapshot === undefined || e.tokenSnapshot.source !== 'projection') return true
  }
  for (const t of view.tasks) {
    if (t.requirementId !== req.id) continue
    for (const e of t.executions) {
      const startOk = e.tokenUsage?.start?.source === 'projection'
      const endOk = e.tokenUsage?.end?.source === 'projection'
      if (e.endedAt === undefined ? !startOk : !(startOk && endOk)) return true
    }
  }
  return false
}

function executionRows(req: RequirementRecord, view: Pick<TasksView, 'tasks'>): TokenExecutionRow[] {
  const rows: TokenExecutionRow[] = []
  for (const t of view.tasks) {
    if (t.requirementId !== req.id) continue
    for (const e of t.executions) {
      const u = e.tokenUsage
      if (u === undefined) continue
      rows.push({
        taskId: t.id,
        title: t.title,
        status: t.status,
        ...(u.delta !== undefined ? { delta: u.delta } : {}),
        ...(u.start !== undefined ? { start: u.start } : {}),
        ...(u.end !== undefined ? { end: u.end } : {}),
      })
    }
  }
  return rows
}

/**
 * 装配需求 token 视图。
 * 任务执行归到 implementing 节点（任务是实施阶段的产物，执行消耗属该节点）。
 */
export function assembleRequirementToken(
  req: RequirementRecord,
  view: Pick<TasksView, 'tasks'>,
): RequirementTokenView {
  const executions = executionRows(req, view)
  const byStage: RequirementTokenStageRow[] = ALL_STAGE_KEYS.map(stage => ({
    stage,
    ...(stageBucketsOf(req, stage) !== undefined ? { buckets: stageBucketsOf(req, stage)! } : {}),
    executions: stage === 'implementing' ? executions : [],
  }))
  const usage = req.tokenUsage
  // 总量口径：Σ 各节点。节点有快照 → 用节点差值；节点无快照但其任务执行有差值 → 用执行差值合计兜底。
  // 为什么需要兜底：功能上线前创建的需求没有节点进入快照，但任务执行差值仍可得；
  // 不兜底会出现「总量 0、任务行有数」的自相矛盾（口径不完整就等于错）。
  let totals = emptyBuckets()
  for (const row of byStage) {
    if (row.buckets !== undefined) {
      totals = addBuckets(totals, row.buckets)
      continue
    }
    for (const e of row.executions) {
      if (e.delta !== undefined) totals = addBuckets(totals, e.delta)
    }
  }
  const result: RequirementTokenView = {
    requirementId: req.id,
    totals,
    byStage,
    degraded: usage === undefined || hasSnapshotGap(req, view),
  }
  if (usage?.costEstimateCny !== undefined) result.costEstimateCny = usage.costEstimateCny
  return result
}

/** 便捷：需求 total token（卡面展示用）；无快照 → undefined（不显示 0）。 */
export function requirementTotalTokens(req: RequirementRecord): number | undefined {
  if (req.tokenUsage === undefined) return undefined
  return totalTokens(req.tokenUsage.totals)
}
