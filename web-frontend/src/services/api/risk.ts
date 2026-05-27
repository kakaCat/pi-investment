import { apiClient } from './client'
import type {
  RiskCheckRequest,
  RiskCheckResponse
} from '@/types'

export const riskApi = {
  /**
   * 风险检查
   */
  checkRisk(data: RiskCheckRequest) {
    return apiClient.post<RiskCheckResponse>('/api/risk/check', data)
  },

  /**
   * 获取风险指标
   */
  getRiskMetrics() {
    return apiClient.get('/api/risk/metrics')
  },

  /**
   * 获取风险限额
   */
  getRiskLimits() {
    return apiClient.get('/api/risk/limits')
  },

  /**
   * 更新风险限额
   */
  updateRiskLimits(limits: any) {
    return apiClient.put('/api/risk/limits', limits)
  },

  /**
   * 获取风险报告
   */
  getRiskReport(startDate?: string, endDate?: string) {
    return apiClient.get('/api/risk/report', {
      params: { startDate, endDate }
    })
  },

  /**
   * 获取VaR (Value at Risk)
   */
  getVaR(confidence = 0.95) {
    return apiClient.get('/api/risk/var', {
      params: { confidence }
    })
  },

  /**
   * 获取压力测试结果
   */
  getStressTest() {
    return apiClient.get('/api/risk/stress-test')
  },

  /**
   * 运行压力测试
   */
  runStressTest(scenarios: any[]) {
    return apiClient.post('/api/risk/stress-test', { scenarios })
  },

  /**
   * 获取止损规则列表
   */
  async getStopLossRules(symbol?: string) {
    const result = await apiClient.get<any>('/api/risk/stop-loss/rules', {
      params: symbol ? { symbol } : {}
    })
    return result.rules || result || []
  },

  /**
   * 创建止损规则
   */
  async createStopLossRule(data: any) {
    const result = await apiClient.post<any>('/api/risk/stop-loss/rules', data)
    return result.rule || result
  },

  /**
   * 批量创建止损规则
   */
  async batchCreateStopLossRules(rules: any[]) {
    const result = await apiClient.post<any>('/api/risk/stop-loss/rules/batch', { rules })
    return result.rules || result || []
  },

  /**
   * 更新止损规则
   */
  async updateStopLossRule(id: string, data: any) {
    const result = await apiClient.put<any>(`/api/risk/stop-loss/rules/${id}`, data)
    return result.rule || result
  },

  /**
   * 删除止损规则
   */
  async deleteStopLossRule(id: string) {
    const result = await apiClient.delete<any>(`/api/risk/stop-loss/rules/${id}`)
    return result
  }
}
