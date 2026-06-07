/**
 * 调度器业务逻辑 Composable
 * 封装所有 API 调用和状态管理
 */

import { ref, reactive, computed, onUnmounted, getCurrentInstance } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiClient } from '@/services/api/client'
import type {
  Task,
  TaskForm,
  TaskStats,
  TaskLevelStat,
  TaskLevelGroup,
  HistoryRecord,
  HistoryLevelStat,
  BackendTaskListResponse,
  BackendRunListResponse,
  TASK_LEVEL_ORDER,
  HISTORY_LEVEL_ORDER
} from '@/types/scheduler'
import {
  mapTask,
  mapRun,
  buildTaskRequest,
  isDeletedTaskSummary
} from '@/services/scheduler/mappers'

/**
 * 获取响应的分页数据
 */
function getResponsePageItems<T>(
  items: T[],
  page: number,
  pageSize: number,
  hasServerPagination: boolean
): T[] {
  if (hasServerPagination) return items
  const start = (page - 1) * pageSize
  return items.slice(start, start + pageSize)
}

/**
 * 调度器 Composable
 */
export function useScheduler() {
  // ========== 任务列表状态 ==========
  const loading = ref(false)
  const tasks = ref<Task[]>([])
  const taskPage = ref(1)
  const taskPageSize = ref(12)
  const taskTotal = ref(0)
  const taskStats = reactive<TaskStats>({
    enabled: 0,
    paused: 0,
    problem: 0,
  })
  const triggeringTaskIds = ref<Set<string>>(new Set())

  // 轮询定时器
  let pollingTimer: ReturnType<typeof setInterval> | null = null

  // 任务级别顺序
  const taskLevelOrder: typeof TASK_LEVEL_ORDER = ['failed', 'warning', 'paused', 'idle', 'healthy']

  // 任务级别统计
  const taskLevelStats = computed<TaskLevelStat[]>(() =>
    taskLevelOrder.map(level => ({
      level,
      label: getTaskLevelText(level),
      count: tasks.value.filter(task => task.level === level).length,
    }))
  )

  // 是否有任务正在运行
  const hasRunningTasks = computed(() => tasks.value.some(task => task.isRunning))

  // 任务级别分组
  const taskLevelGroups = computed<TaskLevelGroup[]>(() =>
    taskLevelStats.value
      .map(group => ({
        ...group,
        tasks: tasks.value.filter(task => task.level === group.level),
      }))
      .filter(group => group.tasks.length > 0)
  )

  // ========== 运行历史状态 ==========
  const history = ref<HistoryRecord[]>([])
  const historyPage = ref(1)
  const historyPageSize = ref(20)
  const historyTotal = ref(0)

  // 运行级别顺序
  const historyLevelOrder: typeof HISTORY_LEVEL_ORDER = ['failed', 'internal_failed', 'skipped', 'success']

  // 运行级别统计
  const historyLevelStats = computed<HistoryLevelStat[]>(() =>
    historyLevelOrder.map(level => ({
      level,
      label: getRunLevelText(level),
      count: history.value.filter(row => row.status === level).length,
    }))
  )

  // ========== 任务列表操作 ==========

  /**
   * 加载任务列表
   */
  const loadTasks = async () => {
    loading.value = true
    try {
      const result = await apiClient.get('/api/scheduler/tasks', {
        params: {
          page: taskPage.value,
          pageSize: taskPageSize.value,
        },
      }) as BackendTaskListResponse

      const list = (result.tasks || []).filter(item => !isDeletedTaskSummary(item))
      const pagination = result.pagination || {}
      const hasServerPagination = Boolean(result.pagination || result.total !== undefined || result.count !== undefined)
      const pageItems = getResponsePageItems(list, taskPage.value, taskPageSize.value, hasServerPagination)

      tasks.value = pageItems.map(mapTask)
      taskTotal.value = hasServerPagination
        ? Number(result.total ?? result.count ?? (pagination as any).total ?? list.length)
        : list.length

      // 更新统计
      taskStats.enabled = tasks.value.filter(task => task.enabled).length
      taskStats.paused = tasks.value.filter(task => !task.enabled).length
      taskStats.problem = tasks.value.filter(task => task.level === 'failed' || task.level === 'warning').length

      // 检查是否需要启动轮询
      checkAndStartPolling()
    } catch (error) {
      console.error('加载调度任务失败:', error)
      ElMessage.error('加载调度任务失败')
    } finally {
      loading.value = false
    }
  }

  /**
   * 切换任务页大小
   */
  const handleTaskPageSizeChange = () => {
    taskPage.value = 1
    loadTasks()
  }

  /**
   * 创建任务
   */
  const createTask = async (form: TaskForm) => {
    const body = buildTaskRequest(form)
    await apiClient.post('/api/scheduler/tasks', body)
    ElMessage.success('任务已创建')
    await loadTasks()
  }

  /**
   * 更新任务
   */
  const updateTask = async (form: TaskForm) => {
    if (!form.id) throw new Error('任务 ID 不能为空')
    const body = buildTaskRequest(form)
    await apiClient.put(`/api/scheduler/tasks/${form.id}`, body)
    ElMessage.success('任务已更新')
    await loadTasks()
  }

  /**
   * 触发任务
   */
  const triggerTask = async (task: Task) => {
    // 幂等性检查：如果任务正在运行或触发请求未完成，禁止重复触发
    if (task.isRunning || triggeringTaskIds.value.has(task.id)) {
      ElMessage.warning(`任务 ${task.name} 正在运行中，请等待完成后再触发`)
      return
    }

    triggeringTaskIds.value = new Set(triggeringTaskIds.value).add(task.id)

    try {
      await apiClient.post(`/api/scheduler/tasks/${task.id}/trigger`)
      ElMessage.success(`任务 ${task.name} 已触发`)
      await loadTasks()
    } catch (error: any) {
      ElMessage.error(error?.message || '触发失败')
    } finally {
      const nextTriggeringTaskIds = new Set(triggeringTaskIds.value)
      nextTriggeringTaskIds.delete(task.id)
      triggeringTaskIds.value = nextTriggeringTaskIds
    }
  }

  const isTaskTriggering = (task: Task) => triggeringTaskIds.value.has(task.id)

  /**
   * 切换任务启用/暂停状态
   */
  const toggleTask = async (task: Task) => {
    const action = task.enabled ? 'disable' : 'enable'
    try {
      await apiClient.post(`/api/scheduler/tasks/${task.id}/${action}`)
      ElMessage.success(`任务已${task.enabled ? '暂停' : '启用'}`)
      await loadTasks()
    } catch (error: any) {
      ElMessage.error(error?.message || '操作失败')
    }
  }

  /**
   * 删除任务
   */
  const deleteTask = async (task: Task) => {
    await ElMessageBox.confirm(`确定要删除任务 ${task.name} 吗？`, '确认删除', {
      type: 'warning',
    })

    try {
      await apiClient.delete(`/api/scheduler/tasks/${task.id}`)
      ElMessage.success('任务已删除')
      await loadTasks()
    } catch (error: any) {
      ElMessage.error(error?.message || '删除失败')
    }
  }

  // ========== 运行历史操作 ==========

  /**
   * 加载执行历史
   */
  const loadHistory = async () => {
    try {
      const result = await apiClient.get('/api/scheduler/runs', {
        params: {
          page: historyPage.value,
          pageSize: historyPageSize.value,
        },
      }) as BackendRunListResponse

      const runs = result.runs || []
      const pagination = result.pagination || {}
      const hasServerPagination = Boolean(result.pagination || result.total !== undefined || result.count !== undefined)
      const pageItems = getResponsePageItems(runs, historyPage.value, historyPageSize.value, hasServerPagination)

      history.value = pageItems.map(mapRun)
      historyTotal.value = Number(result.total ?? result.count ?? (pagination as any).total ?? runs.length)
    } catch (error) {
      console.error('加载执行历史失败:', error)
    }
  }

  /**
   * 切换历史页大小
   */
  const handleHistoryPageSizeChange = () => {
    historyPage.value = 1
    loadHistory()
  }

  // ========== 工具函数 ==========

  /**
   * 获取任务级别文本
   */
  function getTaskLevelText(level: string): string {
    const labels: Record<string, string> = {
      healthy: '正常',
      warning: '需关注',
      failed: '失败',
      paused: '已暂停',
      idle: '待运行',
    }
    return labels[level] || level
  }

  /**
   * 获取运行级别文本
   */
  function getRunLevelText(level: string): string {
    const labels: Record<string, string> = {
      success: '成功',
      failed: '失败',
      internal_failed: '内部失败',
      skipped: '跳过',
    }
    return labels[level] || level
  }

  // ========== 轮询逻辑 ==========

  /**
   * 开始轮询（当有任务运行时）
   */
  const startPolling = () => {
    if (pollingTimer) return

    pollingTimer = setInterval(() => {
      if (hasRunningTasks.value) {
        loadTasks() // 静默刷新
        loadHistory() // 同时刷新历史
      } else {
        stopPolling() // 没有运行任务时停止轮询
      }
    }, 3000) // 每 3 秒刷新一次
  }

  /**
   * 停止轮询
   */
  const stopPolling = () => {
    if (pollingTimer) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }
  }

  /**
   * 检查并启动轮询
   */
  const checkAndStartPolling = () => {
    if (hasRunningTasks.value) {
      startPolling()
    } else {
      stopPolling()
    }
  }

  // 清理定时器
  if (getCurrentInstance()) {
    onUnmounted(() => {
      stopPolling()
    })
  }

  return {
    // 任务列表
    loading,
    tasks,
    taskPage,
    taskPageSize,
    taskTotal,
    taskStats,
    taskLevelStats,
    taskLevelGroups,
    loadTasks,
    handleTaskPageSizeChange,
    createTask,
    updateTask,
    triggerTask,
    isTaskTriggering,
    toggleTask,
    deleteTask,

    // 运行历史
    history,
    historyPage,
    historyPageSize,
    historyTotal,
    historyLevelStats,
    loadHistory,
    handleHistoryPageSizeChange,

    // 工具函数
    getTaskLevelText,
    getRunLevelText,
  }
}
