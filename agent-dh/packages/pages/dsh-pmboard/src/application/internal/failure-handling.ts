/**
 * 失败处理与卡片修订（REQ-4842fe t8 / FR-7、FR-13、FR-15）。
 *
 * 用户裁定（2026-09-20）：**不自动重试**——失败常见根因是"需求本身没描述对"，
 * 自动重试解决不了描述错误，只会烧 token 并掩盖真因。故：失败 → 子卡退回 + attempt+1 +
 * 留痕 → 暂停自动链 → 高优告警 + 弹框请人三处置。
 *
 * @module dsh-pmboard/application/internal/failure-handling
 */
import { fmt } from '../../domain/text/fmt.js'
import type { IdFactory } from '../ports.js'
import type { ReqboardLedger, TaskRecord } from '../../shared/protocol.js'

export type FailureCategory = 'no_output' | 'run_failed' | 'gate_failed' | 'engine_unavailable' | 'unknown'

export interface FailureClass {
  category: FailureCategory
  reason: string
}

/** 失败分类（判定依据：run 结果 / 凭证门错误码 / 引擎缺失）。 */
export function classifyFailure(result: { ok: boolean; reason?: string; code?: string }): FailureClass {
  const reason = result.reason ?? ''
  if (result.code === 'REQBOARD_SUBTASK_GATE') return { category: 'gate_failed', reason }
  if (reason.includes('engine_unavailable')) return { category: 'engine_unavailable', reason }
  if (reason.length === 0) return { category: 'no_output', reason: '无产出（子代理返回 null / 产出为空）' }
  return { category: 'run_failed', reason }
}

/**
 * 子卡失败回退（in_progress → todo）+ attempt+1 + revisions(rollback) + 失败评论。
 * 返回是否真的回退了（幂等：非 in_progress 状态不改）。
 */
export function rollbackSubtask(
  ledger: ReqboardLedger,
  subtaskId: string,
  now: number,
  ids: IdFactory,
  failure: FailureClass,
): boolean {
  const t = ledger.tasks.find((x) => x.id === subtaskId)
  if (t === undefined || t.status !== 'in_progress') return false
  const attempt = t.attempt ?? 0
  t.status = 'todo'
  t.attempt = attempt + 1
  t.version += 1
  t.updatedAt = now
  t.updatedBy = { kind: 'system' }
  delete t.claimedAt
  delete t.claimedBy
  t.revisions = [
    ...(t.revisions ?? []),
    {
      at: now,
      by: { kind: 'system' },
      kind: 'rollback',
      reason: fmt('子卡执行失败（{category}）：{reason}', { category: failure.category, reason: failure.reason }),
      changes: [fmt('attempt: {from}→{to}', { from: attempt, to: attempt + 1 }), 'status: in_progress→todo'],
    },
  ]
  t.comments.push({
    id: ids.comment(),
    body: fmt('[子卡失败] 退回待办（第 {n} 次尝试）：{reason}。自动链已暂停，等人处置（重跑 / 退回上游 / 取消）', {
      n: attempt + 1,
      reason: failure.reason,
    }),
    createdAt: now,
    createdBy: { kind: 'system' },
  })
  for (const e of t.executions) {
    if (e.outcome === 'running') { e.endedAt = now; e.outcome = 'failed'; e.error = failure.reason }
  }
  return true
}

/** 卡片修订追加（FR-15）：就地更新 / 重开都走这里，append-only。 */
export function appendRevision(
  task: TaskRecord,
  at: number,
  kind: 'update' | 'rollback' | 'reopen',
  reason: string,
  changes: string[],
): void {
  task.revisions = [...(task.revisions ?? []), { at, by: { kind: 'human' }, kind, reason, changes }]
}
