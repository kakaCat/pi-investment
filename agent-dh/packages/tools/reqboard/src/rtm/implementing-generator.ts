/**
 * rtm-implementing.yml（汇总）+ rtm-implementing/t-xxx.yml（任务详情）生成
 * （REQ-260926140539-457b FR-2 触发点 5/6、FR-10 性能、FR-11 子阶段追踪）。
 *
 * 拆分策略：汇总文件只放统计与任务 id/状态（轻量，Dive 秒读）；
 * 单任务详情（含 workflow 子阶段执行链）独立成文件，更新只写变化的那一份。
 *
 * @module @pi-investment/reqboard/rtm/implementing-generator
 */
import { getRTMPath, readRTM, writeRTM } from './file-io.js'
import type { RTMContext } from './context.js'
import { effectiveSections } from './decomposing-generator.js'
import {
  FULL_WORKFLOW,
  type RTMImplementing,
  type RTMTaskDetail,
  type RTMTaskLike,
  type WorkflowPhase,
  type WorkflowStatus,
  type WorkflowStep,
} from './types.js'

/** 任务状态分类（与 dsh-pmboard TaskStatus 对齐）。 */
const DONE_STATUSES = new Set(['done'])
const ACTIVE_STATUSES = new Set(['in_progress', 'testing', 'in_review', 'integrating'])

/** 按任务 phase/side 决定需要哪些子阶段。 */
export function workflowPhasesFor(phase?: string, side?: string): WorkflowPhase[] {
  switch (phase) {
    case 'implement':
      return ['implement']
    case 'doc':
      return ['doc', 'implement', 'test', 'commit']
    case 'ui':
      return ['ui', 'implement', 'test', 'commit']
    case 'analysis':
      return ['analysis', 'implement', 'test', 'commit']
    case 'test':
      return ['test']
    case 'review':
      return ['review']
    default:
      break
  }
  void side
  return [...FULL_WORKFLOW]
}

/** 新建任务详情时的初始 workflow（backend 任务的 ui 阶段标 skipped）。 */
export function initialWorkflow(phases: readonly WorkflowPhase[], side?: string): WorkflowStep[] {
  return phases.map(phase => {
    if (phase === 'ui' && side === 'backend') {
      return { phase, status: 'skipped' as WorkflowStatus, skip_reason: 'backend task, no UI needed' }
    }
    return { phase, status: 'pending' as WorkflowStatus }
  })
}

/** 单个任务的 workflow 参数（生成 Worker 提示词用）。 */
function workflowParams(ctx: RTMContext, reqId: string, task: RTMTaskLike): Record<string, string> {
  const section = effectiveSections(ctx, reqId).find(s => s.serves.some(fr => (task.serves ?? []).includes(fr)))
  return {
    REQ_ID: reqId,
    TASK_ID: task.id,
    TASK_TITLE: task.title ?? '',
    DESIGN_FILES: section?.file ?? '',
    TEST_PATTERN: 'rtm',
    SIDE: task.side ?? '',
    PHASE: task.phase ?? 'fullstack',
  }
}

/** 任务详情的相对文件名。 */
export function taskDetailName(taskId: string): string {
  return `rtm-implementing/${taskId}.yml`
}

/** 初始化或刷新单个任务详情文件（保留已有 workflow 进度）。 */
export function syncTaskDetail(ctx: RTMContext, reqId: string, task: RTMTaskLike): RTMTaskDetail {
  const filePath = getRTMPath(ctx.reqDir(reqId), taskDetailName(task.id))
  const existing = readRTM<RTMTaskDetail>(filePath)
  const phases = workflowPhasesFor(task.phase, task.side)
  const workflow = existing?.task?.workflow?.length
    ? existing.task.workflow
    : initialWorkflow(phases, task.side)
  const status = task.status ?? 'todo'
  const counted = workflow.filter(w => w.status === 'done').length
  const data: RTMTaskDetail = {
    task: {
      id: task.id,
      title: task.title ?? '',
      status,
      implements: task.implements ?? '',
      serves: task.serves ?? [],
      depends_on: task.depends_on ?? [],
      phase: task.phase ?? '',
      side: task.side ?? '',
      workflow_params: workflowParams(ctx, reqId, task),
      workflow_total: workflow.length,
      workflow_done: counted,
      workflow,
    },
    metadata: ctx.metadata('implementing', reqId, existing, { detail_dir: 'rtm-implementing/', detail_count: workflow.length }),
  }
  writeRTM(filePath, data)
  return data
}

/** 统计并写 rtm-implementing.yml 汇总文件。 */
export function refreshImplementingSummary(ctx: RTMContext, reqId: string): RTMImplementing {
  const filePath = getRTMPath(ctx.reqDir(reqId), 'rtm-implementing.yml')
  const existing = readRTM<RTMImplementing>(filePath)
  const tasks = ctx.tasks(reqId)
  let done = 0
  let active = 0
  for (const t of tasks) {
    const st = t.status ?? 'todo'
    if (DONE_STATUSES.has(st)) done += 1
    else if (ACTIVE_STATUSES.has(st)) active += 1
  }
  const data: RTMImplementing = {
    metadata: ctx.metadata('implementing', reqId, existing, {
      detail_dir: 'rtm-implementing/',
      detail_count: tasks.length,
    }),
    inputs: { tasks: tasks.map(t => ({ id: t.id, title: t.title ?? '', status: t.status ?? 'todo' })) },
    status: {
      tasks_total: tasks.length,
      tasks_done: done,
      tasks_in_progress: active,
      tasks_todo: tasks.length - done - active,
    },
    tasks: tasks.map(t => ({ id: t.id, status: t.status ?? 'todo' })),
  }
  writeRTM(filePath, data)
  return data
}

/** 生成实施节点 RTM：汇总 + 每个任务的详情文件。 */
export function generateImplementingRTM(ctx: RTMContext, reqId: string): RTMImplementing {
  for (const task of ctx.tasks(reqId)) syncTaskDetail(ctx, reqId, task)
  return refreshImplementingSummary(ctx, reqId)
}

/** 任务详情增量更新入参。 */
export interface TaskDetailUpdate {
  status?: string
  started_at?: string
  completed_at?: string
  workflow?: Array<{
    phase: WorkflowPhase
    status: WorkflowStatus
    started_at?: string
    completed_at?: string
    skip_reason?: string
    steps_completed?: Array<{ action: string; output?: string; files_changed?: string[]; commit?: string }>
  }>
  /** 是否同时刷新汇总统计（默认 true）。 */
  refreshSummary?: boolean
}

/** 增量更新单个任务详情（只写这一个文件）+ 可选刷新汇总。 */
export function updateTaskDetail(
  ctx: RTMContext,
  reqId: string,
  taskId: string,
  updates: TaskDetailUpdate,
): RTMTaskDetail | null {
  const filePath = getRTMPath(ctx.reqDir(reqId), taskDetailName(taskId))
  let detail = readRTM<RTMTaskDetail>(filePath)
  if (detail === null) {
    const task = ctx.tasks(reqId).find(t => t.id === taskId)
    if (task === undefined) return null
    detail = syncTaskDetail(ctx, reqId, task)
  }
  const task = detail.task
  const wasActive = ACTIVE_STATUSES.has(task.status)
  if (updates.status !== undefined) task.status = updates.status
  // 首次进入执行态：把第一个待办子阶段点亮（幂等——已有 in_progress 时不重复推进）
  if (!wasActive && ACTIVE_STATUSES.has(task.status) && !task.workflow.some(w => w.status === 'in_progress')) {
    const first = task.workflow.find(w => w.status === 'pending')
    if (first !== undefined) {
      first.status = 'in_progress'
      first.started_at = updates.started_at ?? ctx.iso()
    }
  }
  // 任务完成：未结束的子阶段一并收口（台账 done 是终态）
  if (task.status === 'done') {
    for (const w of task.workflow) {
      if (w.status === 'in_progress' || w.status === 'pending') {
        w.status = 'done'
        if (w.completed_at === undefined) w.completed_at = updates.completed_at ?? ctx.iso()
      }
    }
  }
  for (const u of updates.workflow ?? []) {
    const step = task.workflow.find(w => w.phase === u.phase)
    if (step === undefined) {
      task.workflow.push({ ...u })
      continue
    }
    step.status = u.status
    if (u.started_at !== undefined) step.started_at = u.started_at
    else if (u.status === 'in_progress' && step.started_at === undefined) step.started_at = ctx.iso()
    if (u.completed_at !== undefined) step.completed_at = u.completed_at
    else if (u.status === 'done' && step.completed_at === undefined) step.completed_at = ctx.iso()
    if (u.skip_reason !== undefined) step.skip_reason = u.skip_reason
    if (u.steps_completed !== undefined) step.steps_completed = u.steps_completed
  }
  task.workflow_total = task.workflow.length
  task.workflow_done = task.workflow.filter(w => w.status === 'done').length
  const data: RTMTaskDetail = {
    task,
    metadata: ctx.metadata('implementing', reqId, detail, { detail_dir: 'rtm-implementing/', detail_count: task.workflow_total }),
  }
  writeRTM(filePath, data)
  if (updates.refreshSummary !== false) refreshImplementingSummary(ctx, reqId)
  return data
}
