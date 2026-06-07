/**
 * 调度器数据映射工具
 * 负责后端数据 ↔ 前端数据的转换
 */

import type {
  Task,
  TaskForm,
  TaskLevel,
  RunLevel,
  HistoryRecord,
  BackendTaskSummary,
  BackendRun,
  BackendTaskRequest
} from '@/types/scheduler'

// ========== 辅助函数 ==========

/**
 * 判断任务是否已删除
 */
export function isDeletedTaskSummary(task: BackendTaskSummary): boolean {
  const payload = task.payload || {}
  return Boolean(payload._deleted_at || task.deletedAt || task.deleted_at)
}

/**
 * 从后端运行记录获取运行级别
 */
export function getRunLevel(run: BackendRun): RunLevel {
  const payload = (run.payload || {}) as Record<string, unknown>
  if (run.status === 'failed' || run.status === 'compensation_failed') return 'failed'
  if (run.status === 'skipped' || payload.status === 'skipped') return 'skipped'
  if (payload.status === 'failed' || payload.status === 'error') return 'internal_failed'
  return 'success'
}

/**
 * 根据任务状态获取任务级别
 */
export function getTaskLevel(enabled: boolean, lastStatus: RunLevel | null): TaskLevel {
  if (!enabled) return 'paused'
  if (!lastStatus) return 'idle'
  if (lastStatus === 'failed') return 'failed'
  if (lastStatus === 'internal_failed' || lastStatus === 'skipped') return 'warning'
  return 'healthy'
}

/**
 * 格式化 payload 参数为显示字符串
 * 排除 command 和 description 字段
 */
export function formatPayloadParams(payload: Record<string, unknown>): string {
  const { command, description, ...rest } = payload
  const entries = Object.entries(rest)
  if (entries.length === 0) return ''
  return entries.map(([k, v]) => `${k}: ${v}`).join(', ')
}

/**
 * 总结 payload 内容
 * 用于运行历史的结果摘要和详情
 */
export function summarizePayload(payload: unknown): { summary: string; detail: string } {
  if (!payload) return { summary: '', detail: '' }

  if (typeof payload !== 'object') {
    const value = String(payload)
    return { summary: value, detail: value }
  }

  const record = payload as Record<string, unknown>
  const detail = JSON.stringify(record)

  const parts = [
    record.action ? String(record.action) : '',
    record.status ? `status=${record.status}` : '',
    typeof record.errors === 'number' ? `errors=${record.errors}` : '',
    Array.isArray(record.errors) ? `errors=${record.errors.length}` : '',
    typeof record.symbols_checked === 'number' ? `checked=${record.symbols_checked}` : '',
    typeof record.symbols_updated === 'number' ? `updated=${record.symbols_updated}` : '',
    typeof record.symbols_processed === 'number' ? `processed=${record.symbols_processed}` : '',
    typeof record.symbols_computed === 'number' ? `computed=${record.symbols_computed}` : '',
  ].filter(Boolean)

  return {
    summary: parts.join(', ') || detail,
    detail,
  }
}

// ========== 核心映射函数 ==========

/**
 * 判断任务是否正在运行
 */
export function isTaskRunning(lastRun?: BackendRun): boolean {
  if (!lastRun) return false

  // 如果有 finishedAt，说明已完成
  if (lastRun.finishedAt) return false

  // 如果有 startedAt 但没有 finishedAt，说明正在运行
  if (lastRun.startedAt) return true

  // 如果只有 triggeredAt，也认为正在运行（刚触发）
  if (lastRun.triggeredAt) return true

  return false
}

/**
 * 映射后端任务摘要 → 前端任务对象
 */
export function mapTask(backendTask: BackendTaskSummary): Task {
  const payload = backendTask.payload || {}
  const lastRun = backendTask.lastRun
  const lastStatus = lastRun ? getRunLevel(lastRun) : null
  const enabled = Boolean(backendTask.enabled)
  const isRunning = isTaskRunning(lastRun)

  return {
    id: backendTask.id,
    name: backendTask.name,
    command: (payload.command as string) || '',
    cron: backendTask.scheduleKind === 'cron' ? (backendTask.scheduleExpr || '') : '',
    params: formatPayloadParams(payload),
    description: (payload.description as string) || '',
    enabled,
    lastRun: (lastRun?.finishedAt ?? lastRun?.startedAt ?? lastRun?.triggeredAt ?? null) as string | null,
    nextRun: (backendTask.nextRunAt ?? null) as string | null,
    lastStatus,
    level: getTaskLevel(enabled, lastStatus),
    isRunning,
  }
}

/**
 * 映射后端运行记录 → 前端历史记录
 */
export function mapRun(backendRun: BackendRun): HistoryRecord {
  const payload = summarizePayload(backendRun.payload)

  return {
    id: String(backendRun.id ?? ''),
    taskName: backendRun.taskName,
    status: getRunLevel(backendRun),
    startTime: (backendRun.startedAt ?? backendRun.triggeredAt ?? '') as string,
    endTime: (backendRun.finishedAt ?? '') as string,
    duration: typeof backendRun.durationMs === 'number' ? Math.round(backendRun.durationMs / 1000) : 0,
    result: payload.summary,
    resultDetail: payload.detail,
    error: (backendRun.error ?? '') as string,
  }
}

/**
 * 构建后端任务创建/更新请求对象
 */
export function buildTaskRequest(form: TaskForm): BackendTaskRequest {
  const payload: Record<string, unknown> = {}

  if (form.command) payload.command = form.command
  if (form.description) payload.description = form.description

  // 解析参数字符串
  const paramsStr = String(form.params || '').trim()
  if (paramsStr) {
    try {
      // 尝试作为 JSON 解析
      const parsed = JSON.parse(paramsStr)
      if (typeof parsed === 'object' && parsed !== null) {
        Object.assign(payload, parsed)
      } else {
        payload.params = form.params
      }
    } catch {
      // 尝试作为 key:value 对解析
      const pairs: Record<string, string> = {}
      paramsStr.split(',').forEach((pair) => {
        const colonIdx = pair.indexOf(':')
        if (colonIdx > 0) {
          pairs[pair.slice(0, colonIdx).trim()] = pair.slice(colonIdx + 1).trim()
        }
      })
      if (Object.keys(pairs).length > 0) {
        Object.assign(payload, pairs)
      } else {
        payload.params = form.params
      }
    }
  }

  return {
    name: form.name,
    enabled: form.enabled !== false,
    scheduleKind: 'cron',
    scheduleExpr: form.cron,
    payload,
  }
}

/**
 * 映射任务对象 → 任务表单
 * 用于编辑时回显
 */
export function mapTaskToForm(task: Task): TaskForm {
  return {
    id: task.id,
    name: task.name,
    command: task.command,
    cron: task.cron,
    params: task.params,
    description: task.description,
    enabled: task.enabled,
  }
}
