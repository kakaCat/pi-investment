import { describe, it, expect, vi, beforeEach } from 'vitest'

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn()
}))

vi.mock('@/services/api/client', () => ({ apiClient: apiClientMock }))

import { tradingApi } from '@/services/api/trading'

describe('tradingApi 多账户契约', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getPositions 必传 account_name', async () => {
    apiClientMock.get.mockResolvedValue({ positions: [], count: 0 })
    await tradingApi.getPositions('v13_simulation')
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/portfolio/positions', {
      params: { account_name: 'v13_simulation' }
    })
  })

  it('getPortfolioSummary 必传 account_name', async () => {
    apiClientMock.get.mockResolvedValue({ totalValue: 0 })
    await tradingApi.getPortfolioSummary('agent_virtual')
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/portfolio/summary', {
      params: { account_name: 'agent_virtual' }
    })
  })
})
