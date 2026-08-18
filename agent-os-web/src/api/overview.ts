import client from '@/utils/request'

export function getTaskStats() {
  // Agent OS 暂无 stats 端点，用任务列表代替
  return client.get('/scheduler/tasks')
}

export function getSystemHealth() {
  // health 端点不在 /api/v1 下，需要特殊处理
  return fetch('/health').then(r => r.json())
}

export function getRecentExecutions(taskId: string, limit = 10) {
  return client.get('/scheduler/executions', { params: { task_id: taskId, limit } })
}
