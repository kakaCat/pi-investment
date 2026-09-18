/**
 * 把某需求的条款接收状态写回需求文档（REQ-d3e61a T-5 / PRD FR-3 的"自动更新"落点）。
 *
 * 触发时机 = 卡的生命周期变化（reqboard_task_move 落库之后）：取消一张卡的交付，同一次调用里
 * 需求文档的对应条就回落为「🔴 未被接收」——不靠人记得去重新生成。
 *
 * 幂等：内容未变则不写盘（避免无谓的 mtime 抖动与文档 diff 噪声）。
 *
 * @module dsh-pmboard/application/use-cases/SyncRequirementMarks
 */
import type { UseCaseDeps } from '../ports.js'
import type { RequirementRecord } from '../../shared/protocol.js'
import { assembleRequirementMarks } from '../query/QueryRequirementMarks.js'
import { renderMarksBlock, upsertMarksBlock } from '../internal/requirement-marks-doc.js'

/** 回写结果：synced=false 表示"文档不存在 / 内容未变"，两种都属正常，不是错误。 */
export interface SyncMarksResult {
  readonly synced: boolean
  readonly path: string
  /** 未被接收的条款（调用方可据此播报缺口；空数组=没有缺口） */
  readonly unreceived: readonly string[]
}

function requirementDocPath(reqId: string): string {
  return 'docs/requirements/' + reqId + '/requirement.md'
}

/** 把接收状态写回 `docs/requirements/<req>/requirement.md`（文档不存在 → 静默跳过）。 */
export async function syncRequirementMarks(
  deps: Pick<UseCaseDeps, 'docs'>,
  req: RequirementRecord,
  tasks: readonly { id: string; status: string; lastReport?: { completed?: readonly string[]; filesChanged?: readonly string[] } | undefined }[],
): Promise<SyncMarksResult> {
  const path = requirementDocPath(req.id)
  if (!deps.docs.exists(path)) return { synced: false, path, unreceived: [] }
  const before = await deps.docs.read(path).catch(() => undefined)
  if (before === undefined) return { synced: false, path, unreceived: [] }
  const view = await assembleRequirementMarks({ docs: deps.docs }, req, tasks)
  const after = upsertMarksBlock(before, renderMarksBlock(view))
  if (after === before) return { synced: false, path, unreceived: view.unreceived }
  await deps.docs.write(path, after)
  return { synced: true, path, unreceived: view.unreceived }
}
