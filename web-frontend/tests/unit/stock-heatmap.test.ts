import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/services/api/client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }
}))

const { apiClient } = await import('@/services/api/client')
const { stockApi } = await import('@/services/api/stock')
const mockedClient = vi.mocked(apiClient)

describe('stockApi.getHeatmap', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls heatmap endpoint with params', async () => {
    mockedClient.get.mockResolvedValueOnce({ industries: [] })
    await stockApi.getHeatmap({ date: '2026-07-24', window: 5 })
    expect(mockedClient.get).toHaveBeenLastCalledWith('/api/market/heatmap', {
      params: { date: '2026-07-24', window: 5 }
    })
  })

  it('adapts backend camelCase payload and tolerates snake_case', async () => {
    mockedClient.get.mockResolvedValueOnce({
      date: '2026-07-24', window: 5, actualEndDate: '2026-07-31',
      partial: false, scopeDegraded: false, excludedCount: 1,
      industries: [{
        name: '半导体', changePct: 4.2, agentStance: 'bullish',
        stocks: [{
          symbol: '688981', name: '中芯国际', change_pct: 8.2,
          market_cap: 4.5e11, in_scope: true,
          signals: [{ type: 'buy', date: '2026-07-23', strategy: 'v13' }]
        }]
      }]
    })
    const result = await stockApi.getHeatmap()
    expect(result.actualEndDate).toBe('2026-07-31')
    expect(result.excludedCount).toBe(1)
    const ind = result.industries[0]
    expect(ind.agentStance).toBe('bullish')
    const st = ind.stocks[0]
    expect(st.changePct).toBe(8.2)
    expect(st.marketCap).toBe(4.5e11)
    expect(st.inScope).toBe(true)
    expect(st.signals?.[0].type).toBe('buy')
  })
})
