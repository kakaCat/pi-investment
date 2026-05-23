import { apiClient } from './client'
import type {
  KLineData,
  StockListRequest,
  StockDetailRequest,
  MarketDataRequest
} from '@/types'
import { adaptStock, adaptStockList } from './adapters'

export const stockApi = {
  /**
   * 获取股票列表
   */
  async getStocks(params?: StockListRequest) {
    const response = await apiClient.get('/api/stocks/list', { params })
    return adaptStockList(response)
  },

  /**
   * 获取股票详情
   */
  async getStockDetail(symbol: string, _params?: StockDetailRequest) {
    const response = await apiClient.post('/api/stocks/resolve', { code: symbol })
    return adaptStock(response)
  },

  /**
   * 搜索股票
   */
  async searchStocks(keyword: string) {
    const response = await apiClient.get('/api/stocks/search', {
      params: { q: keyword }
    })
    const stocks = (response as any)?.stocks ?? response ?? []
    return Array.isArray(stocks) ? stocks.map(adaptStock) : []
  },

  /**
   * 获取K线数据
   */
  async getKLineData(params: MarketDataRequest) {
    const response = await apiClient.get(`/api/stock/${params.symbol}/klines`, {
      params: {
        start_date: params.startDate,
        end_date: params.endDate
      }
    })
    const klines = (response as any)?.klines ?? (response as any)?.data ?? response
    return Array.isArray(klines) ? klines as KLineData[] : []
  },

  /**
   * 获取股票基本面数据
   */
  getFundamentals(symbol: string) {
    return apiClient.get(`/api/stocks/${symbol}/fundamentals`)
  },

  /**
   * 获取股票技术指标
   */
  getTechnicalIndicators(symbol: string, indicators: string[]) {
    return apiClient.get(`/api/stock/${symbol}/technical`, {
      params: { indicators: indicators.join(',') }
    })
  },

  /**
   * 获取股票资金流向
   */
  getFundFlow(symbol: string, days = 30) {
    return apiClient.get(`/api/stocks/${symbol}/fund-flow`, {
      params: { days }
    })
  },

  /**
   * 获取股票龙虎榜
   */
  getDragonTiger(symbol: string) {
    return apiClient.get(`/api/stocks/${symbol}/dragon-tiger`)
  },

  /**
   * 获取股票公告
   */
  getAnnouncements(symbol: string) {
    return apiClient.get(`/api/stocks/${symbol}/announcements`)
  },

  /**
   * 获取股票新闻
   */
  getNews(symbol: string) {
    return apiClient.get(`/api/stocks/${symbol}/news`)
  },

  /**
   * 获取自选股列表
   */
  getWatchlist(groupId?: string) {
    return apiClient.get('/api/stocks/watchlist', {
      params: { groupId }
    })
  },

  /**
   * 添加到自选股
   */
  addToWatchlist(symbol: string, groupId?: string, note?: string) {
    return apiClient.post('/api/stocks/watchlist', {
      symbol,
      groupId,
      note
    })
  },

  /**
   * 从自选股移除
   */
  removeFromWatchlist(symbol: string) {
    return apiClient.delete(`/api/stocks/watchlist/${symbol}`)
  },

  /**
   * 检查是否在自选股中
   */
  isInWatchlist(symbol: string) {
    return apiClient.get(`/api/stocks/watchlist/${symbol}/check`)
  },

  /**
   * 获取自选股分组
   */
  getWatchlistGroups() {
    return apiClient.get('/api/stocks/watchlist/groups')
  },

  /**
   * 创建自选股分组
   */
  createWatchlistGroup(name: string, description?: string) {
    return apiClient.post('/api/stocks/watchlist/groups', {
      name,
      description
    })
  },

  /**
   * 更新自选股分组
   */
  updateWatchlistGroup(id: string, name: string, description?: string) {
    return apiClient.put(`/api/stocks/watchlist/groups/${id}`, {
      name,
      description
    })
  },

  /**
   * 删除自选股分组
   */
  deleteWatchlistGroup(id: string) {
    return apiClient.delete(`/api/stocks/watchlist/groups/${id}`)
  }
}
