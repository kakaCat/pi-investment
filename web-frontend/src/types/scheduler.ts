/**
 * 调度器类型定义
 */

// ========== 任务相关类型 ==========

export type TaskLevel = 'healthy' | 'warning' | 'failed' | 'paused' | 'idle'
export type RunLevel = 'success' | 'failed' | 'internal_failed' | 'skipped'

/**
 * 前端任务对象
 */
export interface Task {
  id: string
  name: string
  command: string
  cron: string
  params: string
  description: string
  enabled: boolean
  lastRun: string | null
  nextRun: string | null
  lastStatus: RunLevel | null
  level: TaskLevel
  isRunning: boolean  // 是否正在运行
}

/**
 * 任务表单对象
 */
export interface TaskForm {
  id?: string
  name: string
  command: string
  cron: string
  params: string
  description: string
  enabled: boolean
}

/**
 * 任务统计
 */
export interface TaskStats {
  enabled: number
  paused: number
  problem: number
}

/**
 * 任务级别统计
 */
export interface TaskLevelStat {
  level: TaskLevel
  label: string
  count: number
}

/**
 * 任务级别分组
 */
export interface TaskLevelGroup extends TaskLevelStat {
  tasks: Task[]
}

// ========== 运行历史相关类型 ==========

/**
 * 运行历史记录
 */
export interface HistoryRecord {
  id: string
  taskName: string
  status: RunLevel
  startTime: string
  endTime: string
  duration: number
  result: string
  resultDetail: string
  error: string
}

/**
 * 运行级别统计
 */
export interface HistoryLevelStat {
  level: RunLevel
  label: string
  count: number
}

// ========== 后端数据类型 ==========

/**
 * 后端任务摘要
 */
export interface BackendTaskSummary {
  id: string
  name: string
  enabled: boolean
  scheduleKind: string
  scheduleExpr: string
  payload?: Record<string, unknown>
  lastRun?: BackendRun
  nextRunAt?: string
  deletedAt?: string
  deleted_at?: string
}

/**
 * 后端运行记录
 */
export interface BackendRun {
  id: string | number
  taskName: string
  status: string
  payload?: Record<string, unknown>
  startedAt?: string
  finishedAt?: string
  triggeredAt?: string
  durationMs?: number
  error?: string
}

/**
 * 后端任务列表响应
 */
export interface BackendTaskListResponse {
  tasks: BackendTaskSummary[]
  total?: number
  count?: number
  pagination?: {
    total: number
    page: number
    pageSize: number
  }
}

/**
 * 后端运行历史响应
 */
export interface BackendRunListResponse {
  runs: BackendRun[]
  total?: number
  count?: number
  pagination?: {
    total: number
    page: number
    pageSize: number
  }
}

/**
 * 后端任务创建/更新请求
 */
export interface BackendTaskRequest {
  name: string
  enabled: boolean
  scheduleKind: 'cron'
  scheduleExpr: string
  payload: Record<string, unknown>
}

// ========== 常量 ==========

export const TASK_LEVEL_ORDER: TaskLevel[] = ['failed', 'warning', 'paused', 'idle', 'healthy']
export const HISTORY_LEVEL_ORDER: RunLevel[] = ['failed', 'internal_failed', 'skipped', 'success']
