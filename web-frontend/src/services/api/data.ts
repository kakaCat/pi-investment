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
  type: string
  source: string
  scope: 'hs300' | 'watchlist' | 'portfolio' | 'all'
  days: number
  status: 'queued' | 'running' | 'success' | 'failed' | 'cancelled'
  total: number
  success: number
  failed: number
  progress: number
  createdAt: string
  completedAt?: string
  forceUpdate: boolean
  params?: Record<string, any>
  result?: Record<string, any>
  error?: string
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

// ========== 数据转换辅助函数 ==========

/**
 * 将后端任务格式 ({ id, type, status, params, result, createdAt, finishedAt, ... })
 * 转换为前端 DataUpdateJob 格式
 */
export function mapJobToDataUpdateJob(raw: any): DataUpdateJob {
  // Normalize: params may be nested or at top level (legacy compat)
  const params = raw.params || {}
  const result = raw.result || {}
  const total = result.total || 0
  const succeeded = result.succeeded || 0
  const failedCount = result.failed || 0

  // 计算进度
  let progress = 0
  const rawStatus = raw.status || 'queued'
  if (rawStatus === 'completed' || rawStatus === 'success') {
    progress = 100
  } else if (total > 0) {
    progress = Math.round((succeeded / total) * 100)
  }

  // Read params fields, with top-level fallback for legacy jobs
  const jobSource = params.source || raw.source || raw.type || 'unknown'
  const jobDays = params.days || raw.days || 0
  const jobForce = params.force || raw.force || false
  const scope = (['hs300', 'watchlist', 'portfolio', 'all'].includes(jobSource) ? jobSource : 'all') as DataUpdateJob['scope']

  // Normalize status: backend 'completed'/'pending' → frontend 'success'/'queued'
  let status = rawStatus
  if (status === 'completed') {
    status = failedCount > 0 ? 'failed' : 'success'
  }
  if (status === 'pending') status = 'queued'

  return {
    jobId: raw.id || raw.jobId || '',
    type: raw.type || 'unknown',
    source: jobSource,
    scope,
    days: jobDays,
    status,
    total,
    success: succeeded,
    failed: failedCount,
    progress,
    forceUpdate: jobForce,
    createdAt: raw.createdAt || '',
    completedAt: raw.finishedAt || raw.completedAt || undefined,
    params,
    result,
    error: raw.error || undefined
  }
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
  async startUpdate(request: StartUpdateRequest) {
    const response = await apiClient.post<{ success: boolean; job_id: string; message: string }>('/api/data/update', {
      source: request.scope,
      days: request.days,
      force: request.forceUpdate ?? false,
      async: true
    })
    // 转换后端格式 job_id -> jobId
    return { jobId: response?.job_id }
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
   * 后端返回: { success: true, jobs: [...], count: N }
   * 适配为: PaginatedResponse<DataUpdateJob>
   */
  getJobs(params?: PaginationParams) {
    return apiClient.get<any>('/api/jobs', { params })
      .then((response) => {
        const jobsList: any[] = response.jobs || []
        const pageSize = params?.pageSize || 20
        const total = response.count || 0
        return {
          items: jobsList.map(mapJobToDataUpdateJob),
          total,
          page: params?.page || 1,
          pageSize,
          totalPages: Math.ceil(total / pageSize)
        } as PaginatedResponse<DataUpdateJob>
      })
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
  },

  /**
   * 重试失败的任务
   */
  retryJob(jobId: string) {
    return apiClient.post(`/api/jobs/${jobId}/retry`)
  },

  /**
   * 取消运行中的任务
   */
  cancelJob(jobId: string) {
    return apiClient.post(`/api/jobs/${jobId}/cancel`)
  }
}
