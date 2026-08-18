import client from '@/utils/request'

export function getTaskStats() {
  return client.get('/scheduler/tasks/stats')
}

export function getSystemHealth() {
  return client.get('/health')
}

export function getRecentExecutions(limit = 10) {
  return client.get('/scheduler/executions', { params: { limit } })
}
