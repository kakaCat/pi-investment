import { apiClient } from './client'

export interface StageStatus {
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  detail: string
  startTime?: string
  endTime?: string
}

export interface PipelineConfig {
  stockRange?: string
  days: number
  model: string
  threshold: number
}

export interface PipelineRun {
  runId: string
  startTime: string
  endTime?: string
  stockCount: number
  model: string
  status: 'running' | 'completed' | 'failed'
  signalCount: number | null
  bestReturn: number | null
  riskLevel: 'low' | 'medium' | 'high' | null
  duration: number
  config: PipelineConfig
  stages: StageStatus[]
  logs: string[]
  error?: string
}

export interface PipelineHistoryResult {
  items: PipelineRun[]
  pagination: {
    page: number
    pageSize: number
    total: number
    totalPages: number
  }
}

/** 后端 runs/list 原始返回结构（来自 quantsys-v2 api_response） */
interface RunsListRaw {
  runs?: PipelineRun[]
  items?: PipelineRun[]
  total?: number
  page?: number
  pageSize?: number
  [key: string]: any
}

export const pipelineApi = {
  /**
   * 触发流水线 → POST /api/pipeline/trigger
   * apiClient 自动解包 { success, data } → 返回 PipelineRun
   */
  async runPipeline(config: PipelineConfig): Promise<PipelineRun> {
    return apiClient.post<PipelineRun>('/api/pipeline/trigger', config)
  },

  /**
   * 获取任务列表 → GET /api/pipeline/tasks/list
   * apiClient 自动解包 { success, data } → 返回 { items }
   */
  async getTasks(params?: { limit?: number; page?: number; pageSize?: number }): Promise<any> {
    return apiClient.get('/api/pipeline/tasks/list', { params })
  },

  /**
   * 获取运行历史 → GET /api/pipeline/runs/list
   * 适配后端返回格式为 PipelineHistoryResult
   */
  async getHistory(page: number = 1, pageSize: number = 20): Promise<PipelineHistoryResult> {
    const result: RunsListRaw = await apiClient.get<RunsListRaw>('/api/pipeline/runs/list', {
      params: { page, pageSize }
    })
    const items = result.runs || result.items || []
    const total = result.total || 0
    return {
      items,
      pagination: {
        page: result.page || page,
        pageSize: result.pageSize || pageSize,
        total,
        totalPages: Math.ceil(total / (result.pageSize || pageSize)) || 0
      }
    }
  },

  /**
   * 获取运行列表（原始格式，供测试和直接消费使用）
   * → GET /api/pipeline/runs/list
   */
  async getRuns(params?: { limit?: number; page?: number; pageSize?: number }): Promise<any> {
    return apiClient.get('/api/pipeline/runs/list', { params })
  },

  /**
   * 运行详情 → GET /api/pipeline/runs/list?runId=xxx（降级方案）
   * 后端无单独详情端点，从列表查找
   */
  async getRun(runId: string): Promise<PipelineRun> {
    const result: RunsListRaw = await apiClient.get<RunsListRaw>('/api/pipeline/runs/list', {
      params: { runId, pageSize: 1 }
    })
    const run = result?.items?.[0] || result?.runs?.[0]
    if (!run) throw new Error('运行记录未找到')
    return run
  },

  /**
   * 统计信息 → GET /api/pipeline/statistics
   * apiClient 自动解包 { success, data } → 返回统计数据
   */
  async getStatistics(): Promise<any> {
    return apiClient.get('/api/pipeline/statistics')
  }
}
