import { apiClient } from './client'
import type { PaginatedResponse, PaginationParams } from '@/types'

// ========== 数据更新相关类型 ==========

export interface DataSource {
  id: string
  name: string
  type: 'stock' | 'index' | 'fund' | 'macro' | 'news'
  status: 'idle' | 'updating' | 'success' | 'failed'
  lastUpdateTime?: string
  nextUpdateTime?: string
  updateFrequency: string // e.g., 'daily', 'hourly', 'realtime'
  dataCount: number
  progress?: number // 0-100
  errorMessage?: string
}

export interface DataUpdateJob {
  jobId: string
  source: string
  scope: 'hs300' | 'watchlist' | 'portfolio' | 'all'
  days: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  total: number
  success: number
  failed: number
  createdAt: string
  completedAt?: string
  forceUpdate: boolean
}

export interface DataUpdateLog {
  id: string
  timestamp: string
  source: string
  action: string
  status: 'success' | 'failed' | 'running'
  duration?: number // 秒
  dataCount?: number
  errorMessage?: string
}

export interface DataUpdateStats {
  totalSources: number
  updating: number
  todayUpdates: number
  failed: number
}

export interface StartUpdateRequest {
  scope: 'hs300' | 'watchlist' | 'portfolio' | 'all'
  days: number
  forceUpdate?: boolean
}

export interface DataUpdateLogsRequest extends PaginationParams {
  source?: string
  status?: string
  startDate?: string
  endDate?: string
}

// ========== API 方法 ==========

export const dataApi = {
  /**
   * 获取数据源列表
   */
  getDataSources() {
    return apiClient.get<DataSource[]>('/api/data/sources')
  },

  /**
   * 获取数据更新统计
   */
  getStats() {
    return apiClient.get<DataUpdateStats>('/api/data/stats')
  },

  /**
   * 开始数据更新
   */
  startUpdate(request: StartUpdateRequest) {
    return apiClient.post<{ jobId: string }>('/api/data/update', {
      source: request.scope,
      days: request.days,
      force: request.forceUpdate ?? false,
      async: true
    })
  },

  /**
   * 停止所有更新任务
   */
  stopAllUpdates() {
    return apiClient.post('/api/data/update/stop-all')
  },

  /**
   * 立即更新指定数据源
   */
  updateSource(sourceId: string) {
    return apiClient.post(`/api/data/sources/${sourceId}/update`)
  },

  /**
   * 获取更新任务列表
   */
  getJobs(params?: PaginationParams) {
    return apiClient.get<PaginatedResponse<DataUpdateJob>>('/api/data/jobs', { params })
  },

  /**
   * 获取更新日志
   */
  getLogs(params?: DataUpdateLogsRequest) {
    return apiClient.get<PaginatedResponse<DataUpdateLog>>('/api/data/logs', { params })
  },

  /**
   * 获取数据源配置
   */
  getSourceConfig(sourceId: string) {
    return apiClient.get(`/api/data/sources/${sourceId}/config`)
  },

  /**
   * 更新数据源配置
   */
  updateSourceConfig(sourceId: string, config: any) {
    return apiClient.put(`/api/data/sources/${sourceId}/config`, config)
  }
}
