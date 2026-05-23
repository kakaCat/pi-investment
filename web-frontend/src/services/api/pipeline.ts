import { apiClient } from './client'

export interface PipelineTask {
  id: string
  name: string
  type: 'data_update' | 'factor_calc' | 'ml_predict' | 'backtest' | 'risk_assess'
  status: 'pending' | 'running' | 'completed' | 'failed'
  startTime?: string
  endTime?: string
  duration?: number
  progress?: number
  config?: PipelineConfig
  logs?: string[]
  error?: string
  result?: PipelineResult
}

export interface PipelineConfig {
  symbols?: string[]
  days?: number
  model?: 'XGBoost' | 'LightGBM' | 'RandomForest'
  threshold?: number
}

export interface PipelineResult {
  klineCount?: number
  factorCount?: number
  signalCount?: number
  backtestReturn?: number
  riskLevel?: 'low' | 'medium' | 'high'
}

export interface PipelineRun {
  id: string
  runId: string
  startTime: string
  endTime?: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  stockCount: number
  model: string
  signalCount?: number
  backtestReturn?: number
  riskLevel?: string
  duration?: number
  stages: PipelineTask[]
}

export interface PipelineStatistics {
  runningTasks: number
  completedToday: number
  failedTasks: number
  avgDuration: number
}

export const pipelineApi = {
  /**
   * 获取流水线统计
   */
  getStatistics() {
    return apiClient.get<PipelineStatistics>('/api/pipeline/statistics')
  },

  /**
   * 获取流水线任务列表
   */
  getTasks(params?: { status?: string; limit?: number }) {
    return apiClient.get<PipelineTask[]>('/api/pipeline/tasks/list', { params })
  },

  /**
   * 获取任务详情
   */
  getTaskById(taskId: string) {
    return apiClient.get<PipelineTask>(`/api/pipeline/tasks/${taskId}`)
  },

  /**
   * 获取历史运行记录
   */
  getRuns(params?: { limit?: number; offset?: number }) {
    return apiClient.get<{ runs: PipelineRun[]; total: number }>('/api/pipeline/runs/list', {
      params
    })
  },

  /**
   * 获取运行详情
   */
  getRunById(runId: string) {
    return apiClient.get<PipelineRun>(`/api/pipeline/runs/${runId}`)
  },

  /**
   * 手动触发流水线
   */
  triggerPipeline(config: PipelineConfig) {
    return apiClient.post<{ runId: string }>('/api/pipeline/trigger', config)
  },

  /**
   * 停止任务
   */
  stopTask(taskId: string) {
    return apiClient.post(`/api/pipeline/tasks/${taskId}/stop`)
  },

  /**
   * 重试任务
   */
  retryTask(taskId: string) {
    return apiClient.post(`/api/pipeline/tasks/${taskId}/retry`)
  },

  /**
   * 获取任务日志
   */
  getTaskLogs(taskId: string) {
    return apiClient.get<{ logs: string[] }>(`/api/pipeline/tasks/${taskId}/logs`)
  }
}
