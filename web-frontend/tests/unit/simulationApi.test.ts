import { describe, it, expect, vi, beforeEach } from 'vitest'

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn()
}))

vi.mock('@/services/api/client', () => ({ apiClient: apiClientMock }))

import { simulationApi } from '@/services/api/simulation'

describe('simulationApi', () => {
  beforeEach(() => vi.clearAllMocks())

  it('listAccounts 请求账户发现端点', async () => {
    apiClientMock.get.mockResolvedValue({ success: true, data: { accounts: [], total: 0 } })
    await simulationApi.listAccounts()
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/simulation/accounts', { params: { status: 'active' } })
  })

  it('createAccount 提交开户参数', async () => {
    apiClientMock.post.mockResolvedValue({ success: true, data: { account_name: 'x' } })
    await simulationApi.createAccount({ account_name: 'x', display_name: 'X', initial_capital: 100000 })
    expect(apiClientMock.post).toHaveBeenCalledWith('/api/simulation/accounts', {
      account_name: 'x', display_name: 'X', initial_capital: 100000, strategy_name: undefined
    })
  })

  it('getAccount 按账户名查询', async () => {
    apiClientMock.get.mockResolvedValue({ success: true, data: {} })
    await simulationApi.getAccount('v13_simulation')
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/simulation/accounts/v13_simulation')
  })

  it('trade 提交交易到账户端点', async () => {
    apiClientMock.post.mockResolvedValue({ success: true, data: { order_id: 1 } })
    await simulationApi.trade('v13_simulation', { action: 'buy', symbol: '600519', shares: 100, reason: '测试理由：不少于十个字' })
    expect(apiClientMock.post).toHaveBeenCalledWith('/api/simulation/accounts/v13_simulation/trade', {
      action: 'buy', symbol: '600519', shares: 100, reason: '测试理由：不少于十个字'
    })
  })

  it('getTrades/getPerformance/executionHistory 必传 account_name', async () => {
    apiClientMock.get.mockResolvedValue({ success: true, data: [] })
    await simulationApi.getTrades('v13_simulation', 50)
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/simulation/trades', { params: { account_name: 'v13_simulation', limit: 50 } })
    await simulationApi.getPerformance('v13_simulation')
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/simulation/performance', { params: { account_name: 'v13_simulation' } })
    await simulationApi.getExecutionHistory('v13_simulation', 50)
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/simulation/execution-history', { params: { account_name: 'v13_simulation', limit: 50 } })
  })

  it('runStrategy 携带 strategy_id 和 account_name', async () => {
    apiClientMock.post.mockResolvedValue({ success: true, data: {} })
    await simulationApi.runStrategy('v13', 'v13_simulation')
    expect(apiClientMock.post).toHaveBeenCalledWith('/api/simulation/run', {
      strategy_id: 'v13', account_name: 'v13_simulation'
    })
  })

  it('getStrategyInfo 查询策略详情', async () => {
    apiClientMock.get.mockResolvedValue({ success: true, data: {} })
    await simulationApi.getStrategyInfo('v13')
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/simulation/strategies/v13')
  })
})
