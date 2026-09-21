/**
 * 返工就地更新（REQ-4842fe t8 / FR-15）：重新批准计划后，对受影响的既有父卡**就地更新**。
 *
 * 用户裁定：不新增重复卡、不把受影响卡置 canceled；每次修订写 revisions(kind=update)，
 * 形成可回溯时间线（与子卡失败回退同口径）。
 *
 * @module dsh-pmboard/application/internal/rework-update
 */
import { fmt } from '../../domain/text/fmt.js'
import type { PlanTask, ReqboardLedger, TaskRecord } from '../../shared/protocol.js'
import { appendRevision } from './failure-handling.js'

/**
 * 按计划任务表就地更新匹配的父卡（匹配键 = 标题：decompose 落库时标题取自计划）。
 * 返回被更新的卡（卡数不变——只更新、不新增）。
 */
export function applyReworkUpdate(
  ledger: ReqboardLedger,
  requirementId: string,
  planTasks: readonly PlanTask[],
  now: number,
): TaskRecord[] {
  const updated: TaskRecord[] = []
  for (const plan of planTasks) {
    const card = ledger.tasks.find(
      (t) => t.requirementId === requirementId && t.parentId === undefined && t.status !== 'canceled' && t.title === plan.title,
    )
    if (card === undefined) continue // 新增的计划任务由 decompose 负责落卡；这里只管"更新旧卡"
    const changes: string[] = []
    if ((plan.description ?? '') !== '' && card.description !== plan.description) {
      card.description = plan.description as string
      changes.push('description')
    }
    if ((plan.acceptance ?? '') !== '' && card.acceptance !== plan.acceptance) {
      card.acceptance = plan.acceptance as string
      changes.push('acceptance')
    }
    if ((plan.implementation ?? '') !== '' && card.implementation !== plan.implementation) {
      card.implementation = plan.implementation as string
      changes.push('implementation')
    }
    if (plan.phase !== undefined && card.phase !== plan.phase) {
      card.phase = plan.phase
      changes.push('phase')
    }
    if (plan.side !== undefined && card.side !== plan.side) {
      card.side = plan.side
      changes.push('side')
    }
    if (changes.length === 0) continue
    card.version += 1
    card.updatedAt = now
    appendRevision(card, now, 'update', fmt('返工回上游后重新批准计划（{key}）：就地更新', { key: plan.key }), changes)
    updated.push(card)
  }
  return updated
}
