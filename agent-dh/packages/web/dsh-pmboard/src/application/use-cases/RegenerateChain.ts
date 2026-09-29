/**
 * RegenerateChain 用例（卡片层契约 2026-09-28）——子卡链**再生成（补链）** + 只读诊断。
 *
 * 为什么需要：父卡的子卡链只在「开工那一次」由 expandSubtasks 懒展开（MoveTask.ts:148 被 req.autoRun
 * 门住，AdvanceChain 只服务自动链），且**有子卡即整体跳过**（幂等）⇒ 卡一旦"开工了却没有链"
 * （历史非自动链需求 / 链只落了一半 / autoRun 事后才打开）就永远没有第二次机会。本用例补这条写路径。
 *
 * 纪律：
 *  - dry_run 默认 true（安全默认在 execute 内显式兜底，不靠 schema default——本仓铁律）；
 *  - 真写必须同时给 task_id 与 reason（不做批量写：避免一次性给几百张存量卡生链）；
 *  - solo 卡（stages: []）**跳过并回执说明**，不静默跳过；
 *  - 只补缺失阶段，已有子卡（含 done）一律不动；补链在父卡 comment 留痕。
 *
 * @module dsh-pmboard/application/use-cases/RegenerateChain
 */
import type { UseCaseDeps } from '../ports.js'
import { normalizeText } from '../../shared/protocol.js'
import { fmt } from '../../domain/text/fmt.js'
import { chainDiagnosis, regenerateChain } from '../internal/lazy-expand.js'
import { openRequirementsFor } from '../internal/window.js'
import { reject, agentIdFromExec, requireLiveDriver, mapAgentError } from '../internal/support.js'
import { taskStoreOf } from './queue-access.js'

/** 单张卡的链体检结果（回执形状，与工具 schema 对齐）。 */
interface ChainCandidate {
  task_id: string
  title: string
  status: string
  chain_status: string
  expected: string[]
  existing: string[]
  missing: string[]
  created: string[]
  note?: string
}

export async function executeRegenerateChain(deps: UseCaseDeps, args: unknown, exec: unknown): Promise<unknown> {
  const windowKey = agentIdFromExec(deps, exec)
  requireLiveDriver(deps, exec)
  const a = (args ?? {}) as { task_id?: unknown; requirement_id?: unknown; dry_run?: unknown; reason?: unknown }
  const taskId = normalizeText(a.task_id, 'task_id', 64)
  const reqIdArg = normalizeText(a.requirement_id, 'requirement_id', 64)
  const reason = normalizeText(a.reason, 'reason', 500)
  // 安全默认：缺省与显式 true 都判只读；只有显式 false 才写（dsh-tools 不注入 schema default）。
  const dryRun = a.dry_run !== false
  if (!dryRun && reason.length === 0) {
    reject('reqboard_task_regenerate 未执行：dry_run:false（真补链）必须传 reason——写台账要留痕', 'REQBOARD_INVALID_INPUT')
  }
  if (!dryRun && taskId.length === 0) {
    reject('reqboard_task_regenerate 未执行：真补链必须指定 task_id（不提供批量写路径）', 'REQBOARD_INVALID_INPUT')
  }
  const snap = deps.repo.snapshot()
  const bound = openRequirementsFor(snap, windowKey)
  if (bound.length === 0) reject('reqboard_task_regenerate 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
  const store = taskStoreOf(deps)

  // 目标需求：显式 requirement_id → 由 task_id 反查 → 绑定需求里的第一个。
  let reqId = reqIdArg
  if (reqId.length === 0 && taskId.length > 0) {
    const t = await store.get(taskId)
    if (t === undefined) reject(fmt('reqboard_task_regenerate 未执行：任务 {id} 不存在', { id: taskId }), 'REQBOARD_TASK_NOT_FOUND')
    reqId = t.requirementId
  }
  if (reqId.length === 0) reqId = bound[0].id
  if (!bound.some((r) => r.id === reqId)) {
    reject(fmt('reqboard_task_regenerate 未执行：需求 {id} 不属于本窗口绑定的需求（只能动自己的卡）', { id: reqId }), 'REQBOARD_NOT_BOUND_TO_WINDOW')
  }
  const req = snap.requirements.find((r) => r.id === reqId)
  const tasks0 = await store.listByRequirement(reqId)
  const tops = tasks0
    .filter((t) => t.parentId === undefined)
    .filter((t) => taskId.length === 0 || t.id === taskId)

  const candidates: ChainCandidate[] = tops.map((t) => {
    const d = chainDiagnosis(tasks0, t, req)
    const status = d.solo
      ? 'solo'
      : d.existing.length === 0 ? 'missing' : (d.missing.length > 0 ? 'partial' : 'complete')
    const applicable = t.status === 'todo' || t.status === 'in_progress'
    const notes: string[] = []
    if (d.solo) notes.push('该卡显式声明 stages: []（solo），本就不落链——跳过，不是缺陷')
    if (status === 'complete') notes.push('链完整，无需再生成')
    if (!applicable) notes.push(fmt('卡状态 {s} 不在 todo/in_progress：done/取消的卡不追溯生链', { s: t.status }))
    return {
      task_id: t.id,
      title: t.title,
      status: t.status,
      chain_status: status,
      expected: d.expected,
      existing: d.existing,
      missing: d.missing,
      created: [],
      ...(notes.length > 0 ? { note: notes.join('；') } : {}),
    }
  })

  let createdTotal = 0
  let applied = false
  if (!dryRun) {
    const createdIds: string[] = []
    await store.mutate(reqId, (tasks) => {
      const parent = tasks.find((t) => t.id === taskId)
      if (parent === undefined) return undefined
      const at = deps.clock.now()
      const actor = { kind: 'agent' as const, sessionId: windowKey }
      const created = regenerateChain(tasks, parent, req, at, deps.ids)
      if (created.length > 0) {
        tasks.push(...created.map((c) => ({ ...c, layer: 0 })))
        for (const c of created) createdIds.push(c.id)
      }
      // 留痕：补链是写台账的动作，父卡必须有可回溯记录（含原因与新建 id）。
      parent.comments.push({
        id: deps.ids.comment(),
        body: fmt('[再生成] 补子卡 {n} 张（{ids}）：{why}（reqboard_task_regenerate）', {
          n: created.length, ids: createdIds.join('、') || '-', why: reason,
        }),
        createdAt: at,
        createdBy: actor,
      })
      return tasks
    }).catch(mapAgentError)
    createdTotal = createdIds.length
    applied = createdTotal > 0
    const hit = candidates.find((c) => c.task_id === taskId)
    if (hit !== undefined) hit.created = createdIds
  }

  return {
    success: true,
    requirement_id: reqId,
    dry_run: dryRun,
    applied,
    scanned: tops.length,
    created_total: createdTotal,
    candidates,
  }
}
