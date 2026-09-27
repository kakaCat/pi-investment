/**
 * TaskTree 用例（REQ-260927144541-0481 FR-3 / design I-3）——父子结构**只读**视图。
 *
 * 为什么需要：需求级 reqboard_status 只给计数（看不到链上是谁），单卡级 reqboard_task_status
 * 又要求先知道卡 id——"链上有哪几张卡、各自到哪一步"此前只能靠人脑拼。本用例把台账里
 * parentId + dependsOn 已经表达的结构，投影成一次调用可读的树。
 *
 * 纪律（design/data-model §约束）：
 *  - **只读**：不 mutate，不改任何台账字段；
 *  - **绑定**：只读本窗口绑定需求下的任务，跨窗口一律显式拒绝（不返回空当成功）；
 *  - **顺序**：subtasks 按 dependsOn 链序；成环/悬空时回退稳定插入序（不抛）。
 *
 * @module dsh-pmboard/application/use-cases/TaskTree
 */
import type { UseCaseDeps } from '../ports.js'
import type { TaskRecord } from '../../shared/protocol.js'
import { normalizeText, taskRoleIn } from '../../shared/protocol.js'
import { openRequirementsFor } from '../internal/window.js'
import { countDoneTasks } from '../../domain/status/Predicates.js'
import { fmt } from '../../domain/text/fmt.js'
import { taskStoreOf } from './queue-access.js'

/** 树节点投影（design/data-model §新增视图模型）。 */
export interface TaskTreeNodeView {
  id: string
  title: string
  status: string
  role: 'parent' | 'subtask' | 'legacy'
  stageKind?: string
  dependsOn: string[]
  attempt?: number
  lastRunOk?: boolean
  reportSummary?: string
  cardDoc: string
}

export interface TaskTreeView {
  parent: TaskTreeNodeView
  subtasks: TaskTreeNodeView[]
  note: string
}

export interface TaskTreeResult {
  success: boolean
  requirement_id: string
  parents: TaskTreeView[]
  error?: string
}

/** 汇报摘要上限（字符）：tree 是"一眼看清"，不搬运全文（decision D-2 选 A）。 */
const REPORT_SUMMARY_MAX = 120

/** 无子卡时的固定文案（design/data-model §I-3；测试与文档同源）。 */
const NOTE_NOT_EXPANDED = '该父卡尚未开工展开子卡链'

function clip(text: string, max: number): string {
  return text.length <= max ? text : text.slice(0, max - 1) + '…'
}

/** 单节点投影（只读字段；缺省字段不硬造）。 */
function nodeOf(task: TaskRecord, tasks: readonly TaskRecord[]): TaskTreeNodeView {
  const node: TaskTreeNodeView = {
    id: task.id,
    title: task.title,
    status: task.status,
    role: taskRoleIn(tasks, task),
    dependsOn: [...task.dependsOn],
    cardDoc: typeof task.cardDoc === 'string' && task.cardDoc.length > 0
      ? task.cardDoc
      : 'docs/requirements/' + task.requirementId + '/tasks/' + task.id + '.md',
  }
  if (task.stageKind !== undefined) node.stageKind = task.stageKind
  if (task.attempt !== undefined) node.attempt = task.attempt
  if (task.lastRun !== undefined) node.lastRunOk = task.lastRun.ok
  if (task.lastReport !== undefined) {
    // 台账的 TaskReportSummary 只有 {at, reportIndex, filesChanged, completed}——**没有** summary
    // 文本字段，而本需求不新增台账字段（design/data-model §1）。摘要因此由既有事实派生，不另造字段。
    const head = task.lastReport.completed.length > 0 ? task.lastReport.completed.join('；') : '无完成项'
    node.reportSummary = clip(fmt('第 {n} 次汇报：{head}', { n: task.lastReport.reportIndex, head }), REPORT_SUMMARY_MAX)
  }
  return node
}

/**
 * 子卡链序：反复取"链内前置已就位"的卡。成环或悬空依赖时把剩余卡按插入序补回（**不抛**）——
 * 视图工具宁可少一点顺序保证，也不能因为脏数据让整个查询失败。
 */
function chainOrder(subs: readonly TaskRecord[]): TaskRecord[] {
  const ids = new Set(subs.map((s) => s.id))
  const remaining = [...subs]
  const ordered: TaskRecord[] = []
  const placed = new Set<string>()
  while (remaining.length > 0) {
    const idx = remaining.findIndex((s) => s.dependsOn.every((d) => !ids.has(d) || placed.has(d)))
    if (idx < 0) {
      ordered.push(...remaining)
      break
    }
    const next = remaining.splice(idx, 1)[0]
    if (next === undefined) break
    ordered.push(next)
    placed.add(next.id)
  }
  return ordered
}

function fail(code: string, requirementId: string, detail: string): TaskTreeResult {
  return { success: false, requirement_id: requirementId, parents: [], error: fmt('{code}：{detail}', { code, detail }) }
}

/** 执行 reqboard_task_tree：只读、经端口、按窗口绑定（跨窗口不返回空当成功）。 */
export async function executeTaskTree(
  deps: UseCaseDeps,
  args: unknown,
  exec: unknown,
): Promise<TaskTreeResult> {
  const windowKey = deps.session.windowKey(exec)
  const a = (args ?? {}) as Record<string, unknown>
  const snap = deps.repo.snapshot()
  const bound = openRequirementsFor(snap, windowKey)

  // 1. 目标需求：显式 requirement_id 优先（须绑定校验）；否则取本窗口绑定需求。
  let requirementId = normalizeText(a.requirement_id, 'requirement_id', 64)
  if (requirementId.length === 0) {
    const first = bound[0]
    if (first === undefined) {
      return fail('REQBOARD_NO_BOUND_REQ', '', '本窗口未绑定需求，请传 requirement_id')
    }
    requirementId = first.id
  } else if (!bound.some((r) => r.id === requirementId)) {
    return fail('REQBOARD_NOT_BOUND_TO_WINDOW', requirementId, fmt('需求 {id} 不属于本窗口绑定的需求', { id: requirementId }))
  }

  const store = taskStoreOf(deps)
  const inReq = await store.listByRequirement(requirementId)
  const byId = new Map(inReq.map((t) => [t.id, t]))

  // 2. 根集合：显式 parent_id → 该卡；否则该需求下全部顶层卡（parentId 缺省）。
  const parentId = normalizeText(a.parent_id, 'parent_id', 64)
  let roots: TaskRecord[]
  if (parentId.length > 0) {
    const task = byId.get(parentId)
    if (task === undefined) {
      const anywhere = await store.get(parentId)
      if (anywhere === undefined) return fail('REQBOARD_TASK_NOT_FOUND', requirementId, fmt('任务不存在：{id}', { id: parentId }))
      return fail('REQBOARD_NOT_BOUND_TO_WINDOW', requirementId,
        fmt('任务 {id} 属于需求 {req}，不属于本窗口绑定的需求', { id: parentId, req: anywhere.requirementId }))
    }
    roots = [task]
  } else {
    roots = inReq.filter((t) => t.parentId === undefined)
  }

  // 3. 逐根投影（父卡 + 链序子卡）。
  const parents: TaskTreeView[] = roots.map((parent) => {
    const subs = chainOrder(inReq.filter((t) => t.parentId === parent.id))
    const done = countDoneTasks(subs)
    const note = subs.length === 0
      ? NOTE_NOT_EXPANDED
      : fmt('子卡链 {n} 张，已完成 {done} 张', { n: subs.length, done })
    return { parent: nodeOf(parent, inReq), subtasks: subs.map((s) => nodeOf(s, inReq)), note }
  })

  return { success: true, requirement_id: requirementId, parents }
}
