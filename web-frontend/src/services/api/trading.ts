import { apiClient } from './client'
import type {
  Order,
  Trade,
  CreateOrderRequest,
  OrderListRequest,
  PaginatedResponse,
  PortfolioSummaryResponse
} from '@/types'

// 多账户改造后（2026-07-21）portfolio 接口必须传 account_name；
// agent_virtual 是 agent 唯一交易账本（盈利闭环约定），作为默认账户
export const DEFAULT_ACCOUNT = 'agent_virtual'

export const tradingApi = {
  /**
   * 获取持仓列表（account_name 必填）
   */
  getPositions(accountName: string) {
    return apiClient.get('/api/portfolio/positions', {
      params: { account_name: accountName }
    })
  },

  /**
   * 获取持仓明细（含实时价格、盈亏、权重）
   */
  getHoldings() {
    return apiClient.get('/api/portfolio/holdings')
  },

  /**
   * 获取持仓汇总（account_name 必填）
   */
  getPortfolioSummary(accountName: string) {
    return apiClient.get<PortfolioSummaryResponse>('/api/portfolio/summary', {
      params: { account_name: accountName }
    })
  },

  /**
   * 获取资产曲线
   */
  getEquityCurve(startDate?: string, endDate?: string) {
    return apiClient.get('/api/portfolio/equity-curve', {
      params: { startDate, endDate }
    })
  },

  /**
   * 获取持仓分布
   */
  getAllocation() {
    return apiClient.get('/api/portfolio/allocation')
  },

  /**
   * 获取执行记录列表
   */
  getExecutions(params?: {
    status?: string
    startDate?: string
    endDate?: string
    limit?: number
    offset?: number
  }) {
    return apiClient.get('/api/executions', { params })
  },

  /**
   * 获取执行记录详情
   */
  getExecutionById(executionId: number) {
    return apiClient.get(`/api/executions/${executionId}`)
  },

  /**
   * 获取执行统计
   */
  getExecutionStats(startDate?: string, endDate?: string) {
    return apiClient.get('/api/executions/stats', {
      params: { start_date: startDate, end_date: endDate }
    })
  },

  /**
   * 批准信号（执行）
   */
  executeSignal(signalId: number) {
    return apiClient.post(`/api/signals/approve/${signalId}`)
  },

  /**
   * 取消执行记录
   */
  cancelExecution(executionId: number) {
    return apiClient.put(`/api/executions/${executionId}/cancel`)
  },

  /**
   * 平仓执行记录
   */
  closeExecution(executionId: number, closeDate: string, closePrice: number) {
    return apiClient.put(`/api/executions/${executionId}/close`, {
      close_date: closeDate,
      close_price: closePrice
    })
  }
}
