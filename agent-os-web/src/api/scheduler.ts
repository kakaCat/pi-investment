import client from '@/utils/request'
import type { Task, TaskRun } from '@/types'

export const schedulerApi = {
  listTasks: (params?: any) => client.get('/scheduler/tasks', { params }),
  getTask: (id: string) => client.get(`/scheduler/tasks/${id}`),
  createTask: (data: any) => client.post('/scheduler/tasks', data),
  updateTask: (id: string, data: any) => client.put(`/scheduler/tasks/${id}`, data),
  deleteTask: (id: string) => client.delete(`/scheduler/tasks/${id}`),
  triggerTask: (id: string) => client.post(`/scheduler/tasks/${id}/trigger`),
  pauseTask: (id: string) => client.post(`/scheduler/tasks/${id}/pause`),
  resumeTask: (id: string) => client.post(`/scheduler/tasks/${id}/resume`),
  listExecutions: (params?: { task_id?: string; limit?: number }) => client.get('/scheduler/executions', { params }),
}
