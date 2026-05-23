import { apiClient } from './client'
import type {
  RiskCheckRequest,
  RiskCheckResponse
} from '@/types'

let localStopLossRules: any[] = []

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
  getStopLossRules(symbol?: string) {
    return Promise.resolve(symbol
      ? localStopLossRules.filter(rule => rule.symbol === symbol)
      : localStopLossRules)
  },

  /**
   * 创建止损规则
   */
  createStopLossRule(data: any) {
    const now = new Date().toISOString()
    const rule = {
      ...data,
      id: `${Date.now()}`,
      status: 'active',
      createdAt: now,
      updatedAt: now
    }
    localStopLossRules = [rule, ...localStopLossRules]
    return Promise.resolve(rule)
  },

  /**
   * 批量创建止损规则
   */
  batchCreateStopLossRules(rules: any[]) {
    return Promise.all(rules.map(rule => riskApi.createStopLossRule(rule)))
  },

  /**
   * 更新止损规则
   */
  updateStopLossRule(id: string, data: any) {
    localStopLossRules = localStopLossRules.map(rule =>
      rule.id === id ? { ...rule, ...data, updatedAt: new Date().toISOString() } : rule
    )
    return Promise.resolve(localStopLossRules.find(rule => rule.id === id))
  },

  /**
   * 删除止损规则
   */
  deleteStopLossRule(id: string) {
    localStopLossRules = localStopLossRules.filter(rule => rule.id !== id)
    return Promise.resolve({ success: true })
  }
}
