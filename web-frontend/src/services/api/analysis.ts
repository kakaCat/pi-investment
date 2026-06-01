import { apiClient } from './client'
import { toPaginatedResponse } from './adapters'
import type {
  BacktestRequest,
  BacktestResponse,
  FactorAnalysis,
  Opportunity,
  OpportunityFilters,
  OpportunityScanResponse,
  PaginatedResponse
} from '@/types'

export const analysisApi = {
  /**
   * 运行回测
   */
  runBacktest(data: BacktestRequest) {
    return apiClient.post<BacktestResponse>('/api/backtest', data)
  },

  /**
   * 获取回测结果
   */
  getBacktestResult(backtestId: string) {
    return apiClient.get<BacktestResponse>('/api/backtest/results', { params: { id: backtestId } })
  },

  /**
   * 获取回测历史
   */
  getBacktestHistory(params?: any) {
    return apiClient.get<PaginatedResponse<BacktestResponse>>('/api/backtest/history', { params })
  },

  /**
   * 获取因子分析
   */
  getFactorAnalysis(symbols: string[]) {
    return apiClient.post<FactorAnalysis[]>('/api/compute/factors', { symbols })
  },

  /**
   * 获取单个股票因子分析
   */
  getStockFactorAnalysis(symbol: string) {
    return apiClient.get<FactorAnalysis>(`/api/stock/${symbol}/factors`)
  },

  /**
   * 机会雷达扫描
   */
  async scanOpportunities(filters?: OpportunityFilters): Promise<OpportunityScanResponse> {
    const response = await apiClient.post<any>('/api/signals/scan', filters)
    return {
      success: response.success !== false,
      scanMode: response.scanMode ?? response.scan_mode ?? 'score',
      opportunities: (response.opportunities ?? []).map(adaptOpportunity),
      total: Number(response.total ?? response.opportunities?.length ?? 0),
      scanned: Number(response.scanned ?? 0),
      strategyId: response.strategyId ?? response.strategy_id,
      sectorInfo: response.sectorInfo ?? response.sector_info
    }
  },

  /**
   * 获取机会列表
   */
  async getOpportunities(params?: any) {
    const response = await apiClient.get('/api/signals', { params })
    return toPaginatedResponse<Opportunity>(response, 'signals')
  },

  /**
   * 获取机会详情
   */
  getOpportunityDetail(opportunityId: string) {
    return apiClient.get<Opportunity>(`/api/signals/detail/${opportunityId}`)
  },

  /**
   * 技术分析
   */
  getTechnicalAnalysis(symbol: string) {
    return apiClient.get(`/api/stock/${symbol}/technical`)
  },

  /**
   * 基本面分析
   * TODO: Backend endpoint not implemented yet
   */
  getFundamentalAnalysis(symbol: string) {
    return apiClient.get(`/api/analysis/fundamental/${symbol}`)
  },

  /**
   * 情绪分析
   * TODO: Backend endpoint not implemented yet
   */
  getSentimentAnalysis(symbol: string) {
    return apiClient.get(`/api/analysis/sentiment/${symbol}`)
  },

  /**
   * 相关性分析
   * TODO: Backend endpoint not implemented yet
   */
  getCorrelationAnalysis(symbols: string[]) {
    return apiClient.post('/api/analysis/correlation', { symbols })
  },

  /**
   * 行业分析
   * TODO: Backend endpoint not implemented yet
   */
  getIndustryAnalysis(industry: string) {
    return apiClient.get(`/api/analysis/industry/${industry}`)
  }
}

function adaptOpportunity(raw: any): Opportunity {
  const confidence = Number(raw.confidence ?? 0)
  return {
    id: String(raw.id ?? `${raw.strategy_id ?? raw.strategyId ?? 'scan'}-${raw.symbol ?? ''}-${raw.timestamp ?? raw.created_at ?? raw.createdAt ?? ''}`),
    symbol: raw.symbol ?? '',
    symbolName: raw.symbolName ?? raw.symbol_name ?? raw.name ?? raw.symbol ?? '',
    score: Number(raw.score ?? 0),
    technicalScore: Number(raw.technicalScore ?? raw.technical_score ?? 0),
    fundamentalScore: Number(raw.fundamentalScore ?? raw.fundamental_score ?? 0),
    sentimentScore: Number(raw.sentimentScore ?? raw.sentiment_score ?? raw.capital_score ?? 0),
    reasons: raw.reasons ?? (raw.reason ? [raw.reason] : []),
    riskLevel: raw.riskLevel ?? raw.risk_level ?? 'medium',
    expectedReturn: Number(raw.expectedReturn ?? raw.expected_return ?? 0),
    confidence: confidence <= 1 ? confidence * 100 : confidence,
    createdAt: raw.createdAt ?? raw.created_at ?? raw.timestamp ?? raw.signal_date ?? '',
    strategyId: raw.strategyId ?? raw.strategy_id,
    strategyName: raw.strategyName ?? raw.strategy_name,
    price: raw.price !== undefined ? Number(raw.price) : undefined
  }
}
