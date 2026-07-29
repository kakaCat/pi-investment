import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn()
}))

vi.mock('@/services/api/client', () => ({ apiClient: apiClientMock }))

import { usePortfolioStore } from '@/stores/portfolio'

const POSITION_PAYLOAD = {
  symbol: '600519',
  name: '',
  quantity: 200,
  shares_available: 100,
  avg_cost: 1400.5,
  current_price: 1500,
  total_cost: 280100,
  current_value: 300000,
  profit_loss: 19900,
  profit_loss_pct: 7.1,
  profit_today: 500
}

describe('portfolio store 多账户适配', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('fetchAll 透传 account_name 并记录 currentAccount', async () => {
    apiClientMock.get.mockImplementation((url: string) => {
      if (url === '/api/portfolio/summary') {
        return Promise.resolve({ totalValue: 400000, totalCost: 280100, totalPnl: 19900, totalPnlPct: 7.1, positions: 1, cash: 100000 })
      }
      return Promise.resolve({ positions: [POSITION_PAYLOAD], count: 1 })
    })
    const store = usePortfolioStore()
    await store.fetchAll('v13_simulation')
    expect(store.currentAccount).toBe('v13_simulation')
    const calledUrls = apiClientMock.get.mock.calls.map(c => c[0])
    expect(calledUrls).toContain('/api/portfolio/summary')
    expect(calledUrls).toContain('/api/portfolio/positions')
    for (const call of apiClientMock.get.mock.calls) {
      expect(call[1]).toEqual({ params: { account_name: 'v13_simulation' } })
    }
  })

  it('fetchPositions 按 snake_case 契约映射字段', async () => {
    apiClientMock.get.mockResolvedValue({ positions: [POSITION_PAYLOAD], count: 1 })
    const store = usePortfolioStore()
    await store.fetchPositions('v13_simulation')
    const p = store.positions[0]
    expect(p.symbol).toBe('600519')
    expect(p.quantity).toBe(200)
    expect(p.sharesAvailable).toBe(100)
    expect(p.avgCost).toBe(1400.5)
    expect(p.currentPrice).toBe(1500)
    expect(p.marketValue).toBe(300000)
    expect(p.totalCost).toBe(280100)
    expect(p.profit).toBe(19900)
    expect(p.profitPercent).toBe(7.1)
    expect(p.name).toBe('600519')  // 后端 name 为空时 fallback symbol
    expect(p.weight).toBe(100)     // 单持仓权重 100%
  })

  it('账户名为空时不发请求', async () => {
    const store = usePortfolioStore()
    await store.fetchAll('')
    expect(apiClientMock.get).not.toHaveBeenCalled()
  })
})
