import { apiClient } from './client'
import { toPaginatedResponse } from './adapters'
import type {
  BacktestRequest,
  BacktestResponse,
  FactorAnalysis,
  Opportunity,
  OpportunityFilters,
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
  scanOpportunities(filters?: OpportunityFilters) {
    return apiClient.post<Opportunity[]>('/api/signals/scan', filters)
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
