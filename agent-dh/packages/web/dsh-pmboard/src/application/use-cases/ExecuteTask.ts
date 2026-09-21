/**
 * ExecuteTask 用例（REQ-4842fe t5 / FR-6）——**单张子卡的完整闭环**：
 *   子卡 in_progress（开执行记录）→ 一次 workflow run → 由产出生成子卡 report →
 *   子卡凭证门（三项 + 构建新鲜度）→ 子卡 done。
 *
 * 为什么单点在这里：叶子（干活）在 workflow 引擎的子代理里，枝干（状态/凭证/台账）
 * 必须留在宿主侧——脚本内无 ctx、读不到台账，任何"让脚本改状态"的设想都会炸
 * （design/workflow-engine-contract §4）。
 *
 * @module dsh-pmboard/application/use-cases/ExecuteTask
 */
import type { UseCaseDeps, WorkflowRunOutcome } from '../ports.js'
import { fmt } from '../../domain/text/fmt.js'
import { stageLabel } from '../../domain/task/SubtaskTemplate.js'
import { generateSubtaskScript } from '../internal/workflow-script.js'
import { assertDoneEvidence } from '../internal/support.js'
import { detectCrossCardOverwrite } from '../internal/cross-card.js'
import { isSubtask, recordStatus, type TaskRecord } from '../../shared/protocol.js'

/** 子代理产出的结构化摘要（filesChanged / 完成项 / 证据）。 */
export interface SubtaskOutput {
  filesChanged: string[]
  completed: string[]
  evidence: string[]
  raw: string
}

function asStringArray(v: unknown): string[] {
  if (!Array.isArray(v)) return []
  return v.filter((x): x is string => typeof x === 'string').map((s) => s.trim()).filter((s) => s.length > 0).slice(0, 50)
}

/**
 * 解析子代理产出：优先按 JSON 对象读（脚本约定的产出形状）；文本则尝试 JSON.parse；
 * 都不是时把原文当一条完成项（filesChanged 为空 → 凭证门会因此拦下，**不猜文件**）。
 */
export function parseSubtaskOutput(output: unknown): SubtaskOutput {
  let obj: unknown = output
  if (typeof output === 'string') {
    try { obj = JSON.parse(output) } catch { obj = undefined }
  }
  if (typeof obj === 'object' && obj !== null && !Array.isArray(obj)) {
    const o = obj as Record<string, unknown>
    return {
      filesChanged: asStringArray(o.filesChanged),
      completed: asStringArray(o.completed ?? o.done),
      evidence: asStringArray(o.evidence),
      raw: typeof output === 'string' ? output : JSON.stringify(output),
    }
  }
  const raw = typeof output === 'string' ? output : output === undefined || output === null ? '' : JSON.stringify(output)
  const trimmed = raw.trim()
  return { filesChanged: [], completed: trimmed.length > 0 ? [trimmed.slice(0, 200)] : [], evidence: [], raw: trimmed }
}

/** 产出是否"非空"（null/undefined/空串/空对象/空数组都算空）。 */
export function isNonEmptyValue(v: unknown): boolean {
  if (v === null || v === undefined) return false
  if (typeof v === 'string') return v.trim().length > 0
  if (Array.isArray(v)) return v.length > 0
  if (typeof v === 'object') return Object.keys(v as Record<string, unknown>).length > 0
  return true
}

/** 子卡提示词：含父卡实施方案 + 本卡验收标准 + 产出 JSON 约定。 */
export function buildSubtaskPrompt(parent: TaskRecord, subtask: TaskRecord, label: string): string {
  return `你是实施子代理，只完成这一张子卡的工作，做完即止（不要扩大范围）。

【父卡】${parent.title}
【本卡阶段】${String(subtask.stageKind ?? '')}（${label}）
【本卡验收标准（怎么算做完）】
${subtask.acceptance}

【父卡实施方案（上下文）】
${parent.implementation ?? '（父卡未写实施方案）'}

【父卡需求背景】
${parent.context || '（无）'}

【产出要求】完成后**只输出一个 JSON 对象**，不要额外解释：
{"filesChanged":["相对工作区路径", ...],"completed":["完成项", ...],"evidence":["命令与输出摘要", ...]}`
}

export interface ExecuteSubtaskInput {
  subtaskId: string
  /** 执行窗口码（system 驱动可传 'system'）。 */
  windowKey: string
  /** 调用者（透传给引擎作 parent 归属）。 */
  exec?: unknown
}

export interface ExecuteSubtaskResult {
  ok: boolean
  subtaskId: string
  parentId?: string
  stageKind?: string
  filesChanged?: string[]
  reason?: string
  code?: string
}

function fail(subtaskId: string, reason: string, code: string, extra: Partial<ExecuteSubtaskResult> = {}): ExecuteSubtaskResult {
  return { ok: false, subtaskId, reason, code, ...extra }
}

/**
 * 执行一张子卡（幂等：已 done 直接返回；已在 in_progress 不重复开执行记录）。
 * 失败**不改子卡状态**（退回 todo + attempt+1 属 t8 失败语义，由事件链决定）。
 */
export async function executeSubtask(deps: UseCaseDeps, input: ExecuteSubtaskInput): Promise<ExecuteSubtaskResult> {
  const snap = deps.repo.snapshot()
  const task = snap.tasks.find((t) => t.id === input.subtaskId)
  if (task === undefined) return fail(input.subtaskId, fmt('子卡不存在：{id}', { id: input.subtaskId }), 'REQBOARD_TASK_NOT_FOUND')
  if (!isSubtask(task)) return fail(task.id, fmt('{id} 不是子卡（无 parentId）', { id: task.id }), 'REQBOARD_NOT_SUBTASK')
  const parent = snap.tasks.find((t) => t.id === task.parentId)
  if (parent === undefined) {
    return fail(task.id, fmt('子卡 {id} 的父卡 {p} 不存在', { id: task.id, p: String(task.parentId) }), 'REQBOARD_SUBTASK_GATE')
  }
  const base = { subtaskId: task.id, parentId: parent.id, stageKind: task.stageKind }
  if (task.status === 'done') return { ok: true, ...base, filesChanged: task.lastReport?.filesChanged ?? [], reason: 'already_done' }
  if (task.status === 'canceled') return fail(task.id, '子卡已取消', 'REQBOARD_SUBTASK_GATE', base)

  const actor = { kind: 'system' as const }
  const claimAt = deps.clock.now()
  await deps.repo.mutate('subtask-started', (ledger) => {
    const t = ledger.tasks.find((x) => x.id === task.id)
    if (t === undefined) return undefined
    if (t.status === 'done' || t.status === 'in_progress') return undefined
    t.status = 'in_progress'
    t.version += 1
    t.updatedAt = claimAt
    t.updatedBy = actor
    t.claimedAt = claimAt
    t.claimedBy = input.windowKey
    t.executions.push({ id: deps.ids.execution(), sessionId: input.windowKey, trigger: 'auto', startedAt: claimAt, outcome: 'running' })
    recordStatus(t, 'in_progress', claimAt, actor)
    return { tasks: [t] }
  })

  const label = stageLabel(task.stageKind as never)
  let script: string
  try {
    script = generateSubtaskScript({
      stageKind: String(task.stageKind ?? ''),
      stageLabel: label,
      prompt: buildSubtaskPrompt(parent, task, label),
    })
  } catch (err) {
    return fail(task.id, (err as Error).message, (err as { code?: string }).code ?? 'workflow_script_contract', base)
  }

  let outcome: WorkflowRunOutcome
  if (deps.workflow === undefined) {
    outcome = { ok: false, reason: 'engine_unavailable' }
  } else {
    try {
      outcome = await deps.workflow.start({
        script,
        meta: { name: 'reqboard-subtask-' + String(task.stageKind ?? 'x'), description: fmt('子卡执行：{title}', { title: task.title }) },
        args: { subtaskId: task.id, parentId: parent.id, stageKind: String(task.stageKind ?? '') },
        parent: (input.exec as { agent?: unknown } | undefined)?.agent,
        signal: (input.exec as { signal?: AbortSignal } | undefined)?.signal,
      })
    } catch (err) {
      outcome = { ok: false, reason: fmt('run 异常：{m}', { m: String((err as Error).message ?? err) }) }
    }
  }

  const outputValue = (outcome.value as { output?: unknown } | undefined)?.output ?? outcome.value
  const parsed = outcome.ok ? parseSubtaskOutput(outputValue) : { filesChanged: [], completed: [], evidence: [], raw: '' }
  const valueNonEmpty = isNonEmptyValue(outputValue)
  const ranAt = deps.clock.now()

  // REQ-4842fe t9/FR-10 次防线：产出文件的 mtime 落在另一张在跑父卡的执行窗口内 → 判跨卡覆盖。
  if (outcome.ok && parsed.filesChanged.length > 0) {
    const conflict = detectCrossCardOverwrite(
      snap.tasks,
      parent.id,
      parsed.filesChanged,
      (f) => deps.docs.stat(f)?.mtimeMs,
      ranAt,
    )
    if (conflict !== undefined) {
      return fail(
        task.id,
        fmt('跨卡覆盖：{file} 的 mtime 落在父卡 {p} 的子卡 {s} 执行窗口内', {
          file: conflict.file,
          p: conflict.otherParentId,
          s: conflict.otherSubtaskId,
        }),
        'REQBOARD_CROSS_CARD',
        base,
      )
    }
  }

  await deps.repo.mutate('subtask-ran', (ledger) => {
    const t = ledger.tasks.find((x) => x.id === task.id)
    if (t === undefined) return undefined
    t.lastRun = { at: ranAt, ok: outcome.ok, stopReason: outcome.ok ? 'completed' : (outcome.reason ?? 'error'), valueNonEmpty, ...(outcome.ok ? {} : { reason: outcome.reason ?? '' }) }
    if (parsed.raw.length > 0 || parsed.filesChanged.length > 0 || parsed.completed.length > 0 || parsed.evidence.length > 0) {
      t.lastReport = {
        at: ranAt,
        reportIndex: (t.lastReport?.reportIndex ?? 0) + 1,
        filesChanged: parsed.filesChanged,
        completed: parsed.completed.length > 0 ? parsed.completed : [parsed.raw.slice(0, 200)],
      }
    }
    t.version += 1
    t.updatedAt = ranAt
    t.updatedBy = actor
    return { tasks: [t] }
  })

  try {
    const doneAt = deps.clock.now()
    await deps.repo.mutate('subtask-completed', (ledger) => {
      const t = ledger.tasks.find((x) => x.id === task.id)
      if (t === undefined) return undefined
      assertDoneEvidence(deps, input.windowKey, t, ledger)
      t.status = 'done'
      t.version += 1
      t.updatedAt = doneAt
      t.updatedBy = actor
      for (const e of t.executions) {
        if (e.outcome === 'running') { e.endedAt = doneAt; e.outcome = 'succeeded' }
      }
      recordStatus(t, 'done', doneAt, actor)
      return { tasks: [t] }
    })
    return { ok: true, ...base, filesChanged: parsed.filesChanged }
  } catch (err) {
    const code = (err as { code?: string }).code ?? 'REQBOARD_SUBTASK_GATE'
    const reason = (err as Error).message ?? String(err)
    const failedAt = deps.clock.now()
    await deps.repo.mutate('subtask-failed', (ledger) => {
      const t = ledger.tasks.find((x) => x.id === task.id)
      if (t === undefined) return undefined
      for (const e of t.executions) {
        if (e.outcome === 'running') { e.endedAt = failedAt; e.outcome = 'failed'; e.error = reason }
      }
      t.version += 1
      t.updatedAt = failedAt
      t.updatedBy = actor
      return { tasks: [t] }
    })
    return fail(task.id, reason, code, base)
  }
}
