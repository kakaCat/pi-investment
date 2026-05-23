import { apiClient } from './client'
import type { TradingSignal, SignalFilters, SignalStatistics, PaginatedResponse } from '@/types/models'

export const signalApi = {
  /**
   * 获取信号列表
   */
  getSignals(filters?: SignalFilters) {
    return apiClient.get<PaginatedResponse<TradingSignal>>('/api/signals', { params: filters })
  },

  /**
   * 获取单个信号详情
   */
  getSignalById(id: string) {
    return apiClient.get<TradingSignal>(`/api/signals/${id}`)
  },

  /**
   * 批准信号
   */
  approveSignal(id: string) {
    return apiClient.post(`/api/signals/${id}/approve`)
  },

  /**
   * 拒绝信号
   */
  rejectSignal(id: string, reason: string) {
    return apiClient.post(`/api/signals/${id}/reject`, { reason })
  },

  /**
   * 标记错误信号
   */
  markError(id: string, errorType: string) {
    return apiClient.post(`/api/signals/${id}/mark-error`, { errorType })
  },

  /**
   * 获取信号统计
   */
  getStatistics(dateRange?: { start: string; end: string }) {
    return apiClient.get<SignalStatistics>('/api/signals/statistics', { params: dateRange })
  },

  /**
   * 复现验证信号
   */
  verifySignal(id: string) {
    return apiClient.post(`/api/signals/${id}/verify`)
  }
}
