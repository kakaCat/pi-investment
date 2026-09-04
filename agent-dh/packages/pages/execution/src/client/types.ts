// Client-half board types: kept in sync with src/types/index.ts (host side).
// Self-contained on purpose — the browser bundle must not import host files.

export interface BoardHealth {
  name?: string
  status?: string
  port?: number
  metrics?: Record<string, string | number | boolean | null | undefined>
  responseTimeMs?: number
  error?: string
}
export interface CheckpointResult {
  id?: string
  line?: string
  module?: string
  name?: string
  status?: string
  message?: string
  blocksFlow?: string[]
  /** 计划执行时间 HH:mm */
  expectTime?: string
}
export interface SchedulerTask {
  id?: string | number
  name?: string
  enabled?: boolean | string
  scheduleExpr?: string
  lastRun?: string | Record<string, unknown> | null
  nextRunAt?: string | null
  todaySuccess?: string | number
  todayTriggered?: string | number
  error?: string
}
export interface ErrorEvent {
  source?: string
  timestamp?: string
  line?: string
  file?: string
}
export interface TimelineEntry {
  taskId?: string | number
  taskName?: string
  expectedTime?: string
  status?: string
  runId?: string | number
  error?: string
}
export interface BlockedFlowEntry {
  checkpointId?: string
  checkpointName?: string
  status?: string
  blocks?: string[]
}
export interface BoardData {
  health?: BoardHealth[]
  checkpoints?: CheckpointResult[]
  tasks?: SchedulerTask[]
  errors?: ErrorEvent[]
  timeline?: TimelineEntry[]
  blockedFlows?: BlockedFlowEntry[]
  degraded?: { source?: string; error?: string }[]
  v2Available?: boolean
  fetchedAt?: string
}
export interface ApiResponse {
  success?: boolean
  data?: BoardData
  error?: string
}
