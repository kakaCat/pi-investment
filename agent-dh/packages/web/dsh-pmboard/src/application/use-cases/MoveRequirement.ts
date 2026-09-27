/**
 * MoveRequirement 用例（REQ-260927100007-b8ba FR-7 + FR-3）——agent 侧需求阶段推进。
 *
 * 语义与看板移动 HTTP 路由逐条对齐（先产物闸门、后状态机；预检 + mutate 内复查防并发），
 * 额外加 FR-3 的任务完整性守卫。**五道人工门 agent 一律不可越过**——由 assertReqTransition
 * 在收敛点（transitionRequirement）内抛 human_gate，本用例不做任何绕过。
 *
 * @module dsh-pmboard/application/use-cases/MoveRequirement
 */
import type { UseCaseDeps } from '../ports.js'
import { asReqStatus, normalizeText } from '../../shared/protocol.js'
import { assertArtifactGates } from '../internal/artifact-gates.js'
import { openRequirementsFor } from '../internal/window.js'
import { taskCompletenessGap } from '../internal/task-completeness.js'
import { captureSnapshot, transitionRequirement } from '../internal/token-usage.js'
import { reject, agentIdFromExec, requireLiveDriver, mapAgentError } from '../internal/support.js'
import { fmt } from '../../domain/text/fmt.js'
import { taskStoreOf } from './queue-access.js'

export async function executeMoveRequirement(deps: UseCaseDeps, args: unknown, exec: unknown): Promise<unknown> {
  const windowKey = agentIdFromExec(deps, exec)
  requireLiveDriver(deps, exec)
  const a = (args ?? {}) as { requirement_id?: unknown; to?: unknown; reason?: unknown }
  const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
  const to = asReqStatus(a.to)
  const reason = normalizeText(a.reason, 'reason', 500)

  const snap = deps.repo.snapshot()
  const bound = openRequirementsFor(snap, windowKey)
  if (bound.length === 0) reject('reqboard_move 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
  const req0 = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
  if (req0 === undefined) {
    reject(fmt('reqboard_move 未执行：需求 {id} 不是本窗口绑定的进行中需求', { id: explicitId }), 'REQBOARD_NOT_BOUND_TO_WINDOW')
  }
  const from = req0.status

  // 任务已迁出台账（v9）：完整性判据的任务集从 TaskStore 取一次，预检与 mutate 内复查共用同一份
  // 快照（mutate 回调是同步契约，不能在回调里 await；并发漂移由需求侧 from 复查兜底）。
  const store = taskStoreOf(deps)
  const reqTasks = await store.listByRequirement(req0.id)

  // 只读预检（拒绝次序与会话侧一致：先产物闸门，后任务完整性）
  const preGate = assertArtifactGates(req0, from, to)
  if (preGate !== undefined) reject(fmt('reqboard_move 未执行：{msg}', { msg: preGate.message }), preGate.code)
  const preGap = taskCompletenessGap(req0, reqTasks, to)
  if (preGap !== undefined) reject(fmt('reqboard_move 未执行：{msg}', { msg: preGap }), 'REQBOARD_TASK_INCOMPLETE')

  const actor = { kind: 'agent' as const, sessionId: windowKey }
  // 用例边界：domain 状态机抛 human_gate，agent 工具的传输码是 REQBOARD_HUMAN_GATE（FR-7 契约）。
  const result = await deps.repo.mutate('requirement-moved', (ledger) => {
    const req = ledger.requirements.find(r => r.id === req0.id)
    if (req === undefined || req.status !== from) return undefined
    // mutate 内复查（防并发漂移）
    const gate = assertArtifactGates(req, req.status, to)
    if (gate !== undefined) throw Object.assign(new Error(gate.message), { code: gate.code })
    const gap = taskCompletenessGap(req, reqTasks, to)
    if (gap !== undefined) throw Object.assign(new Error(gap), { code: 'REQBOARD_TASK_INCOMPLETE' })
    const at = deps.clock.now()
    // 收敛点：human_gate / invalid_transition / system_gate 在此抛错 → mutate 回滚，状态不变
    transitionRequirement(req, to, {
      at,
      actor,
      ...(reason.length > 0 ? { reason } : {}),
      snap: captureSnapshot(deps, windowKey),
    })
    req.comments.push({
      id: deps.ids.comment(),
      body: fmt('[状态] {from} → {to}（reqboard_move{why}）', { from, to, why: reason.length > 0 ? '：' + reason : '' }),
      createdAt: at,
      createdBy: actor,
    })
    return { requirements: [req] }
  }).catch(mapAgentError)
  const changed = (result.changed.requirements ?? [])[0]
  return { success: true, requirement_id: req0.id, from, to, status: changed?.status ?? to }
}
