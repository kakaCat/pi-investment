import { apiClient } from './client'
import type {
  Order,
  Trade,
  CreateOrderRequest,
  OrderListRequest,
  PaginatedResponse,
  PortfolioSummaryResponse
} from '@/types'

export const tradingApi = {
  /**
   * 获取订单列表
   */
  getOrders(params?: OrderListRequest) {
    return apiClient.get<PaginatedResponse<Order>>('/api/orders/list', { params })
  },

  /**
   * 获取订单详情
   */
  getOrderById(orderId: string) {
    return apiClient.get<Order>(`/api/orders/detail/${orderId}`)
  },

  /**
   * 创建订单
   */
  createOrder(data: CreateOrderRequest) {
    return apiClient.post<Order>('/api/orders/create', {
      symbol: data.symbol,
      action: data.type,
      orderType: data.priceType || 'limit',
      quantity: data.quantity,
      price: data.price,
      stopPrice: data.stopLoss
    })
  },

  /**
   * 取消订单
   */
  cancelOrder(orderId: string) {
    return apiClient.post(`/api/orders/cancel/${orderId}`)
  },

  /**
   * 修改订单
   */
  updateOrder(orderId: string, data: Partial<CreateOrderRequest>) {
    return apiClient.post(`/api/orders/update/${orderId}`, data)
  },

  /**
   * 获取持仓列表
   */
  getPositions() {
    return apiClient.get('/api/portfolio/positions')
  },

  /**
   * 获取持仓明细（含实时价格、盈亏、权重）
   */
  getHoldings() {
    return apiClient.get('/api/portfolio/holdings')
  },

  /**
   * 获取持仓汇总
   */
  getPortfolioSummary() {
    return apiClient.get<PortfolioSummaryResponse>('/api/portfolio/summary')
  },

  /**
   * 获取交易历史
   */
  getTradeHistory(params?: any) {
    return apiClient.get('/api/trades/list', { params })
  },

  /**
   * 获取交易记录列表
   */
  getTrades(params?: any) {
    return apiClient.get<PaginatedResponse<Trade>>('/api/trades/list', { params })
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
