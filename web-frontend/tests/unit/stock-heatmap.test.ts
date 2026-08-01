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

const { judgeSignal, judgePoolEvent, judgeStance } = await import('@/views/StockHeatmap/verdict')

describe('verdict 对错判定', () => {
  it('买入信号涨=对，跌=错', () => {
    expect(judgeSignal('buy', 8.2)).toBe('right')
    expect(judgeSignal('buy', -4.4)).toBe('wrong')
  })

  it('卖出信号跌=对，涨=错', () => {
    expect(judgeSignal('sell', -3.1)).toBe('right')
    expect(judgeSignal('sell', 2.0)).toBe('wrong')
  })

  it('涨跌为 0 时不判', () => {
    expect(judgeSignal('buy', 0)).toBe('none')
  })

  it('池调入涨=对，池调出跌=对', () => {
    expect(judgePoolEvent('add', 1.5)).toBe('right')
    expect(judgePoolEvent('add', -1.5)).toBe('wrong')
    expect(judgePoolEvent('remove', -2.0)).toBe('right')
    expect(judgePoolEvent('remove', 2.0)).toBe('wrong')
  })

  it('行业 stance：看好且行业涨=对，回避且行业跌=对，neutral 不判', () => {
    expect(judgeStance('bullish', 4.2)).toBe('right')
    expect(judgeStance('bullish', -1.0)).toBe('wrong')
    expect(judgeStance('bearish', -5.0)).toBe('right')
    expect(judgeStance('bearish', 3.0)).toBe('wrong')
    expect(judgeStance('neutral', 9.9)).toBe('none')
  })
})
