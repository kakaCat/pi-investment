import { apiClient } from './client'
import type {
  Strategy,
  CreateStrategyRequest,
  UpdateStrategyRequest,
  StrategyListRequest,
  PaginatedResponse
} from '@/types'

export const strategyApi = {
  /**
   * 获取策略列表
   */
  getStrategies(params?: StrategyListRequest) {
    return apiClient.get<PaginatedResponse<Strategy>>('/api/strategies/list', { params })
  },

  /**
   * 获取策略详情
   */
  getStrategyById(strategyId: string) {
    return apiClient.get<Strategy>(`/api/strategies/detail/${strategyId}`)
  },

  /**
   * 创建策略
   */
  createStrategy(data: CreateStrategyRequest) {
    return apiClient.post<Strategy>('/api/strategies/create', data)
  },

  /**
   * 更新策略
   */
  updateStrategy(data: UpdateStrategyRequest) {
    return apiClient.post<Strategy>(`/api/strategies/update/${data.id}`, data)
  },

  /**
   * 删除策略
   */
  deleteStrategy(strategyId: string) {
    return apiClient.post(`/api/strategies/delete/${strategyId}`)
  },

  /**
   * 启动策略
   */
  startStrategy(strategyId: string) {
    return apiClient.post(`/api/strategies/start/${strategyId}`)
  },

  /**
   * 停止策略
   */
  stopStrategy(strategyId: string) {
    return apiClient.post(`/api/strategies/stop/${strategyId}`)
  },

  /**
   * 暂停策略
   */
  pauseStrategy(strategyId: string) {
    return apiClient.post(`/api/strategies/${strategyId}/pause`)
  },

  /**
   * 恢复策略
   */
  resumeStrategy(strategyId: string) {
    return apiClient.post(`/api/strategies/${strategyId}/resume`)
  },

  /**
   * 获取策略绩效
   */
  getStrategyPerformance(strategyId: string, startDate?: string, endDate?: string) {
    return apiClient.get(`/api/strategies/performance/${strategyId}`, {
      params: { startDate, endDate }
    })
  },

  /**
   * 获取策略持仓
   */
  getStrategyPositions(strategyId: string) {
    return apiClient.get(`/api/strategies/${strategyId}/positions`)
  },

  /**
   * 获取策略订单
   */
  getStrategyOrders(strategyId: string) {
    return apiClient.get(`/api/strategies/${strategyId}/orders`)
  },

  /**
   * 获取策略日志
   */
  getStrategyLogs(strategyId: string, params?: any) {
    return apiClient.get(`/api/strategies/${strategyId}/logs`, { params })
  }
}
