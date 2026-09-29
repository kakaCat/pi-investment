/**
 * AdvanceChain 用例（REQ-4842fe t7 / FR-11、FR-12）——**事件链执行器**。
 *
 * 机制一句话：不是"一条传送带一直转"，而是"推倒第一张骨牌，它自己撞倒下一张"——
 * 每完成一步自动触发下一步，直到 ROLLUP（需求进验收）或 PAUSE（失败/熔断/人工关闭）。
 *
 * 四性（design/architecture §4）：
 *  - 小：一次事件只推进一张子卡 / 一步收尾；
 *  - 幂等：选择依据全部来自台账状态（重复触发只会 noop）；
 *  - 可中断：不触发下一步，链即停住；
 *  - 留痕：台账 advance.history + docs/requirements/<REQ>/advance-log.md。
 *
 * 并发：进程内单飞 Set + 台账 advance.lockAt（stale 阈值可接管）。
 *
 * @module dsh-pmboard/application/use-cases/AdvanceChain
 */
import type { UseCaseDeps } from '../ports.js'
import { fmt } from '../../domain/text/fmt.js'
import { LIMITS } from '../../domain/limits.js'
import {
  hasOpenWork,
  selectAdvanceEvent,
  subtasksOf,
  type AdvanceSelection,
} from '../internal/advance-select.js'
import { executeSubtask } from './ExecuteTask.js'
import { expandSubtasks } from '../internal/lazy-expand.js'
import { applyTaskRollup } from '../internal/rollup.js'
import { assertDoneEvidence } from '../internal/support.js'
import { classifyFailure, isTransientAbort, rollbackSubtask } from '../internal/failure-handling.js'
import {
  type AdvanceEvent,
  type AdvanceRecord,
  type RequirementRecord,
  type TaskRecord,
} from '../../shared/protocol.js'
import { transitionTask } from '../internal/task-transition.js'
import {
  closeExecutions,
  openExecution,
  safeWindowKey,
  snapshotForWindow,
  snapshotProviderFor,
} from '../internal/token-usage.js'
import { taskStoreOf } from './queue-access.js'

export type AdvanceStop =
  | 'rollup' | 'paused' | 'noop' | 'terminal' | 'not_autorun' | 'not_found' | 'max_steps' | 'locked'

export interface AdvanceStep {
  event: AdvanceEvent
  outcome: 'ok' | 'failed' | 'skipped' | 'noop'
  parentId?: string
  subtaskId?: string
  detail: string
  durationMs: number
}

export interface AdvanceOutcome {
  requirementId: string
  steps: AdvanceStep[]
  stopped: AdvanceStop
  /** 是否成功投递（REQ-260925110957-552d FR-1） */
  dispatched?: boolean
  /** Job ID（dispatched=true 时） */
  job_id?: string
  /** Run ID（dispatched=true 时） */
  run_id?: string
  /** 拒绝原因（dispatched=false 时） */
  reason?: string
  /** 已有的 run ID（幂等检查时） */
  existing_run_id?: string
}

/** 进程内单飞（同需求同时只允许一个事件在跑）。 */
const inflight = new Set<string>()

const TERMINAL_REQ = new Set(['accepting', 'archived', 'canceled', 'done'])

function stepOf(
  event: AdvanceEvent,
  outcome: AdvanceStep['outcome'],
  detail: string,
  startedAt: number,
  now: number,
  extra: Partial<AdvanceStep> = {},
): AdvanceStep {
  return { event, outcome, detail, durationMs: Math.max(0, now - startedAt), ...extra }
}

async function appendHistory(deps: UseCaseDeps, requirementId: string, record: AdvanceRecord): Promise<void> {
  await deps.repo.mutate('advance-history', (ledger) => {
    const req = ledger.requirements.find((r) => r.id === requirementId)
    if (req === undefined) return undefined
    const adv = (req.advance ??= {})
    adv.history = [...(adv.history ?? []), record]
    return { requirements: [req] }
  })
  // 事件日志（append-only，best-effort：写文档失败不改变链的推进结果）
  try {
    const path = fmt('docs/requirements/{req}/advance-log.md', { req: requirementId })
    const prev = deps.docs.exists(path) ? await deps.docs.read(path) : '# 推进事件日志\n'
    const line = fmt('- {at} [{event}] parent={parent} subtask={sub} {outcome}：{detail}', {
      at: new Date(record.at).toISOString(),
      event: record.event,
      parent: record.parentId ?? '-',
      sub: record.subtaskId ?? '-',
      outcome: record.outcome,
      detail: record.detail,
    })
    await deps.docs.write(path, prev.replace(/\s*$/, '\n') + line + '\n')
  } catch { /* 日志失败不影响链 */ }
}

async function pauseRequirement(deps: UseCaseDeps, requirementId: string, reason: string, detail: string): Promise<void> {
  const now = deps.clock.now()
  await deps.repo.mutate('advance-pause', (ledger) => {
    const req = ledger.requirements.find((r) => r.id === requirementId)
    if (req === undefined) return undefined
    req.autoRun = false
    const adv = (req.advance ??= {})
    adv.pausedReason = reason
    adv.noopStreak = 0
    adv.history = [...(adv.history ?? []), { at: now, requirementId, event: 'PAUSE', outcome: 'skipped', durationMs: 0, detail }]
    req.comments.push({
      id: deps.ids.comment(),
      body: fmt('[自动链暂停] {reason}：{detail}（autoRun 已置 false，可人工继续）', { reason, detail }),
      createdAt: now,
      createdBy: { kind: 'system' },
    })
    return { requirements: [req] }
  })
}

async function openParent(deps: UseCaseDeps, requirementId: string, parentId: string, startedAt: number, exec?: unknown): Promise<AdvanceStep> {
  const now = deps.clock.now()
  const store = taskStoreOf(deps)
  // 需求侧只读（台账仍在）：req 供 autoRun/sourceSessionId；任务一律走队列（v9 无 tasks）。
  const req = deps.repo.snapshot().requirements.find((r) => r.id === requirementId)
  let created: TaskRecord[] = []
  // 顺序契约（REQ-260927202051-f6df t9）：任务写经 TaskStore，本函数**不动需求**（comments 等由
  // advance-history 单独写），故不存在任务/需求交错。
  const changed = await store.mutate(requirementId, (tasks) => {
    const parent = tasks.find((t) => t.id === parentId)
    if (req === undefined || parent === undefined || parent.status !== 'todo') return undefined
    const active = tasks.filter(
      (t) => t.parentId === undefined && t.status === 'in_progress',
    ).length
    if (active >= LIMITS.advanceMaxParallelParents) return undefined
    transitionTask(parent, 'in_progress', { at: now, actor: { kind: 'system' }, role: 'parent' })
    parent.claimedAt = now
    parent.claimedBy = 'system'
    // 执行快照唯一写入口（REQ-260927121324-abde FR-4）：开工落记录 + 写 start 快照。
    // 自动链父卡会话码 = safeWindowKey(deps, exec) ?? req.sourceSessionId；解析不到（system /
    // 无 agent）→ 诚实不写快照（缺失 ≠ 0，禁止编造 token 归属）。
    const sessionKey = safeWindowKey(deps, exec) ?? req.sourceSessionId
    openExecution(
      parent,
      {
        id: deps.ids.execution(),
        trigger: 'auto',
        at: now,
        ...(sessionKey !== undefined ? { sessionId: sessionKey } : {}),
      },
      snapshotForWindow(deps, sessionKey),
    )
    // 懒展开（reader-http 已裂变）：只返回新建子卡、不落库 → 由本回调 append 进 draft。
    created = expandSubtasks(tasks, parent, req, now, deps.ids)
    // TaskRecord → QueueTask：layer 为派生占位，落盘前由 TaskStore.recompute 重算。
    if (created.length > 0) tasks.push(...created.map(c => ({ ...c, layer: 0 })))
    return tasks
  })
  if (changed.length === 0) {
    return stepOf('OPEN_PARENT', 'noop', fmt('父卡 {id} 不可开工（已在跑/已达并发上限）', { id: parentId }), startedAt, deps.clock.now(), { parentId })
  }
  return stepOf('OPEN_PARENT', 'ok', fmt('父卡 {id} 自动开工并落子卡 {n} 张', { id: parentId, n: created.length }), startedAt, deps.clock.now(), { parentId })
}

async function finalizeParent(deps: UseCaseDeps, parentId: string, startedAt: number, exec?: unknown): Promise<AdvanceStep> {
  const now = deps.clock.now()
  const store = taskStoreOf(deps)
  const parent0 = await store.get(parentId)
  const parentReq = parent0 === undefined
    ? undefined
    : deps.repo.snapshot().requirements.find((r) => r.id === parent0.requirementId)
  try {
    const changed = await store.mutate(parent0?.requirementId ?? '', (tasks) => {
      const parent = tasks.find((t) => t.id === parentId)
      if (parent === undefined || parent.status !== 'in_progress') return undefined
      const subs = subtasksOf({ tasks }, parent.id)
      if (subs.length === 0 || !subs.every((s) => s.status === 'done' || s.status === 'canceled')) return undefined
      const files = [...new Set(subs.flatMap((s) => s.lastReport?.filesChanged ?? []))]
      const completed = [...new Set(subs.flatMap((s) => s.lastReport?.completed ?? []))]
      parent.lastReport = {
        at: now,
        reportIndex: (parent.lastReport?.reportIndex ?? 0) + 1,
        filesChanged: files,
        completed: completed.length > 0 ? completed : [fmt('子卡 {n} 张全部完成', { n: subs.length })],
      }
      // D4：assertDoneEvidence 新签名 (deps, windowKey, task, ledger, tasks)。
      assertDoneEvidence(deps, 'system', parent, deps.repo.snapshot(), tasks)
      transitionTask(parent, 'done', { at: now, actor: { kind: 'system' }, role: 'parent' })
      // 收尾唯一入口（REQ-260927121324-abde FR-5）：闭合全部 running 并写 end/delta（快照在收尾
      // 时刻新取，非开工旧值）；会话码解析同 openParent，无会话只闭合记录、不写 token 字段。
      const sessionKey = safeWindowKey(deps, exec) ?? parentReq?.sourceSessionId
      closeExecutions(parent, { at: now, outcome: 'succeeded' }, snapshotForWindow(deps, sessionKey))
      return tasks
    })
    if (changed.length === 0) {
      return stepOf('FINALIZE_PARENT', 'noop', fmt('父卡 {id} 尚不可收尾', { id: parentId }), startedAt, deps.clock.now(), { parentId })
    }
    return stepOf('FINALIZE_PARENT', 'ok', fmt('父卡 {id} 汇总子卡产出并收尾', { id: parentId }), startedAt, deps.clock.now(), { parentId })
  } catch (err) {
    return stepOf('FINALIZE_PARENT', 'failed', (err as Error).message, startedAt, deps.clock.now(), { parentId })
  }
}

async function runSubtaskStep(deps: UseCaseDeps, parentId: string, subtaskId: string, startedAt: number, exec?: unknown, runSignal?: AbortSignal): Promise<AdvanceStep> {
  // REQ-4842fe design/architecture §3：`parent: exec.agent`——调用者 agent 必须一路透传到引擎，
  // 否则 workflow-ptc 读 request.parent.session 直接抛错（start_failed）。缺 exec 时保持原样，
  // 由引擎显式失败（不静默成功）。
  const r = await executeSubtask(deps, {
    subtaskId,
    windowKey: 'system',
    ...(exec !== undefined ? { exec } : {}),
    // Phase2：把**后台 job 的 signal** 透传下去（取消权归工作单元，不是派发它的 turn）。
    ...(runSignal !== undefined ? { runSignal } : {}),
  })
  return stepOf(
    'RUN_SUBTASK',
    r.ok ? 'ok' : 'failed',
    r.ok ? fmt('子卡 {id} 执行完成', { id: subtaskId }) : (r.reason ?? '执行失败'),
    startedAt,
    deps.clock.now(),
    { parentId, subtaskId },
  )
}

async function rollupStep(deps: UseCaseDeps, requirementId: string, startedAt: number, exec?: unknown): Promise<AdvanceStep> {
  const now = deps.clock.now()
  // D6：rollup 的输入任务改从队列取（台账 v9 无 tasks）；repo.mutate 只写需求（顺序契约的"后"）。
  const rollupTasks = await taskStoreOf(deps).listByRequirement(requirementId)
  const result = await deps.repo.mutate('advance-rollup', (ledger) => {
    // 派生推进快照提供者（REQ-260927121324-abde FR-6）：显式窗口码 safeWindowKey(deps, exec)
    // 优先，退回 req.sourceSessionId；都无 → 诚实不传（与启动对账同一口径）。
    const advanced = applyTaskRollup(
      ledger,
      rollupTasks,
      { now, commentId: () => deps.ids.comment(), snapshot: snapshotProviderFor(deps, safeWindowKey(deps, exec)) },
      requirementId,
    )
    return advanced.length > 0 ? { requirements: advanced } : undefined
  })
  const ok = (result.changed.requirements ?? []).length > 0
  return stepOf('ROLLUP', ok ? 'ok' : 'noop', ok ? '需求已全部任务完成，滚进验收' : '暂不可 rollup', startedAt, deps.clock.now())
}

async function runSelection(deps: UseCaseDeps, requirementId: string, sel: AdvanceSelection, startedAt: number, exec?: unknown, runSignal?: AbortSignal): Promise<AdvanceStep> {
  if (sel.event === 'OPEN_PARENT' && sel.parentId !== undefined) return openParent(deps, requirementId, sel.parentId, startedAt, exec)
  if (sel.event === 'FINALIZE_PARENT' && sel.parentId !== undefined) return finalizeParent(deps, sel.parentId, startedAt, exec)
  if (sel.event === 'RUN_SUBTASK' && sel.subtaskId !== undefined) return runSubtaskStep(deps, sel.parentId ?? '', sel.subtaskId, startedAt, exec, runSignal)
  if (sel.event === 'ROLLUP') return rollupStep(deps, requirementId, startedAt, exec)
  return stepOf('PAUSE', 'skipped', '无对应事件实现', startedAt, deps.clock.now())
}

/**
 * 链的推进循环（REQ-260927100007-b8ba t-8bce7d）——投递路径与**无后台任务端口**的
 * 同步兼容路径共用同一份逻辑，避免两份实现漂移。
 */
async function driveChain(
  deps: UseCaseDeps,
  requirementId: string,
  exec: unknown,
  isAborted: () => boolean,
  /** 承载本次链的后台 job 的 signal（Phase2）；同步兼容路径不传 → 子卡回落调用方 turn 的 signal。 */
  runSignal?: AbortSignal,
): Promise<{ steps: AdvanceStep[]; stopped: AdvanceStop }> {
  inflight.add(requirementId)
  const steps: AdvanceStep[] = []
  let stopped: AdvanceStop = 'max_steps'

  try {
    for (let i = 0; i < LIMITS.advanceMaxStepsPerCall; i += 1) {
      if (isAborted()) {
        stopped = 'paused'
        break
      }

      const snap = deps.repo.snapshot()
      const req = snap.requirements.find((r) => r.id === requirementId)
      if (req === undefined) { stopped = 'not_found'; break }
      if (req.autoRun !== true) { stopped = 'not_autorun'; break }
      if (TERMINAL_REQ.has(req.status)) { stopped = 'terminal'; break }

      // 任务已迁出台账（v9）：每轮迭代按需求取一次队列任务（事件选择的唯一输入）。
      const queueTasks = await taskStoreOf(deps).listByRequirement(requirementId)
      const sel = selectAdvanceEvent({ tasks: queueTasks }, requirementId, LIMITS.advanceMaxParallelParents)
      if (sel === undefined) {
        if (!hasOpenWork({ tasks: queueTasks }, requirementId)) { stopped = 'noop'; break }
        const streak = (req.advance?.noopStreak ?? 0) + 1
        if (streak >= LIMITS.advanceNoopBreaker) {
          await pauseRequirement(deps, requirementId, 'stagnation', fmt('连续 {n} 次无可推进事件（疑似依赖死锁）', { n: streak }))
          steps.push(stepOf('PAUSE', 'skipped', fmt('停滞熔断：连续 {n} 次 noop', { n: streak }), deps.clock.now(), deps.clock.now()))
          stopped = 'paused'
          break
        }
        await deps.repo.mutate('advance-noop', (ledger) => {
          const r2 = ledger.requirements.find((r) => r.id === requirementId)
          if (r2 === undefined) return undefined
          const adv = (r2.advance ??= {})
          adv.noopStreak = streak
          return { requirements: [r2] }
        })
        steps.push(stepOf('PAUSE', 'noop', fmt('无可推进事件（第 {n} 次）', { n: streak }), deps.clock.now(), deps.clock.now()))
        stopped = 'noop'
        break
      }

      const startedAt = deps.clock.now()
      const step = await runSelection(deps, requirementId, sel, startedAt, exec, runSignal)
      steps.push(step)
      await appendHistory(deps, requirementId, {
        at: deps.clock.now(),
        requirementId,
        event: step.event,
        ...(step.parentId !== undefined ? { parentId: step.parentId } : {}),
        ...(step.subtaskId !== undefined ? { subtaskId: step.subtaskId } : {}),
        outcome: step.outcome,
        durationMs: step.durationMs,
        detail: step.detail,
      })
      if (step.outcome === 'ok') {
        await deps.repo.mutate('advance-progress', (ledger) => {
          const r2 = ledger.requirements.find((r) => r.id === requirementId)
          if (r2 === undefined) return undefined
          const adv = (r2.advance ??= {})
          if (adv.noopStreak === undefined || adv.noopStreak === 0) return undefined
          adv.noopStreak = 0
          return { requirements: [r2] }
        })
      }
      if (step.event === 'PAUSE') { stopped = 'paused'; break }
      if (step.event === 'ROLLUP') { stopped = 'rollup'; break }
      if (step.outcome === 'failed') {
        const failure = classifyFailure({ ok: false, reason: step.detail })
        if (step.subtaskId !== undefined) {
          const subId = step.subtaskId
          await taskStoreOf(deps).mutate(requirementId, (tasks) => {
            const changed = rollbackSubtask(tasks, subId, deps.clock.now(), deps.ids, failure)
            return changed ? tasks : undefined
          })
        }
        // 瞬断类（abort 族）在同一 job 内自动重试一次（REQ-260928185112-e20d Phase2）：
        // 判据看**退回后的 attempt**（首次失败 → attempt=1），故最多重试一次；
        // 其余失败（凭证门/空产出/引擎缺失）行为不变：停下 + 告警 + 请人处置。
        if (step.subtaskId !== undefined && isTransientAbort(step.detail)) {
          const afterAttempt = (await taskStoreOf(deps).get(step.subtaskId))?.attempt ?? 2
          if (afterAttempt <= 1) {
            const retryAt = deps.clock.now()
            await appendHistory(deps, requirementId, {
              at: retryAt, requirementId, event: 'RETRY', outcome: 'skipped', durationMs: 0,
              subtaskId: step.subtaskId, parentId: step.parentId,
              detail: fmt('子卡 {id} 瞬断，同一 job 内自动重试一次（{why}）', { id: step.subtaskId, why: step.detail.slice(0, 120) }),
            })
            steps.push(stepOf('RETRY', 'skipped', step.detail, retryAt, retryAt, { subtaskId: step.subtaskId, parentId: step.parentId }))
            continue
          }
        }
        await pauseRequirement(deps, requirementId, 'fail', step.detail)
        steps.push(stepOf('PAUSE', 'skipped', step.detail, deps.clock.now(), deps.clock.now()))
        try {
          deps.alert?.alert({
            requirementId,
            title: fmt('【实施链暂停】{req}', { req: requirementId }),
            content: fmt(
              '卡住位置：父卡 {parent} / 子卡 {sub}\n失败原因：[{category}] {detail}\n已做处理：子卡退回待办、autoRun 已置 false、链停在实施态未进验收\n可选处置：重跑该卡 / 退回上游重新描述需求 / 取消',
              { parent: step.parentId ?? '-', sub: step.subtaskId ?? '-', category: failure.category, detail: failure.reason },
            ),
          })
        } catch { /* 告警失败不阻断暂停语义 */ }
        stopped = 'paused'
        break
      }
    }
  } finally {
    try {
      await deps.repo.mutate('advance-unlock', (ledger) => {
        const req = ledger.requirements.find((r) => r.id === requirementId)
        if (req?.advance === undefined) return undefined
        // 未认领过（同步兼容路径）→ 不写盘，避免无意义地推高 revision。
        if (req.advance.lockAt === undefined && req.advance.runId === undefined) return undefined
        req.advance.lockAt = undefined
        req.advance.runId = undefined
        return { requirements: [req] }
      })
    } catch { /* 解锁失败由 stale 接管 */ }
    inflight.delete(requirementId)
  }

  return { steps, stopped }
}

/**
 * 投递需求实施链（REQ-260925110957-552d FR-1）：认领 + 注册后台任务 + 立即返回。
 *
 * 改造前：同步循环 20 步（占用调用方预算）。改造后：投递即返回（链在后台 ctx.jobs 中执行）。
 *
 * 兼容路径（REQ-260927100007-b8ba t-8bce7d）：**无后台任务端口**（内存测试 / 嵌入调用）时
 * 同步跑完并返回真实停止原因——此前这类调用方只会拿到一个 `not_found` 空壳，
 * 链明明可跑却被判"系统不可用"（advance-chain / concurrency-limits 一族测试由此长红）。
 */
export async function advanceRequirement(deps: UseCaseDeps, requirementId: string, exec?: unknown): Promise<AdvanceOutcome> {
  // 1. 前置校验：单飞锁 + 需求态
  // 失败要响亮（2026-09-28 实测）：**每条早退路径**都必须给出 dispatched:false + 人话 reason。
  // 此前早退不设 dispatched，工具壳的 `out.dispatched === false` 判断漏过它们，于是走成功回执、
  // 带上 job_id/run_id=undefined 返回——undefined 不是 lossless JSON，dsh-tools 的
  // snapshotJsonValue 直接抛 ["value is not lossless JSON"]，agent 只拿到无信息的硬错误、只能猜。
  if (inflight.has(requirementId)) {
    return {
      requirementId, steps: [], stopped: 'locked', dispatched: false,
      reason: '该需求已有推进事件在本进程内运行（in-flight），本次未投递新任务；请等待当前 run 结束或稍后重试',
    }
  }

  const snapshot0 = deps.repo.snapshot()
  const req0 = snapshot0.requirements.find((r) => r.id === requirementId)
  if (req0 === undefined) {
    return {
      requirementId, steps: [], stopped: 'not_found', dispatched: false,
      reason: fmt('需求 {id} 不存在，无法推进', { id: requirementId }),
    }
  }
  if (req0.autoRun !== true) {
    return {
      requirementId, steps: [], stopped: 'not_autorun', dispatched: false,
      reason: '自动链未开启（autoRun=false）——请人工确认后再触发 reqboard_task_run 续跑',
    }
  }
  if (TERMINAL_REQ.has(req0.status)) {
    return {
      requirementId, steps: [], stopped: 'terminal', dispatched: false,
      reason: fmt('需求已到终态（status={status}），无需再推进', { status: req0.status }),
    }
  }

  const now0 = deps.clock.now()
  if (req0.advance?.lockAt !== undefined && now0 - req0.advance.lockAt < LIMITS.advanceLockStaleMs) {
    return {
      requirementId, steps: [], stopped: 'locked', dispatched: false,
      reason: fmt('该需求已有 run 在跑（runId={runId}，锁未过期），本次未投递；请等待其结束或稍后重试', {
        runId: req0.advance.runId ?? '(未知)',
      }),
    }
  }

  // 2. 残留锁回收（2026-09-28 实测死锁）：走到这里说明 lockAt 缺省或已过期 ⇒ 没有活 job 在跑。
  //    driveChain 正常收尾会清 lockAt/runId，但**进程被杀/重启时 finally 不执行**，
  //    advance.runId 会永久留下；旧逻辑只看「runId 是否存在」就判「已有 run 在跑」，
  //    于是该需求此后**再也无法投递**（实测：quick_restart 后恒返回 REQBOARD_ADVANCE_LOCKED，
  //    连启动恢复扫描 scanAndResume 也被同一判断挡下——"崩溃不丢链"的承诺因此失效）。
  //    锁已过期即视为残留：显式回收后继续投递（无残留时不写盘，保持幂等）。
  if (req0.advance?.runId !== undefined) {
    await deps.repo.mutate('advance-stale-reclaim', (ledger) => {
      const req = ledger.requirements.find((r) => r.id === requirementId)
      if (req?.advance === undefined) return undefined
      if (req.advance.runId === undefined && req.advance.lockAt === undefined) return undefined
      req.advance.lockAt = undefined
      req.advance.runId = undefined
      return { requirements: [req] }
    })
  }

  // 3. 无后台任务端口 → 同步兼容路径（驱动逻辑与投递路径共用 driveChain）
  if (deps.jobs === undefined || !deps.jobs.available()) {
    const { steps, stopped } = await driveChain(deps, requirementId, exec, () => false)
    return {
      requirementId, steps, stopped, dispatched: false,
      reason: fmt('无后台任务端口：已同步推进并停于 stopped={s}', { s: stopped }),
    }
  }

  // 4. 生成 runId 并认领
  const runId = `run-${deps.clock.now()}-${Math.random().toString(36).slice(2, 9)}`

  await deps.repo.mutate('advance-claim', (ledger) => {
    const req = ledger.requirements.find((r) => r.id === requirementId)
    if (req === undefined) return undefined
    const adv = (req.advance ??= {})
    adv.lockAt = now0
    adv.runId = runId
    return { requirements: [req] }
  })

  // 5. 投递后台任务
  let jobId: string
  try {
    jobId = await deps.jobs.start({
      kind: 'reqboard',
      label: `REQ ${requirementId}`,
      owner: (exec as { agent?: unknown })?.agent,
      run: async (signal?: AbortSignal) => {
        // Phase2：job 的 signal 一路透传到子卡 run —— 取消权归工作单元（job），
        // 而不是派发它的那个 turn（turn 结束不再掐掉正在跑的子卡）。
        await driveChain(deps, requirementId, exec, () => signal?.aborted ?? false, signal ?? undefined)
      },
    })
  } catch (err) {
    // ctx.jobs.start 抛错 = 前置校验失败
    return {
      requirementId,
      steps: [],
      stopped: 'not_found' as AdvanceStop,
      dispatched: false,
      reason: `投递失败：${(err as Error).message}`,
    }
  }

  // 6. 成功：立即返回
  return {
    requirementId,
    steps: [],
    stopped: 'noop' as AdvanceStop,
    dispatched: true,
    job_id: jobId,
    run_id: runId,
  }
}

/** 
 * 启动恢复扫描（崩溃不丢链）：autoRun=true 且未到验收态的需求 → 续跑下一个事件。
 * 
 * REQ-260925110957-552d：补充 exec 参数透传给 advanceRequirement（解决 parent undefined 问题）。
 */
export async function scanAndResume(deps: UseCaseDeps, exec?: unknown): Promise<AdvanceOutcome[]> {
  const snapshot = deps.repo.snapshot()
  const candidates = snapshot.requirements.filter(
    (r: RequirementRecord) => r.autoRun === true && !TERMINAL_REQ.has(r.status),
  )
  const out: AdvanceOutcome[] = []
  for (const req of candidates) {
    out.push(await advanceRequirement(deps, req.id, exec))
  }
  return out
}

/** 供测试/诊断：当前在跑的需求（进程内单飞视图）。 */
export function inflightRequirements(): string[] {
  return [...inflight]
}

/**
 * 需求进度口径（FR-12 看板进度）：父卡 done/总、子卡 done/总。
 *
 * 入参改名为 `view`（REQ-260927202051-f6df t12）：任务已不在台账，这里收的是**队列任务视图**
 * `{ tasks }`。改名同时消除 TC-8.12 静态门禁对"台账取任务"字样的误报——语义上也更诚实。
 */
export function progressOf(
  view: { tasks: readonly TaskRecord[] },
  requirementId: string,
): { parentsDone: number; parentsTotal: number; subtasksDone: number; subtasksTotal: number } {
  const parents = view.tasks.filter((t) => t.requirementId === requirementId && t.parentId === undefined && t.status !== 'canceled')
  const subs = view.tasks.filter((t) => t.requirementId === requirementId && t.parentId !== undefined && t.status !== 'canceled')
  return {
    parentsDone: parents.filter((p) => p.status === 'done').length,
    parentsTotal: parents.length,
    subtasksDone: subs.filter((s) => s.status === 'done').length,
    subtasksTotal: subs.length,
  }
}
