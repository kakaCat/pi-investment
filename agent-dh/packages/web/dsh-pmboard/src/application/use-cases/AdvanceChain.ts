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
import { classifyFailure, rollbackSubtask } from '../internal/failure-handling.js'
import {
  recordStatus,
  type AdvanceEvent,
  type AdvanceRecord,
  type RequirementRecord,
  type TaskRecord,
} from '../../shared/protocol.js'

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

async function openParent(deps: UseCaseDeps, requirementId: string, parentId: string, startedAt: number): Promise<AdvanceStep> {
  const now = deps.clock.now()
  let created: TaskRecord[] = []
  const result = await deps.repo.mutate('advance-open-parent', (ledger) => {
    const req = ledger.requirements.find((r) => r.id === requirementId)
    const parent = ledger.tasks.find((t) => t.id === parentId)
    if (req === undefined || parent === undefined || parent.status !== 'todo') return undefined
    const active = ledger.tasks.filter(
      (t) => t.requirementId === requirementId && t.parentId === undefined && t.status === 'in_progress',
    ).length
    if (active >= LIMITS.advanceMaxParallelParents) return undefined
    parent.status = 'in_progress'
    parent.version += 1
    parent.updatedAt = now
    parent.claimedAt = now
    parent.claimedBy = 'system'
    parent.executions.push({ id: deps.ids.execution(), trigger: 'auto', startedAt: now, outcome: 'running' })
    recordStatus(parent, 'in_progress', now, { kind: 'system' })
    created = expandSubtasks(ledger, parent, req, now, deps.ids)
    return { tasks: [parent, ...created] }
  })
  if ((result.changed.tasks ?? []).length === 0) {
    return stepOf('OPEN_PARENT', 'noop', fmt('父卡 {id} 不可开工（已在跑/已达并发上限）', { id: parentId }), startedAt, deps.clock.now(), { parentId })
  }
  return stepOf('OPEN_PARENT', 'ok', fmt('父卡 {id} 自动开工并落子卡 {n} 张', { id: parentId, n: created.length }), startedAt, deps.clock.now(), { parentId })
}

async function finalizeParent(deps: UseCaseDeps, parentId: string, startedAt: number): Promise<AdvanceStep> {
  const now = deps.clock.now()
  try {
    const result = await deps.repo.mutate('advance-finalize-parent', (ledger) => {
      const parent = ledger.tasks.find((t) => t.id === parentId)
      if (parent === undefined || parent.status !== 'in_progress') return undefined
      const subs = subtasksOf({ tasks: ledger.tasks }, parent.id)
      if (subs.length === 0 || !subs.every((s) => s.status === 'done' || s.status === 'canceled')) return undefined
      const files = [...new Set(subs.flatMap((s) => s.lastReport?.filesChanged ?? []))]
      const completed = [...new Set(subs.flatMap((s) => s.lastReport?.completed ?? []))]
      parent.lastReport = {
        at: now,
        reportIndex: (parent.lastReport?.reportIndex ?? 0) + 1,
        filesChanged: files,
        completed: completed.length > 0 ? completed : [fmt('子卡 {n} 张全部完成', { n: subs.length })],
      }
      assertDoneEvidence(deps, 'system', parent, ledger)
      parent.status = 'done'
      parent.version += 1
      parent.updatedAt = now
      parent.updatedBy = { kind: 'system' }
      for (const e of parent.executions) {
        if (e.outcome === 'running') { e.endedAt = now; e.outcome = 'succeeded' }
      }
      recordStatus(parent, 'done', now, { kind: 'system' })
      return { tasks: [parent] }
    })
    if ((result.changed.tasks ?? []).length === 0) {
      return stepOf('FINALIZE_PARENT', 'noop', fmt('父卡 {id} 尚不可收尾', { id: parentId }), startedAt, deps.clock.now(), { parentId })
    }
    return stepOf('FINALIZE_PARENT', 'ok', fmt('父卡 {id} 汇总子卡产出并收尾', { id: parentId }), startedAt, deps.clock.now(), { parentId })
  } catch (err) {
    return stepOf('FINALIZE_PARENT', 'failed', (err as Error).message, startedAt, deps.clock.now(), { parentId })
  }
}

async function runSubtaskStep(deps: UseCaseDeps, parentId: string, subtaskId: string, startedAt: number): Promise<AdvanceStep> {
  const r = await executeSubtask(deps, { subtaskId, windowKey: 'system' })
  return stepOf(
    'RUN_SUBTASK',
    r.ok ? 'ok' : 'failed',
    r.ok ? fmt('子卡 {id} 执行完成', { id: subtaskId }) : (r.reason ?? '执行失败'),
    startedAt,
    deps.clock.now(),
    { parentId, subtaskId },
  )
}

async function rollupStep(deps: UseCaseDeps, requirementId: string, startedAt: number): Promise<AdvanceStep> {
  const now = deps.clock.now()
  const result = await deps.repo.mutate('advance-rollup', (ledger) => {
    const advanced = applyTaskRollup(ledger, { now, commentId: () => deps.ids.comment() }, requirementId)
    return advanced.length > 0 ? { requirements: advanced } : undefined
  })
  const ok = (result.changed.requirements ?? []).length > 0
  return stepOf('ROLLUP', ok ? 'ok' : 'noop', ok ? '需求已全部任务完成，滚进验收' : '暂不可 rollup', startedAt, deps.clock.now())
}

async function runSelection(deps: UseCaseDeps, requirementId: string, sel: AdvanceSelection, startedAt: number): Promise<AdvanceStep> {
  if (sel.event === 'OPEN_PARENT' && sel.parentId !== undefined) return openParent(deps, requirementId, sel.parentId, startedAt)
  if (sel.event === 'FINALIZE_PARENT' && sel.parentId !== undefined) return finalizeParent(deps, sel.parentId, startedAt)
  if (sel.event === 'RUN_SUBTASK' && sel.subtaskId !== undefined) return runSubtaskStep(deps, sel.parentId ?? '', sel.subtaskId, startedAt)
  if (sel.event === 'ROLLUP') return rollupStep(deps, requirementId, startedAt)
  return stepOf('PAUSE', 'skipped', '无对应事件实现', startedAt, deps.clock.now())
}

/**
 * 推进一个需求：循环执行事件直到 ROLLUP / PAUSE / 无事可做 / 步数上限。
 * 重复调用安全（幂等）：已完成的步不会重做。
 */
export async function advanceRequirement(deps: UseCaseDeps, requirementId: string): Promise<AdvanceOutcome> {
  if (inflight.has(requirementId)) return { requirementId, steps: [], stopped: 'locked' }
  const snapshot0 = deps.repo.snapshot()
  const req0 = snapshot0.requirements.find((r) => r.id === requirementId)
  if (req0 === undefined) return { requirementId, steps: [], stopped: 'not_found' }
  if (req0.autoRun !== true) return { requirementId, steps: [], stopped: 'not_autorun' }
  if (TERMINAL_REQ.has(req0.status)) return { requirementId, steps: [], stopped: 'terminal' }
  const now0 = deps.clock.now()
  if (req0.advance?.lockAt !== undefined && now0 - req0.advance.lockAt < LIMITS.advanceLockStaleMs) {
    return { requirementId, steps: [], stopped: 'locked' }
  }

  inflight.add(requirementId)
  const steps: AdvanceStep[] = []
  let stopped: AdvanceStop = 'max_steps'
  try {
    // 单飞锁（台账侧）：只在真要跑事件时写；纯终态 noop 不落盘（重复触发 revision 不变）。
    await deps.repo.mutate('advance-lock', (ledger) => {
      const req = ledger.requirements.find((r) => r.id === requirementId)
      if (req === undefined) return undefined
      const adv = (req.advance ??= {})
      adv.lockAt = now0
      return { requirements: [req] }
    })

    for (let i = 0; i < LIMITS.advanceMaxStepsPerCall; i += 1) {
      const snap = deps.repo.snapshot()
      const req = snap.requirements.find((r) => r.id === requirementId)
      if (req === undefined) { stopped = 'not_found'; break }
      if (req.autoRun !== true) { stopped = 'not_autorun'; break }
      if (TERMINAL_REQ.has(req.status)) { stopped = 'terminal'; break }

      const sel = selectAdvanceEvent({ tasks: snap.tasks }, requirementId, LIMITS.advanceMaxParallelParents)
      if (sel === undefined) {
        if (!hasOpenWork({ tasks: snap.tasks }, requirementId)) { stopped = 'noop'; break }
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
      const step = await runSelection(deps, requirementId, sel, startedAt)
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
        // REQ-4842fe t8/FR-7：失败**不自动重试**——子卡退回 todo + attempt+1 + revisions(rollback)
        // + 失败评论；随后暂停自动链并发出高优告警，等人三选处置。
        const failure = classifyFailure({ ok: false, reason: step.detail })
        if (step.subtaskId !== undefined) {
          const subId = step.subtaskId
          await deps.repo.mutate('subtask-rollback', (ledger) => {
            const changed = rollbackSubtask(ledger, subId, deps.clock.now(), deps.ids, failure)
            if (!changed) return undefined
            const t = ledger.tasks.find((x) => x.id === subId)
            return t === undefined ? undefined : { tasks: [t] }
          })
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
        req.advance.lockAt = undefined
        return { requirements: [req] }
      })
    } catch { /* 解锁失败由 stale 接管 */ }
    inflight.delete(requirementId)
  }
  return { requirementId, steps, stopped }
}

/** 启动恢复扫描（崩溃不丢链）：autoRun=true 且未到验收态的需求 → 续跑下一个事件。 */
export async function scanAndResume(deps: UseCaseDeps): Promise<AdvanceOutcome[]> {
  const snapshot = deps.repo.snapshot()
  const candidates = snapshot.requirements.filter(
    (r: RequirementRecord) => r.autoRun === true && !TERMINAL_REQ.has(r.status),
  )
  const out: AdvanceOutcome[] = []
  for (const req of candidates) {
    out.push(await advanceRequirement(deps, req.id))
  }
  return out
}

/** 供测试/诊断：当前在跑的需求（进程内单飞视图）。 */
export function inflightRequirements(): string[] {
  return [...inflight]
}

/** 需求进度口径（FR-12 看板进度）：父卡 done/总、子卡 done/总。 */
export function progressOf(
  ledger: { tasks: readonly TaskRecord[] },
  requirementId: string,
): { parentsDone: number; parentsTotal: number; subtasksDone: number; subtasksTotal: number } {
  const parents = ledger.tasks.filter((t) => t.requirementId === requirementId && t.parentId === undefined && t.status !== 'canceled')
  const subs = ledger.tasks.filter((t) => t.requirementId === requirementId && t.parentId !== undefined && t.status !== 'canceled')
  return {
    parentsDone: parents.filter((p) => p.status === 'done').length,
    parentsTotal: parents.length,
    subtasksDone: subs.filter((s) => s.status === 'done').length,
    subtasksTotal: subs.length,
  }
}
