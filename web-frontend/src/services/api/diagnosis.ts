import { apiClient } from './client'

function compactParams(params: Record<string, any>) {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
  )
}

export interface DiagnosisParams {
  backtestId?: string
  symbol: string
  startDate: string
  endDate: string
  strategyName: string
  benchmark?: string
}

export interface DiagnosisResult {
  diagnosisId: string
  timestamp: string
  strategy: {
    name: string
    symbol: string
    period: string
  }
  metrics: {
    annualReturn: number
    sharpeRatio: number
    maxDrawdown: number
    winRate: number
    totalTrades: number
  }
  benchmark?: {
    name: string
    annualReturn: number
    sharpeRatio: number
    maxDrawdown: number
  }
  ratings: {
    overall: 'A' | 'B' | 'C' | 'D'
    return: 'excellent' | 'good' | 'moderate' | 'poor'
    risk: 'low' | 'moderate' | 'high'
    stability: 'excellent' | 'good' | 'moderate' | 'poor'
  }
  diagnosis: {
    conclusion: string
    strengths: string[]
    weaknesses: string[]
    suggestions: string[]
  }
  reportPath: string
}

export interface DiagnosisHealthResponse {
  status: string
  service: string
  version: string
}

/**
 * 运行策略诊断
 */
export function runDiagnosis(params: DiagnosisParams): Promise<DiagnosisResult> {
  return apiClient.post<DiagnosisResult>('/api/diagnosis/run', compactParams(params))
    .catch(error => {
      if (error?.response?.status === 400) {
        throw new Error('诊断参数无效')
      }
      if (error?.response?.status === 404) {
        throw new Error('回测数据不存在')
      }
      throw error
    })
}

/**
 * 健康检查
 */
export function diagnosisHealth(): Promise<DiagnosisHealthResponse> {
  return apiClient.get('/api/diagnosis/health')
}

export const diagnosisApi = {
  runDiagnosis,
  diagnosisHealth
}
