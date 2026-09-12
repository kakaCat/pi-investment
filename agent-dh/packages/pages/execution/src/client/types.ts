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
  /** 调度来源：v2=quantsys-v2 引擎任务 / os=Agent OS 定时（webhook 触发 agent） */
  src?: string
  /** 是否调用 agent：dh=agent-dh / ts=agent-ts（无则不显示） */
  agentCall?: string
  /** 任务自带业务线字段（OS=agent_line）——分类首选依据（2026-09-12） */
  agentLine?: string | null
  /** v2 领域六域——与业务线正交，仅作打标对账信号 */
  domain?: string | null
}
export type ErrorEventStatus = 'open' | 'processing' | 'resolved' | 'ignored'
/** 错误事件（数据源=Agent OS error_events 表，采集入库按指纹去重） */
export interface ErrorEvent {
  source?: string
  /** 最近一次出现时间（last_seen_at） */
  timestamp?: string
  /** 错误摘要（msg 提炼，一行） */
  line?: string
  /** 来源文件/任务（log_path basename 或 task_name） */
  file?: string
  // —— Agent OS error_events DB 字段 ——
  id?: string
  status?: ErrorEventStatus
  occurrenceCount?: number
  firstSeenAt?: string
  lastSeenAt?: string
  level?: string
  msg?: string
  detail?: string | null
  taskName?: string | null
  taskId?: string | null
  assignee?: string | null
  dispatchedSession?: string | null
  resolvedAt?: string | null
  resolutionNote?: string | null
  logPath?: string | null
}
export interface TimelineEntry {
  taskId?: string | number
  taskName?: string
  expectedTime?: string
  status?: string
  runId?: string | number
  error?: string
  /** 频率分桶：daily=日执行 / weekly=周执行 */
  freq?: 'daily' | 'weekly'
  /** 透传调度来源与 agent 调用标记（徽标渲染） */
  src?: string
  agentCall?: string
  /** 透传任务自带业务线字段（分类首选依据） */
  agentLine?: string | null
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
  /** 分类对账（2026-09-12）：字段是否打通 / 未归类清单 / OS 并入对账 */
  taskCoverage?: {
    total?: number
    byLine?: Record<string, number>
    fieldTagged?: number
    fieldMissing?: number
    unclassified?: string[]
    os?: { apiTotal?: number; included?: number; excluded?: number; byReason?: Record<string, number> }
  }
  errors?: ErrorEvent[]
  timeline?: TimelineEntry[]
  blockedFlows?: BlockedFlowEntry[]
  degraded?: { source?: string; error?: string }[]
  v2Available?: boolean
  fetchedAt?: string
  orphanedTasks?: OrphanedTask[]
}
export interface ApiResponse {
  success?: boolean
  data?: BoardData
  error?: string
}
export interface OrphanedTask {
  id?: string
  name?: string
  scheduleExpr?: string
  lastRunAt?: string | null
  createdAt?: string
  inScheduler?: boolean
  inDatabase?: boolean
  daysSinceLastRun?: number
  enabled?: boolean
  reason?: string
  webhookUrl?: string
}
