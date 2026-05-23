import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

const { apiClient } = await import('@/services/api/client')
const { stockApi } = await import('@/services/api/stock')
const { tradingApi } = await import('@/services/api/trading')
const { strategyApi } = await import('@/services/api/strategy')
const { indicatorApi } = await import('@/services/api/indicator')
const { pipelineApi } = await import('@/services/api/pipeline')
const { dataApi } = await import('@/services/api/data')

const mockedClient = vi.mocked(apiClient)

describe('QuantSys V2 API contract', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('uses existing stock endpoints', () => {
    stockApi.getStocks({ page: 2, pageSize: 10, keyword: '平安' })
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/stocks/list', {
      params: { page: 2, pageSize: 10, keyword: '平安' }
    })

    stockApi.searchStocks('平安')
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/stocks/search', {
      params: { q: '平安' }
    })

    stockApi.getKLineData({ symbol: '000001.SZ', startDate: '2024-01-01', endDate: '2024-02-01' })
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/stock/000001.SZ/klines', {
      params: { start_date: '2024-01-01', end_date: '2024-02-01' }
    })

    stockApi.getTechnicalIndicators('000001.SZ', ['ma', 'macd'])
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/stock/000001.SZ/technical', {
      params: { indicators: 'ma,macd' }
    })
  })

  it('uses existing trading endpoints and backend payload names', () => {
    tradingApi.getOrders({ page: 1, pageSize: 20, status: 'pending' })
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/orders/list', {
      params: { page: 1, pageSize: 20, status: 'pending' }
    })

    tradingApi.getOrderById('12')
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/orders/detail/12')

    tradingApi.createOrder({ symbol: '000001.SZ', type: 'buy', priceType: 'limit', price: 10, quantity: 100 })
    expect(mockedClient.post).toHaveBeenLastCalledWith('/api/orders/create', {
      symbol: '000001.SZ',
      action: 'buy',
      orderType: 'limit',
      quantity: 100,
      price: 10
    })

    tradingApi.cancelOrder('12')
    expect(mockedClient.post).toHaveBeenLastCalledWith('/api/orders/cancel/12')

    tradingApi.updateOrder('12', { price: 11 })
    expect(mockedClient.post).toHaveBeenLastCalledWith('/api/orders/update/12', { price: 11 })

    tradingApi.getTrades({ page: 1, pageSize: 20 })
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/trades/list', {
      params: { page: 1, pageSize: 20 }
    })
  })

  it('uses existing strategy and indicator endpoints', () => {
    strategyApi.getStrategies({ page: 1, pageSize: 20 })
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/strategies/list', {
      params: { page: 1, pageSize: 20 }
    })

    strategyApi.startStrategy('trend')
    expect(mockedClient.post).toHaveBeenLastCalledWith('/api/strategies/start/trend')

    indicatorApi.getIndicators({ page: 1 })
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/indicators/list', {
      params: { page: 1 }
    })

    indicatorApi.runIndicator('7', '000001.SZ', { limit: 20 })
    expect(mockedClient.post).toHaveBeenLastCalledWith('/api/indicators/run/7', {
      symbol: '000001.SZ',
      limit: 20
    })
  })

  it('uses existing pipeline and data update endpoints', () => {
    pipelineApi.getTasks({ limit: 20 })
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/pipeline/tasks/list', {
      params: { limit: 20 }
    })

    pipelineApi.getRuns({ limit: 10 })
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/pipeline/runs/list', {
      params: { limit: 10 }
    })

    dataApi.startUpdate({ scope: 'hs300', days: 5, forceUpdate: true })
    expect(mockedClient.post).toHaveBeenLastCalledWith('/api/data/update', {
      source: 'hs300',
      days: 5,
      force: true,
      async: true
    })
  })
})
