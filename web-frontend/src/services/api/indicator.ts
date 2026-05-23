import { apiClient } from './client'
import type {
  Indicator,
  IndicatorBacktest,
  PaginatedResponse
} from '@/types'

export const indicatorApi = {
  /**
   * 获取指标列表
   */
  getIndicators(params?: any) {
    return apiClient.get<PaginatedResponse<Indicator>>('/api/indicators/list', { params })
  },

  /**
   * 获取指标详情
   */
  getIndicatorById(indicatorId: string) {
    return apiClient.get<Indicator>(`/api/indicators/detail/${indicatorId}`)
  },

  /**
   * 创建指标
   */
  createIndicator(data: Partial<Indicator>) {
    return apiClient.post<Indicator>('/api/indicators/create', data)
  },

  /**
   * 更新指标
   */
  updateIndicator(indicatorId: string, data: Partial<Indicator>) {
    return apiClient.post<Indicator>(`/api/indicators/update/${indicatorId}`, data)
  },

  /**
   * 删除指标
   */
  deleteIndicator(indicatorId: string) {
    return apiClient.post(`/api/indicators/delete/${indicatorId}`)
  },

  /**
   * 运行指标
   */
  runIndicator(indicatorId: string, symbol: string, params?: any) {
    return apiClient.post(`/api/indicators/run/${indicatorId}`, {
      symbol,
      ...params
    })
  },

  /**
   * 回测指标
   */
  backtestIndicator(data: Partial<IndicatorBacktest>) {
    return apiClient.post<IndicatorBacktest>('/api/indicators/backtest', data)
  },

  /**
   * 获取我的指标
   */
  getMyIndicators() {
    return apiClient.get<PaginatedResponse<Indicator>>('/api/indicators/list')
      .then(response => (response as any).items ?? [])
  },

  /**
   * 获取系统指标
   */
  getSystemIndicators() {
    return Promise.resolve<Indicator[]>([])
  },

  /**
   * 获取社区指标
   */
  getCommunityIndicators(params?: any) {
    return apiClient.get<PaginatedResponse<Indicator>>('/api/indicators/list', { params })
  },

  /**
   * 发布指标到社区
   */
  publishIndicator(indicatorId: string) {
    return Promise.resolve({ id: indicatorId, published: true })
  },

  /**
   * 收藏指标
   */
  favoriteIndicator(indicatorId: string) {
    return Promise.resolve({ id: indicatorId, favorite: true })
  },

  /**
   * 取消收藏指标
   */
  unfavoriteIndicator(indicatorId: string) {
    return Promise.resolve({ id: indicatorId, favorite: false })
  }
}
