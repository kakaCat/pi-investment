import { apiClient } from './client'
import type {
  Order,
  Trade,
  CreateOrderRequest,
  OrderListRequest,
  PaginatedResponse
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
   * 获取持仓汇总
   */
  getPortfolioSummary() {
    return apiClient.get('/api/portfolio/summary')
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
  }
}
