/**
 * 需求侧接收标记读路径（REQ-d3e61a T-5）。
 *
 * 为什么必须服务端算：**客户端拿不到判据的两半**——条款来自 requirement.md（文档），
 * 任务↔条款绑定来自 decomposition.md 的 RTM 表（文档）；client 只有 RequirementRecord + TaskRecord，
 * 而 TaskRecord 不存 requirement_refs。所以看板要显示它，只能服务端先算好放进 payload。
 *
 * 读数语义：需求文档不存在 → available=false（UI 显示"无条款数据"），**不冒充"全部未接收"**。
 *
 * @module dsh-pmboard/application/query/QueryRequirementMarks
 */
import type { UseCaseDeps } from '../ports.js'
import type { ClauseMarkRow, RequirementMarksView, RequirementRecord } from '../../shared/protocol.js'
import { parseDocument, extractClauseDefinitions, extractSkippedClauses } from '../internal/content-gates.js'
import { clauseReceiveStatus, collectTaskRefs } from '../internal/content-trace.js'

export type { ClauseMarkRow, RequirementMarksView }

/** 装配某需求的「逐条接收状态」视图（读 requirement.md + decomposition.md + 台账任务）。 */
export async function assembleRequirementMarks(
  deps: Pick<UseCaseDeps, 'docs'>,
  req: RequirementRecord,
  tasks: readonly { id: string; status: string; lastReport?: { completed?: readonly string[]; filesChanged?: readonly string[] } | undefined }[],
): Promise<RequirementMarksView> {
  // 任务**全量**交给推导：取消的卡由 clauseReceiveStatus 剔除（状态判定归 application/domain）
  const p = 'docs/requirements/' + req.id + '/requirement.md'
  if (!deps.docs.exists(p)) {
    return { requirementId: req.id, clauses: [], unreceived: [], available: false }
  }
  const doc = parseDocument(await deps.docs.read(p))
  const roots = extractClauseDefinitions(doc)
  if (roots.length === 0) {
    return { requirementId: req.id, clauses: [], unreceived: [], available: true }
  }
  const status = clauseReceiveStatus(roots, await collectTaskRefs(deps.docs, req), tasks, extractSkippedClauses(doc))
  const clauses: ClauseMarkRow[] = status.map(s => ({ clause: s.clause, state: s.state, by: [...s.by] }))
  return {
    requirementId: req.id,
    clauses,
    unreceived: status.filter(s => s.state === 'unreceived').map(s => s.clause),
    available: true,
  }
}
