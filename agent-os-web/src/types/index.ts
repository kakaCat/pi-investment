// 任务类型
export interface Task {
  id: string
  name: string
  owner: string
  description?: string
  cron: string
  command?: string
  webhook_url?: string
  payload?: Record<string, any>
  timeout: number
  retry_count: number
  enabled: boolean
  created_at: string
  updated_at: string
}

// 任务执行记录
export interface TaskRun {
  id: string
  task_id: string
  status: string
  started_at: string
  finished_at?: string
  output?: string
  error?: string
}

// 技能类型
export interface Skill {
  id: string
  name: string
  description: string
  category: string
  owner: string
  status: string
  current_version: string
  created_at: string
}

// 事件类型
export interface EventItem {
  type: string
  agent_id: string
  data: Record<string, any>
  timestamp: string
}
