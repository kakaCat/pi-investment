/**
 * ConfirmReceipt 用例（REQ-260924213231-b1c4 T-6 · serves: FR-3 / I-4）——挂起确认的回执查询。
 *
 * 语义（design/interfaces.md I-4 字段明细 + E-5 + design/architecture.md L92/L102）：
 *   · ticket 必须属于**本窗口**且在有效期内；未知/跨窗口/过期 → \`REQBOARD_UNKNOWN_TICKET\`
 *     （引导改读 \`reqboard_status.design_docs[].confirmed\`——以台账为准，不猜）；
 *   · \`confirmed\` **以台账为准**：目标产物 \`confirmedAt\` 已写（target=artifact，成组语义同
 *     \`artifactsToConfirm\`）/ 计划 \`approvedAt\` 已写（target=plan）→ true。注册表只是加速器：
 *     后台尚未作答、或进程重启丢了 outcome，事实判定都不受影响；
 *   · \`advanced\` / \`from\` / \`to\` 从 statusHistory 的确认推进事件还原（推进原因由
 *     \`internal/confirm-settle.ts\` 单点定义，本文件不另立口径）；
 *   · 用户选择/意见取后台回填的 outcome（缺省不返回该键）。
 *
 * 幂等：重复调用返回同一事实（台账不变 → 结论不变），无副作用。
 *
 * @module dsh-pmboard/application/use-cases/ConfirmReceipt
 */
import type { UseCaseDeps } from '../ports.js'
import {
  normalizeText,
  type PendingConfirmation,
  type RequirementRecord,
} from '../../shared/protocol.js'
import { fmt } from '../../domain/text/fmt.js'
import {
  CONFIRM_ADVANCE_REASON,
  PLAN_MERGE_ADVANCE_REASON,
} from '../internal/confirm-settle.js'
import { reject, agentIdFromExec, requireLiveDriver } from '../internal/support.js'

export async function confirmReceipt(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
  const windowKey = agentIdFromExec(deps, exec)
  requireLiveDriver(deps, exec)
  const a = (args ?? {}) as { ticket?: unknown }
  const ticket = normalizeText(a.ticket, 'ticket', 64)
  if (ticket.length === 0) {
    reject('reqboard_confirm_receipt 未执行：ticket 不能为空（reqboard_ask_confirm 返回 pending=true 时的 ticket）', 'REQBOARD_INVALID_INPUT')
  }

  // 注册表缺失（未装配非阻塞能力）与未知/跨窗口/过期同码：本窗口没有这条挂起确认的事实。
  const rec = deps.pendingConfirms?.get(ticket, windowKey)
  if (rec === undefined) {
    reject(
      'reqboard_confirm_receipt 未执行：ticket ' + ticket + ' 未知或已过期（不属于本窗口或超出有效期）——'
      + '回执事务已不可查，改调 reqboard_status 读 design_docs[].confirmed（以台账为准）',
      'REQBOARD_UNKNOWN_TICKET',
    )
  }

  const req = deps.repo.snapshot().requirements.find(r => r.id === rec.requirementId)
  if (req === undefined) {
    reject('reqboard_confirm_receipt 未执行：需求 ' + rec.requirementId + ' 不在台账中', 'REQBOARD_STORE_INCONSISTENT')
  }

  const confirmed = confirmedInLedger(req, rec)
  const adv = advanceFromHistory(req, rec.createdAt)
  const outcome = rec.outcome
  // 推进事实以「回填的 outcome」优先；尚未回填时以台账 statusHistory 还原（两处同源，不冲突）。
  const advanced = outcome?.advanced ?? adv.advanced
  const note = receiptNote(confirmed, advanced, adv, outcome)

  return {
    success: true,
    confirmed,
    advanced,
    from: adv.from,
    to: adv.to,
    requirement_id: rec.requirementId,
    ...(outcome?.userChoice !== undefined ? { user_choice: outcome.userChoice } : {}),
    ...(outcome?.userFeedback !== undefined ? { user_feedback: outcome.userFeedback } : {}),
    note,
  }
}

/** 台账事实：target=plan 看计划批准章；target=artifact 看该 kind 全部产物是否成组落章。 */
function confirmedInLedger(req: RequirementRecord, rec: PendingConfirmation): boolean {
  if (rec.target === 'plan') return req.plan?.approvedAt !== undefined
  const arts = (req.artifacts ?? []).filter(a => a.kind === rec.kind)
  return arts.length > 0 && arts.every(a => a.confirmedAt !== undefined)
}

/**
 * 从 statusHistory 还原确认推进（只看 ticket 登记之后的条目——更早的同类推进属于上一个确认门）。
 * 推进原因取自 confirm-settle 的单点常量；无匹配 → 未推进（from=to=当前状态）。
 */
function advanceFromHistory(
  req: RequirementRecord,
  sinceAt: number,
): { from: string; to: string; advanced: boolean } {
  const history = req.statusHistory ?? []
  for (let i = history.length - 1; i >= 0; i--) {
    const e = history[i]!
    if (e.at < sinceAt) break
    if (e.reason === CONFIRM_ADVANCE_REASON || e.reason === PLAN_MERGE_ADVANCE_REASON) {
      return { from: history[i - 1]?.status ?? 'draft', to: e.status, advanced: true }
    }
  }
  return { from: req.status, to: req.status, advanced: false }
}

/** 一句话说清回执结论（人话；不猜、不粉饰）。 */
function receiptNote(
  confirmed: boolean,
  advanced: boolean,
  adv: { from: string; to: string },
  outcome: PendingConfirmation['outcome'],
): string {
  if (confirmed && advanced) {
    return fmt('回执：已确认并推进 {from} → {to}（以台账为准）', { from: adv.from, to: adv.to })
  }
  if (confirmed) {
    return '回执：已确认（未推进；推进被闸门拦下或当前状态无可自动推进的下一阶段）——以台账 confirmedAt 为准'
  }
  if (outcome !== undefined) {
    const choice = outcome.userChoice ?? '（未选）'
    const feedback = outcome.userFeedback !== undefined && outcome.userFeedback.length > 0
      ? fmt('；用户意见：{fb}', { fb: outcome.userFeedback })
      : ''
    return fmt('回执：用户未确认（选择：{c}）——节点未推进{fb}。按意见修改后可重新发起确认', { c: choice, fb: feedback })
  }
  return '回执：挂起确认尚未作答——人作答后后台自动落章/推进；也可请用户走看板确认'
}
