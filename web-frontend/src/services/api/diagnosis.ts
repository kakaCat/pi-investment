import { apiClient } from './client'

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
  benchmark: {
    name: string
    annualReturn: number
    sharpeRatio: number
    maxDrawdown: number
  }
  ratings: {
    overall: 'A' | 'B' | 'C' | 'D'
    return: string
    risk: string
    stability: string
  }
  diagnosis: {
    conclusion: string
    strengths: string[]
    weaknesses: string[]
    suggestions: string[]
  }
  reportPath: string
}

/**
 * 运行策略诊断
 */
export function runDiagnosis(params: DiagnosisParams): Promise<DiagnosisResult> {
  return apiClient.post<DiagnosisResult>('/api/diagnosis/run', params)
}

/**
 * 健康检查
 */
export function diagnosisHealth(): Promise<{ status: string; timestamp: string }> {
  return apiClient.get('/api/diagnosis/health')
}

export const diagnosisApi = {
  runDiagnosis,
  diagnosisHealth
}
