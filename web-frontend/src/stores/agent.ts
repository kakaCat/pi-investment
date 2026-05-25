import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AgentLog } from '@/types'
import { agentApi } from '@/services/api/agent'

export const useAgentStore = defineStore('agent', () => {
  // State
  const logs = ref<AgentLog[]>([])
  const currentLog = ref<AgentLog | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const isRunning = ref(false)
  const performance = ref({
    totalSignals: 0,
    approvedSignals: 0,
    executedSignals: 0,
    accuracy: 0,
    avgReturn: 0,
    sharpeRatio: 0,
    maxDrawdown: 0,
    winRate: 0,
    avgHoldingDays: 0
  })

  // Getters
  const recentLogs = computed(() => logs.value.slice(0, 10))

  const successLogs = computed(() =>
    logs.value.filter(log => log.status === 'success')
  )

  const failedLogs = computed(() =>
    logs.value.filter(log => log.status === 'failed')
  )

  const successRate = computed(() => {
    const total = logs.value.length
    if (total === 0) return 0
    return (successLogs.value.length / total) * 100
  })

  // Actions
  const fetchLogs = async (params?: any) => {
    loading.value = true
    error.value = null
    try {
      const response = await agentApi.getLogs(params)
      logs.value = response.items
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const fetchLogById = async (id: string) => {
    loading.value = true
    error.value = null
    try {
      currentLog.value = await agentApi.getLogById(id)
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const fetchPerformance = async (startDate: string, endDate: string) => {
    loading.value = true
    error.value = null
    try {
      performance.value = await agentApi.getPerformance({ startDate, endDate })
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  const addLog = (log: AgentLog) => {
    logs.value.unshift(log)
  }

  const startAgent = async () => {
    try {
      // TODO: 调用API启动Agent
      isRunning.value = true
    } catch (e: any) {
      error.value = e.message
      throw e
    }
  }

  const stopAgent = async () => {
    try {
      // TODO: 调用API停止Agent
      isRunning.value = false
    } catch (e: any) {
      error.value = e.message
      throw e
    }
  }

  return {
    // State
    logs,
    currentLog,
    loading,
    error,
    isRunning,
    performance,
    // Getters
    recentLogs,
    successLogs,
    failedLogs,
    successRate,
    // Actions
    fetchLogs,
    fetchLogById,
    fetchPerformance,
    addLog,
    startAgent,
    stopAgent
  }
})
