/**
 * 失败处理与卡片修订（REQ-4842fe t8 / FR-7、FR-13、FR-15）。
 *
 * 用户裁定（2026-09-20）：**不自动重试**——失败常见根因是"需求本身没描述对"，
 * 自动重试解决不了描述错误，只会烧 token 并掩盖真因。故：失败 → 子卡退回 + attempt+1 +
 * 留痕 → 暂停自动链 → 高优告警 + 弹框请人三处置。
 *
 * 2026-09-28 收窄（REQ-260928185112-e20d Phase2）：仅对**瞬断类（abort 族）**允许同一 job 内
 * 自动重试一次——它不改变"描述错误不自愈"的裁定，因为 abort 不是内容问题：实测 4 次
 * `workflow signal aborted` 在 0.1–3.6s 内瞬断（调用方 turn 结束所致），每次却把整条链停住等人。
 * 其余失败（凭证门/空产出/引擎缺失）**仍一律停下**，行为不变。
 *
 * @module dsh-pmboard/application/internal/failure-handling
 */
import { fmt } from '../../domain/text/fmt.js'
import type { IdFactory } from '../ports.js'
import type { TaskRecord } from '../../shared/protocol.js'
import { transitionTask } from './task-transition.js'

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
 * 是否**瞬断类**失败（REQ-260928185112-e20d Phase2）——只有这类才允许自动重试一次。
 *
 * 判据取自引擎的 stopReason 文案（`cancelled: workflow run cancelled: workflow signal aborted`、
 * `workflow execution failed (abort): runtime disposed`）。这类失败**不含任何关于内容对不对的信息**：
 * 是承载它的信号被掐掉了，重试一次是确定的正确动作；而凭证门/空产出/引擎缺失反映的是内容或环境问题，
 * 重试只会烧 token 并掩盖真因 —— 保持"失败即停、请人处置"。
 */
export function isTransientAbort(reason: string): boolean {
  return /signal aborted|workflow run cancelled|runtime disposed|\babort(ed)?\b/i.test(reason)
}

/**
 * 子卡失败回退（in_progress → todo）+ attempt+1 + revisions(rollback) + 失败评论。
 * 返回是否真的回退了（幂等：非 in_progress 状态不改）。
 *
 * @param tasks 队列任务**可变草稿**（REQ-260927202051-f6df D4：`LedgerView.tasks` 随 v9 移除）——
 *              本函数**就地改入参**，调用方在 `taskStore.mutate` 回调内 `return tasks` 落盘。
 */
export function rollbackSubtask(
  tasks: readonly TaskRecord[],
  subtaskId: string,
  now: number,
  ids: IdFactory,
  failure: FailureClass,
): boolean {
  const t = tasks.find((x) => x.id === subtaskId)
  if (t === undefined || t.status !== 'in_progress') return false
  const attempt = t.attempt ?? 0
  // 收敛点：失败退回也是状态转移，必须在唯一入口校验 + 记事件（此前直接赋值绕过了校验）
  transitionTask(t, 'todo', {
    at: now,
    actor: { kind: 'system' },
    role: 'subtask',
    reason: fmt('子卡失败退回（{category}）', { category: failure.category }),
  })
  t.attempt = attempt + 1
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
