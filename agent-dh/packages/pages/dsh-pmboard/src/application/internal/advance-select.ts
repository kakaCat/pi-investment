/**
 * 推进事件的**纯选择器**（REQ-4842fe t7 / FR-11）：给定台账快照，决定"下一步该做什么"。
 *
 * 为什么单独成文件且纯函数：事件选择是自动链的心脏，"状态即事实"的幂等性全靠它——
 * 重复触发不会重复干活，因为选择依据全部来自台账客观状态。抽出后可用冻结入参单测，
 * 不必搭真 I/O（沿用 domain/workflow/RollupSpec 的同款纪律）。
 *
 * @module dsh-pmboard/application/internal/advance-select
 */
import type { AdvanceEvent, TaskRecord } from '../../shared/protocol.js'

export interface AdvanceView {
  readonly tasks: readonly TaskRecord[]
}

export interface AdvanceSelection {
  event: AdvanceEvent
  parentId?: string
  subtaskId?: string
}

/** 顶层卡（父卡/普通卡；不含子卡），排除已取消。 */
export function topLevelTasks(view: AdvanceView, requirementId: string): TaskRecord[] {
  return view.tasks.filter((t) => t.requirementId === requirementId && t.parentId === undefined && t.status !== 'canceled')
}

/** 同需求全部非取消子卡。 */
export function openSubtasks(view: AdvanceView, requirementId: string): TaskRecord[] {
  return view.tasks.filter((t) => t.requirementId === requirementId && t.parentId !== undefined && t.status !== 'canceled')
}

function depsDone(view: AdvanceView, task: TaskRecord): boolean {
  const doneIds = new Set(view.tasks.filter((t) => t.status === 'done').map((t) => t.id))
  return task.dependsOn.every((d) => doneIds.has(d))
}

/** 父卡名下子卡。 */
export function subtasksOf(view: AdvanceView, parentId: string): TaskRecord[] {
  return view.tasks.filter((t) => t.parentId === parentId)
}

/**
 * 选择下一个推进事件（优先级：收尾 → 跑子卡 → 开父卡 → rollup）。
 * 返回 undefined = 当前没有可推进的状态（可能已终态，也可能死锁；由调用方区分）。
 */
export function selectAdvanceEvent(view: AdvanceView, requirementId: string, maxParallelParents: number): AdvanceSelection | undefined {
  const parents = topLevelTasks(view, requirementId)
  // 1) 收尾：某个 in_progress 父卡的子卡全 done
  for (const parent of parents) {
    if (parent.status !== 'in_progress') continue
    const subs = subtasksOf(view, parent.id)
    if (subs.length > 0 && subs.every((s) => s.status === 'done' || s.status === 'canceled')) {
      return { event: 'FINALIZE_PARENT', parentId: parent.id }
    }
  }
  // 2) 跑子卡：某个 in_progress 父卡链上有 ready 子卡
  for (const parent of parents) {
    if (parent.status !== 'in_progress') continue
    const ready = subtasksOf(view, parent.id).find((s) => s.status === 'todo' && depsDone(view, s))
    if (ready !== undefined) return { event: 'RUN_SUBTASK', parentId: parent.id, subtaskId: ready.id }
  }
  // 3) 开父卡：ready 且并发未超限
  const active = parents.filter((p) => p.status === 'in_progress').length
  if (active < maxParallelParents) {
    const readyParent = parents.find((p) => p.status === 'todo' && depsDone(view, p))
    if (readyParent !== undefined) return { event: 'OPEN_PARENT', parentId: readyParent.id }
  }
  // 4) rollup：全部父卡收口（无在跑卡、无待办卡、无未完成子卡）
  const outstanding = parents.some((p) => p.status !== 'done')
  if (!outstanding && openSubtasks(view, requirementId).some((s) => s.status !== 'done')) {
    return undefined // 有子卡没收口（数据异常）→ 交给停滞判定
  }
  if (!outstanding) return { event: 'ROLLUP' }
  return undefined
}

/** 是否仍有"开放工作"（未 done 且未取消的卡）——用于区分"已终态"与"死锁停滞"。 */
export function hasOpenWork(view: AdvanceView, requirementId: string): boolean {
  return view.tasks.some((t) => t.requirementId === requirementId && t.status !== 'done' && t.status !== 'canceled')
}
