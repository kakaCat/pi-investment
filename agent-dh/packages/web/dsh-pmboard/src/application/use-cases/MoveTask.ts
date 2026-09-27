/**
 * MoveTask 用例（REQ-260927100007-b8ba FR-7/FR-8，REQ-4842fe t5/t6 契约）——
 * agent 侧任务流转，语义与看板按钮**逐条对齐**，并补齐自动链需要的四件事：
 *
 *   1. 状态迁移统一走 transitionTask（收敛点），不再直接赋值；
 *   2. 开工返回任务卡全文（task_card.doc_path / implementation）——照卡执行，不凭记忆；
 *   3. 父卡开工**同事务**懒展开子卡链，并受同需求父卡并发上限约束（REQBOARD_PARENT_LIMIT）；
 *   4. 转 done 前过 done 凭证门（父卡收尾门 / 子卡三项证据）。
 *
 * 错误码在用例边界映射：domain 的 human_gate → REQBOARD_HUMAN_GATE（agent 工具传输契约）。
 *
 * @module dsh-pmboard/application/use-cases/MoveTask
 */
import type { UseCaseDeps } from '../ports.js'
import {
  asTaskStatus,
  newExecutionId,
  normalizeText,
  type TaskRecord,
} from '../../shared/protocol.js'
import { endsExecutionSegment, isRollbackOrCancel, startsExecutionSegment } from '../../domain/status/Predicates.js'
import type { TaskRole } from '../../domain/task/TaskStatus.js'
import { LIMITS } from '../../domain/limits.js'
import { openRequirementsFor } from '../internal/window.js'
import { transitionTask } from '../internal/task-transition.js'
import { expandSubtasks } from '../internal/lazy-expand.js'
import { applyTaskRollup } from '../internal/rollup.js'
import { syncRTMYaml } from '../internal/rtm-yaml.js'
import {
  reject,
  agentIdFromExec,
  requireLiveDriver,
  assertDoneEvidence,
  mapAgentError,
} from '../internal/support.js'
import { fmt } from '../../domain/text/fmt.js'

/** 角色判定：子卡（有 parentId）/ 父卡（有子卡）/ 存量卡。 */
function roleOf(task: TaskRecord, tasks: readonly TaskRecord[]): TaskRole {
  if (typeof task.parentId === 'string' && task.parentId.length > 0) return 'subtask'
  return tasks.some(t => t.parentId === task.id) ? 'parent' : 'legacy'
}

/** 同需求当前在跑的父卡（parentId 缺省 = 父卡/存量卡层）。 */
function runningParents(tasks: readonly TaskRecord[], requirementId: string): TaskRecord[] {
  return tasks.filter(t => t.requirementId === requirementId && t.parentId === undefined && t.status === 'in_progress')
}

/** 任务卡文档路径：落库时写死的 cardDoc 优先，缺省按同一口径拼（与 decompose/report 同源）。 */
function taskCardPath(task: TaskRecord): string {
  if (typeof task.cardDoc === 'string' && task.cardDoc.length > 0) return task.cardDoc
  return 'docs/requirements/' + task.requirementId + '/tasks/' + task.id + '.md'
}

export async function executeMoveTask(deps: UseCaseDeps, args: unknown, exec: unknown): Promise<unknown> {
  const windowKey = agentIdFromExec(deps, exec)
  requireLiveDriver(deps, exec)
  const a = (args ?? {}) as { task_id?: unknown; to?: unknown; reason?: unknown }
  const taskId = normalizeText(a.task_id, 'task_id', 64)
  if (taskId.length === 0) reject('reqboard_task_move 未执行：task_id 不能为空', 'REQBOARD_INVALID_INPUT')
  const to = asTaskStatus(a.to)
  const reason = normalizeText(a.reason, 'reason', 500)

  const snap = deps.repo.snapshot()
  const bound = openRequirementsFor(snap, windowKey)
  if (bound.length === 0) reject('reqboard_task_move 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
  const task0 = snap.tasks.find(t => t.id === taskId)
  if (task0 === undefined) reject(fmt('reqboard_task_move 未执行：任务 {id} 不存在', { id: taskId }), 'REQBOARD_TASK_NOT_FOUND')
  if (!bound.some(r => r.id === task0.requirementId)) {
    reject(fmt('reqboard_task_move 未执行：任务 {id} 不属于本窗口绑定的需求（只能动自己的卡）', { id: taskId }), 'REQBOARD_NOT_BOUND_TO_WINDOW')
  }
  const from = task0.status
  const actor = { kind: 'agent' as const, sessionId: windowKey }

  // 闭包内的副产物（单次 mutate 写入，供返回体投影）
  let createdIds: string[] = []
  let card: { doc_path: string; implementation: string } | undefined

  const result = await deps.repo.mutate('task-moved', (ledger) => {
    const task = ledger.tasks.find(t => t.id === taskId)
    if (task === undefined) return undefined
    const at = deps.clock.now()
    const req = ledger.requirements.find(r => r.id === task.requirementId)
    const role = roleOf(task, ledger.tasks)
    const starting = startsExecutionSegment(to)

    // 父卡并发上限（REQ-4842fe §6.1）：非子卡开工时同需求在跑父卡已达上限即拒。
    if (starting && role !== 'subtask') {
      const running = runningParents(ledger.tasks, task.requirementId)
      if (running.length >= LIMITS.advanceMaxParallelParents) {
        reject(
          fmt('reqboard_task_move 未执行：同需求并行父卡已达上限 {n} 张（正在跑：{ids}）——先收尾再开新卡（REQBOARD_PARENT_LIMIT）',
            { n: LIMITS.advanceMaxParallelParents, ids: running.map(t => t.id).join('、') }),
          'REQBOARD_PARENT_LIMIT',
        )
      }
    }

    // done 凭证门：父卡收尾门（INV-5）/ 子卡三项证据 / 汇报前置 / 构建新鲜度。不过即抛错回滚。
    if (to === 'done') assertDoneEvidence(deps, windowKey, task, ledger)

    // 收敛点：非法转移 / 人工门越权在此抛错（抛错 → mutate 回滚，状态不变）
    transitionTask(task, to, { at, actor, ...(reason.length > 0 ? { reason } : {}), role })

    if (starting) {
      task.claimedBy = windowKey
      task.claimedAt = at
      task.executions.push({ id: newExecutionId(), sessionId: windowKey, trigger: 'manual', startedAt: at, outcome: 'running' })
      card = { doc_path: taskCardPath(task), implementation: task.implementation ?? '' }
      // 懒展开（REQ-4842fe FR-3）：父卡开工**同事务**落子卡链；仅自动链需求（autoRun）走这条。
      if (role !== 'subtask' && req?.autoRun === true) {
        createdIds = expandSubtasks(ledger, task, req, at, deps.ids).map(c => c.id)
      }
    }
    if (endsExecutionSegment(to)) {
      delete task.claimedBy
      delete task.claimedAt
    }
    if (!starting) {
      for (const e of task.executions) {
        if (e.outcome === 'running') { e.endedAt = at; e.outcome = isRollbackOrCancel(to) ? 'cancelled' : 'succeeded' }
      }
    }
    if (reason.length > 0) {
      task.comments.push({ id: deps.ids.comment(), body: fmt('[状态] → {to}：{reason}（reqboard_task_move）', { to, reason }), createdAt: at, createdBy: actor })
    }
    const advanced = applyTaskRollup(ledger, { now: at, commentId: () => deps.ids.comment() }, task.requirementId)
    const created = ledger.tasks.filter(t => createdIds.includes(t.id))
    return { tasks: [task, ...created], requirements: advanced }
  }).catch(mapAgentError)

  const moved = (result.changed.tasks ?? []).find(t => t.id === taskId)
  if (moved !== undefined) {
    try { syncRTMYaml(deps, moved.requirementId, 'task:status', { taskId: moved.id }) } catch { /* RTM 是增强层，失败不阻断 */ }
  }
  return {
    success: true,
    task_id: taskId,
    from,
    to,
    status: moved?.status ?? to,
    version: moved?.version,
    ...(createdIds.length > 0 ? { subtasks_created: createdIds } : {}),
    ...(card !== undefined ? { task_card: card } : {}),
  }
}
