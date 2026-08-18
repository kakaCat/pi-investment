// API 响应统一格式
export interface ApiResponse<T = any> {
  success: boolean
  data: T
  message?: string
  error?: string
}

// 分页响应
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

// ==================== 调度器相关 ====================

// 任务
export interface Task {
  id: string
  name: string
  cron: string
  enabled: boolean
  skill_id: string
  skill_name?: string
  last_run?: string
  next_run?: string
  created_at: string
  updated_at?: string
  description?: string
}

// 执行记录
export interface TaskRun {
  id: string
  task_id: string
  task_name: string
  status: 'success' | 'failed' | 'running' | 'timeout' | 'skipped'
  started_at: string
  finished_at?: string
  duration?: string
  error?: string
  result?: any
}

// ==================== 技能相关 ====================

// 技能
export interface Skill {
  id: string
  name: string
  category: string
  description: string
  owner: string
  status: 'active' | 'deprecated' | 'draft'
  content?: string
  content_type?: 'markdown' | 'json' | 'yaml'
  created_at: string
  updated_at?: string
  versions?: SkillVersion[]
}

// 技能版本
export interface SkillVersion {
  version: string
  hash: string
  author: string
  message: string
  content: string
  created_at: string
}

// ==================== 决策相关 ====================

// 决策
export interface Decision {
  id: string
  action: string
  target: string
  confidence: number
  status: 'pending' | 'executed' | 'cancelled' | 'failed'
  reason?: string
  pnl?: number
  created_at: string
  executed_at?: string
  timeline?: DecisionTimelineEvent[]
  data?: Record<string, any>
}

// 决策时间线事件
export interface DecisionTimelineEvent {
  timestamp: string
  type: 'created' | 'executed' | 'cancelled' | 'failed'
  description: string
}

// 决策统计
export interface DecisionStatistics {
  total: number
  executed: number
  pending: number
  avgConfidence: number
  typeDistribution: Array<{ name: string; value: number }>
  statusDistribution: Array<{ name: string; value: number }>
}

// ==================== 记忆相关 ====================

// 记忆
export interface Memory {
  id: string
  title: string
  content: string
  category: 'knowledge' | 'experience' | 'decision' | 'data'
  tags: string[]
  created_at: string
  updated_at?: string
}

// 标签
export interface Tag {
  name: string
  count: number
  created_at: string
}

// ==================== 事件相关 ====================

// 事件
export interface Event {
  id: string
  type: 'task' | 'decision' | 'memory' | 'quota' | 'system'
  message: string
  agent_id?: string
  timestamp: string
  data?: Record<string, any>
}

// 告警规则
export interface AlertRule {
  id: string
  name: string
  event_type: string
  condition: string
  level: 'info' | 'warning' | 'error' | 'critical'
  channels: string[]
  enabled: boolean
  triggered_count: number
  last_triggered_at?: string
}

// ==================== 通知相关 ====================

// 通知渠道
export interface NotificationChannel {
  id: string
  name: string
  type: 'feishu' | 'dingtalk' | 'wechat' | 'email' | 'webhook'
  enabled: boolean
  config: Record<string, any>
  last_sent_at?: string
  created_at: string
}

// 通知日志
export interface NotificationLog {
  id: string
  channel_name: string
  title: string
  content: string
  status: 'success' | 'failed'
  sent_at: string
  error?: string
}

// ==================== 系统相关 ====================

// 系统状态
export interface SystemStatus {
  status: 'ok' | 'error'
  uptime: number
  version: string
  components: Array<{
    name: string
    status: 'healthy' | 'unhealthy'
  }>
}

// 资源配额
export interface ResourceQuota {
  namespace: string
  resource_type: string
  limit: number
  used: number
  unit: string
}

// 命名空间
export interface Namespace {
  name: string
  description: string
  status: 'active' | 'inactive'
  created_at: string
}

// 系统日志
export interface SystemLog {
  id: string
  level: 'debug' | 'info' | 'warning' | 'error'
  source: string
  message: string
  timestamp: string
  details?: Record<string, any>
  user_agent?: string
  ip_address?: string
}

// ==================== 个人中心相关 ====================

// 操作记录
export interface ActivityLog {
  id: string
  action: 'create' | 'update' | 'delete' | 'execute'
  resource_type: string
  resource_name: string
  description: string
  ip_address: string
  user_agent?: string
  created_at: string
  details?: Record<string, any>
}

// 用户配置
export interface UserProfile {
  username: string
  email: string
  role: string
  timezone: string
}

// ==================== 概览相关 ====================

// 统计数据
export interface OverviewStats {
  total: number
  running: number
  successToday: number
  failedToday: number
}

// 健康状态项
export interface HealthItem {
  name: string
  status: 'healthy' | 'unhealthy'
}
