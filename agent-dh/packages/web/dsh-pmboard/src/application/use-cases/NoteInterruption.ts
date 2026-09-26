/**
 * NoteInterruption 用例（REQ-260924213231-b1c4 T-9 · serves: FR-6 / I-8）——断点补写。
 *
 * 两个入口共用一个核心：
 *   · B′ 工具入口 `reqboard_note_interruption(reason)`（`noteInterruption`）：窗口绑定校验
 *     + 显式拒绝（reason 空 / 本窗口无绑定需求）；
 *   · B  事件入口（`noteInterruptionForWindow`）：`Dive 会话驱动器`（原 CaptureHook）的 `turn/end` 经组合根
 *     异步边界调用——此时没有 exec、也不该因"窗口无绑定需求"抛错（只静默跳过）。
 *
 * 写入语义（design/interfaces.md I-8）：同一需求只保留一个 `interruption` 对象，
 * 后写覆盖前写；`pendingAction` 由 `nextActionFor` 按当前状态重算（断点/输入包同源）。
 *
 * @module dsh-pmboard/application/use-cases/NoteInterruption
 */
import type { UseCaseDeps } from '../ports.js'
import { normalizeText, type InterruptionRecord } from '../../shared/protocol.js'
import { fmt } from '../../domain/text/fmt.js'
import { openRequirementsFor } from '../internal/window.js'
import { stampInterruption } from '../internal/interruption.js'
import { reject, agentIdFromExec, requireLiveDriver } from '../internal/support.js'

/** 补写结果（工具返回体 / 事件路径内部消费共用）。 */
export interface NoteInterruptionResult {
  requirement_id: string
  interruption: InterruptionRecord
  note: string
}

/**
 * 核心写入（两入口共用）。窗口未绑定需求、或显式 id 不属于本窗口 → `undefined`
 * （由调用方决定是拒绝还是静默跳过）。幂等：内容未变时不重复写评论。
 */
export async function noteInterruptionCore(
  deps: UseCaseDeps,
  windowKey: string,
  reason: string,
  explicitId = '',
  tool?: string,
): Promise<NoteInterruptionResult | undefined> {
  const bound = openRequirementsFor(deps.repo.snapshot(), windowKey)
  const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
  if (target === undefined) return undefined
  const nowTs = deps.clock.now()
  const result = await deps.repo.mutate('requirement-updated', (ledger) => {
    const req = ledger.requirements.find(r => r.id === target.id)
    if (req === undefined) return undefined
    if (stampInterruption(req, nowTs, reason, tool)) {
      req.comments.push({
        id: deps.ids.comment(),
        body: fmt('[断点] {reason}（阶段 {stage}，下一步 {action}）', {
          reason,
          stage: req.status,
          action: req.interruption?.pendingAction ?? '',
        }),
        createdAt: nowTs,
        createdBy: { kind: 'system' },
      })
      req.version += 1
      req.updatedAt = nowTs
    }
    return { requirements: [req] }
  })
  const changed = (result.changed.requirements ?? [])[0]
  const interruption = changed?.interruption
  if (changed === undefined || interruption === undefined) return undefined
  return {
    requirement_id: changed.id,
    interruption,
    note: fmt('已记断点：{reason}（阶段 {stage}，下一步 {action}）', {
      reason: interruption.reason,
      stage: interruption.stage,
      action: interruption.pendingAction,
    }),
  }
}

/** B′ 工具入口：reqboard_note_interruption(reason)。 */
export async function noteInterruption(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
  const windowKey = agentIdFromExec(deps, exec)
  requireLiveDriver(deps, exec)
  const a = (args ?? {}) as { reason?: unknown; requirement_id?: unknown }
  const reason = normalizeText(a.reason, 'reason', 1000)
  const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
  if (reason.length === 0) {
    reject('reqboard_note_interruption 未执行：reason 不能为空（中断原因原文，如 upstream stream idle 3m）', 'REQBOARD_INVALID_INPUT')
  }
  const out = await noteInterruptionCore(deps, windowKey, reason, explicitId, 'reqboard_note_interruption')
  if (out === undefined) {
    if (explicitId.length > 0) {
      reject(fmt('reqboard_note_interruption 未执行：需求 {id} 不是本窗口绑定的进行中需求', { id: explicitId }), 'REQBOARD_NOT_BOUND_TO_WINDOW')
    }
    reject('reqboard_note_interruption 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
  }
  return {
    success: true,
    requirement_id: out.requirement_id,
    interruption: out.interruption,
    note: out.note,
  }
}

/**
 * B 事件入口：turn/end 异常收尾时由组合根经异步边界调用。**永不抛**（调用方还会再
 * catch）——空 reason / 空窗口 / 窗口无绑定需求一律返回 undefined，不打断流水线。
 */
export async function noteInterruptionForWindow(
  deps: UseCaseDeps,
  windowKey: string,
  reason: string,
  tool?: string,
): Promise<NoteInterruptionResult | undefined> {
  const text = typeof reason === 'string' ? reason.trim().slice(0, 1000) : ''
  if (text.length === 0 || windowKey.length === 0) return undefined
  return noteInterruptionCore(deps, windowKey, text, '', tool)
}
