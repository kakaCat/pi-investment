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
const { dataApi, mapJobToDataUpdateJob } = await import('@/services/api/data')

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
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/stock/000001/klines', {
      params: { start_date: '2024-01-01', end_date: '2024-02-01' }
    })

    stockApi.getTechnicalIndicators('000001.SZ', ['ma', 'macd'])
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/stock/000001.SZ/technical', {
      params: { indicators: 'ma,macd' }
    })
  })

  it('adapts stock list search pagination from backend data wrapper', async () => {
    mockedClient.get.mockResolvedValueOnce({
      stocks: [
        {
          symbol: '000001.SZ',
          name: '平安银行',
          market: 'SZ',
          industry: '银行'
        }
      ],
      pagination: {
        page: 1,
        pageSize: 20,
        total: 1,
        totalPages: 1
      }
    })

    const result = await stockApi.getStocks({ page: 1, pageSize: 20, keyword: '平安' })

    expect(result.items).toHaveLength(1)
    expect(result.items[0].code).toBe('000001.SZ')
    expect(result.total).toBe(1)
    expect(result.page).toBe(1)
    expect(result.pageSize).toBe(20)
  })

  it('treats missing stock detail and klines as empty stock state', async () => {
    const notFoundError = { response: { status: 404, data: { error: 'No kline data for 000001.SZ' } } }

    mockedClient.post.mockRejectedValueOnce(notFoundError)
    mockedClient.get.mockRejectedValueOnce(notFoundError)

    await expect(stockApi.getStockDetail('000001.SZ')).resolves.toMatchObject({
      symbol: '000001.SZ',
      name: '000001.SZ',
      dataStatus: 'missing'
    })
    await expect(stockApi.getKLineData({ symbol: '000001.SZ' })).resolves.toEqual([])
  })

  it('normalizes A-share suffixed symbols before calling stock detail endpoints', async () => {
    mockedClient.post.mockResolvedValueOnce({ found: true, symbol: '000001', name: '平安银行' })

    await stockApi.getStockDetail('000001.SZ')

    expect(mockedClient.post).toHaveBeenLastCalledWith('/api/stocks/resolve', { code: '000001' })
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

    indicatorApi.runIndicator('7', { symbol: '000001.SZ', limit: 20 })
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

  it('maps completed data update jobs with failures to failed status', () => {
    const job = mapJobToDataUpdateJob({
      id: 'job-1',
      type: 'data_update',
      status: 'completed',
      params: { source: 'hs300', days: 730, force: false },
      result: { total: 300, succeeded: 0, failed: 300 },
      createdAt: '2026-05-24T12:27:44'
    })

    expect(job.status).toBe('failed')
    expect(job.success).toBe(0)
    expect(job.failed).toBe(300)
  })
})
