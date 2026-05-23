import { apiClient } from './client'
import type {
  AgentLog,
  AgentLogRequest,
  AgentPerformanceRequest,
  AgentPerformanceResponse,
  PaginatedResponse
} from '@/types'

export const agentApi = {
  /**
   * 获取Agent日志列表
   */
  getLogs(params?: AgentLogRequest) {
    return apiClient.get<PaginatedResponse<AgentLog>>('/api/agent/logs', { params })
  },

  /**
   * 获取Agent日志详情
   */
  getLogById(logId: string) {
    return apiClient.get<AgentLog>(`/api/agent/logs/${logId}`)
  },

  /**
   * 获取Agent绩效
   */
  getPerformance(params: AgentPerformanceRequest) {
    return apiClient.get<AgentPerformanceResponse>('/api/agent/performance', { params })
  },

  /**
   * 获取Agent状态
   */
  getStatus() {
    return apiClient.get('/api/agent/status')
  },

  /**
   * 启动Agent
   */
  startAgent() {
    return apiClient.post('/api/agent/start')
  },

  /**
   * 停止Agent
   */
  stopAgent() {
    return apiClient.post('/api/agent/stop')
  },

  /**
   * 暂停Agent
   */
  pauseAgent() {
    return apiClient.post('/api/agent/pause')
  },

  /**
   * 恢复Agent
   */
  resumeAgent() {
    return apiClient.post('/api/agent/resume')
  },

  /**
   * 获取Agent配置
   */
  getConfig() {
    return apiClient.get('/api/agent/config')
  },

  /**
   * 更新Agent配置
   */
  updateConfig(config: any) {
    return apiClient.put('/api/agent/config', config)
  },

  /**
   * 获取Agent统计
   */
  getStatistics(startDate?: string, endDate?: string) {
    return apiClient.get('/api/agent/statistics', {
      params: { startDate, endDate }
    })
  },

  /**
   * 手动触发Agent分析
   */
  triggerAnalysis(symbol: string) {
    return apiClient.post('/api/agent/analyze', { symbol })
  }
}
