/**
 * 运行期跨卡覆盖兜底（REQ-4842fe t9 / FR-10 次防线）。
 *
 * 子卡产出文件若其 mtime 落在**同需求另一张在跑父卡**的子卡执行窗口内 → 判跨卡覆盖，
 * 该子卡失败并停链，交人仲裁（不自动改文件）。
 *
 * 诚实边界：mtime 只证明"文件被改过"，不证明"内容正确"——本检查防静默覆盖，
 * 不替代人工 review。
 *
 * @module dsh-pmboard/application/internal/cross-card
 */
export interface CrossCardViewTask {
  id: string
  parentId?: string
  status: string
  executions?: ReadonlyArray<{ startedAt: number; endedAt?: number; outcome: string }>
}

export interface CrossCardConflict {
  file: string
  otherParentId: string
  otherSubtaskId: string
}

/**
 * 检测跨卡覆盖。windowEnd 用当前时刻（在跑的执行窗口尚未结束）。
 */
export function detectCrossCardOverwrite(
  tasks: readonly CrossCardViewTask[],
  myParentId: string,
  files: readonly string[],
  mtimeOf: (file: string) => number | undefined,
  now: number,
): CrossCardConflict | undefined {
  const otherParents = new Set(
    tasks.filter((t) => t.parentId === undefined && t.status === 'in_progress' && t.id !== myParentId).map((t) => t.id),
  )
  if (otherParents.size === 0) return undefined
  for (const other of tasks) {
    if (other.parentId === undefined || !otherParents.has(other.parentId)) continue
    for (const exec of other.executions ?? []) {
      const end = exec.endedAt ?? now
      for (const file of files) {
        const mtime = mtimeOf(file)
        if (mtime !== undefined && mtime >= exec.startedAt && mtime <= end) {
          return { file, otherParentId: other.parentId, otherSubtaskId: other.id }
        }
      }
    }
  }
  return undefined
}
