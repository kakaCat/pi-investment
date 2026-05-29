import { apiClient } from './client'
import type {
  Indicator,
  IndicatorBacktest,
  PaginatedResponse
} from '@/types'
import type {
  IndicatorInfo,
  IndicatorListResponse,
  IndicatorRunResult,
  IndicatorRunParams,
  StrategyNotebook
} from '@/types/indicator'

type IndicatorUpdatePayload = Partial<Indicator> & {
  notebook?: StrategyNotebook
}

export const indicatorApi = {
  /**
   * 获取指标列表
   */
  getIndicators(params?: any) {
    return apiClient.get<IndicatorListResponse>('/api/indicators/list', { params })
  },

  /**
   * 获取指标详情
   */
  getIndicatorById(indicatorId: string) {
    return apiClient.get<IndicatorInfo>(`/api/indicators/detail/${indicatorId}`)
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
  updateIndicator(indicatorId: string, data: IndicatorUpdatePayload) {
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
  runIndicator(indicatorId: string, options: IndicatorRunParams) {
    return apiClient.post<IndicatorRunResult>(`/api/indicators/run/${indicatorId}`, options)
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
  getMyIndicators(params?: Record<string, any>) {
    return apiClient.get<PaginatedResponse<Indicator>>('/api/indicators/list', {
      params: { type: 'my', pageSize: 200, ...params }
    })
      .then(response => (response as any).items ?? [])
  },

  /**
   * 获取系统指标
   */
  getSystemIndicators(params?: Record<string, any>) {
    return apiClient.get<PaginatedResponse<Indicator>>('/api/indicators/list', {
      params: { type: 'system', pageSize: 200, ...params }
    })
      .then(response => (response as any).items ?? [])
  },

  /**
   * 获取社区指标
   */
  getCommunityIndicators(params?: any) {
    return apiClient.get<PaginatedResponse<Indicator>>('/api/indicators/list', { params: { ...params, isPublic: true } })
  },

  /**
   * 发布指标到社区
   */
  publishIndicator(indicatorId: string) {
    return apiClient.post<{ id: string; published: boolean }>(`/api/indicators/publish/${indicatorId}`)
  },

  /**
   * 收藏指标
   */
  favoriteIndicator(indicatorId: string) {
    return apiClient.post<{ id: string; favorite: boolean; favoriteCount: number }>(`/api/indicators/favorite/${indicatorId}`)
  },

  /**
   * 取消收藏指标
   */
  unfavoriteIndicator(indicatorId: string) {
    return apiClient.post<{ id: string; favorite: boolean; favoriteCount: number }>(`/api/indicators/unfavorite/${indicatorId}`)
  }
}
