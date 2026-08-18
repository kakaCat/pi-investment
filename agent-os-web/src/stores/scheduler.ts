import { defineStore } from 'pinia'
import { ref } from 'vue'
import { schedulerApi } from '@/api/scheduler'
import type { Task, TaskRun } from '@/types/api'

export const useSchedulerStore = defineStore('scheduler', () => {
  const tasks = ref<Task[]>([])
  const executions = ref<TaskRun[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 获取任务列表
  async function fetchTasks() {
    loading.value = true
    error.value = null
    try {
      const result = await schedulerApi.listTasks()
      tasks.value = result.tasks || []
    } catch (e: any) {
      error.value = e.message || '加载任务失败'
      console.error('加载任务失败:', e)
    } finally {
      loading.value = false
    }
  }

  // 获取执行历史
  async function fetchExecutions(taskId?: string, limit = 50) {
    loading.value = true
    error.value = null
    try {
      if (taskId) {
        const result = await schedulerApi.listExecutions(taskId, { limit })
        executions.value = result.runs || []
      } else {
        // 获取所有任务的执行历史
        const allExecutions: TaskRun[] = []
        for (const task of tasks.value) {
          const result = await schedulerApi.listExecutions(task.id, { limit: 10 })
          if (result.runs) {
            allExecutions.push(...result.runs)
          }
        }
        executions.value = allExecutions.sort((a, b) => 
          (b.started_at || '').localeCompare(a.started_at || '')
        )
      }
    } catch (e: any) {
      error.value = e.message || '加载执行历史失败'
      console.error('加载执行历史失败:', e)
    } finally {
      loading.value = false
    }
  }

  // 创建任务
  async function createTask(data: Partial<Task>) {
    try {
      await schedulerApi.createTask(data)
      await fetchTasks()
      return true
    } catch (e: any) {
      error.value = e.message || '创建任务失败'
      console.error('创建任务失败:', e)
      return false
    }
  }

  // 更新任务
  async function updateTask(id: string, data: Partial<Task>) {
    try {
      await schedulerApi.updateTask(id, data)
      await fetchTasks()
      return true
    } catch (e: any) {
      error.value = e.message || '更新任务失败'
      console.error('更新任务失败:', e)
      return false
    }
  }

  // 删除任务
  async function deleteTask(id: string) {
    try {
      await schedulerApi.deleteTask(id)
      await fetchTasks()
      return true
    } catch (e: any) {
      error.value = e.message || '删除任务失败'
      console.error('删除任务失败:', e)
      return false
    }
  }

  // 触发任务执行
  async function triggerTask(id: string) {
    try {
      await schedulerApi.triggerTask(id)
      return true
    } catch (e: any) {
      error.value = e.message || '触发任务失败'
      console.error('触发任务失败:', e)
      return false
    }
  }

  // 暂停任务
  async function pauseTask(id: string) {
    try {
      await schedulerApi.pauseTask(id)
      await fetchTasks()
      return true
    } catch (e: any) {
      error.value = e.message || '暂停任务失败'
      console.error('暂停任务失败:', e)
      return false
    }
  }

  // 恢复任务
  async function resumeTask(id: string) {
    try {
      await schedulerApi.resumeTask(id)
      await fetchTasks()
      return true
    } catch (e: any) {
      error.value = e.message || '恢复任务失败'
      console.error('恢复任务失败:', e)
      return false
    }
  }

  return {
    // 状态
    tasks,
    executions,
    loading,
    error,
    // 方法
    fetchTasks,
    fetchExecutions,
    createTask,
    updateTask,
    deleteTask,
    triggerTask,
    pauseTask,
    resumeTask,
  }
})
