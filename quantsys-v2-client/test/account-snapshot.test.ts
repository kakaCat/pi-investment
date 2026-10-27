/**
 * account snapshot（/overview）读取契约。
 *
 * 展示型工具（position_list/account_info）改读 DB 快照：毫秒级、不阻塞等行情，
 * 并用 priceStale/priceUpdatedAt 如实告知新鲜度；旧后端 404 时回退实时接口。
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { QuantsysV2Client } from '../src/client'

const ACCOUNT = 'acct_snapshot'

const OVERVIEW = {
  success: true,
  data: {
    account_name: ACCOUNT,
    cash_available: 1000,
    cash_frozen: 0,
    position_value: 152000,
    total_value: 153000,
    last_updated: '2026-10-27T21:00:00',
    price_stale: true,
    positions_count: 1,
    positions: [{
      symbol: '600519',
      name: '贵州茅台',
      shares_total: 100,
      shares_available: 100,
      avg_cost: 1500,
      current_price: 1520,
      market_value: 152000,
      profit_total: 500,
      profit_total_rate: 0.01,
      profit_today: 0,
      price_updated_at: '2026-10-27T20:59:00',
    }],
  },
  meta: { price_stale: true, price_as_of: '2026-10-27T20:59:00' },
}

function makeClient(): QuantsysV2Client {
  return new QuantsysV2Client({ baseURL: 'http://v2.test', timeout: 1000 })
}

afterEach(() => { vi.restoreAllMocks() })

describe('/overview 快照读取', () => {
  it('getPositionsSnapshot → /overview 且透出 priceStale/priceUpdatedAt', async () => {
    const client = makeClient()
    const get = vi.spyOn((client as any).client, 'get').mockResolvedValue({ data: OVERVIEW })

    const positions = await client.getPositionsSnapshot(ACCOUNT)

    expect(get).toHaveBeenCalledWith(`/api/simulation/accounts/${ACCOUNT}/overview`)
    expect(positions).toHaveLength(1)
    expect(positions[0]).toMatchObject({
      symbol: '600519',
      currentPrice: 1520,
      profitLoss: 500,
      priceUpdatedAt: '2026-10-27T20:59:00',
      priceStale: true,
    })
  })

  it('getPortfolioSummarySnapshot → /overview 且口径与旧接口一致', async () => {
    const client = makeClient()
    vi.spyOn((client as any).client, 'get').mockResolvedValue({ data: OVERVIEW })

    const summary = await client.getPortfolioSummarySnapshot(ACCOUNT)

    expect(summary).toMatchObject({
      accountName: ACCOUNT,
      totalValue: 153000,
      totalMarketValue: 152000,
      totalCost: 150000,
      positions: 1,
      cash: 1000,
      priceStale: true,
    })
  })

  it('旧后端无 /overview（404）→ 回退实时账户接口', async () => {
    const client = makeClient()
    const get = vi.spyOn((client as any).client, 'get')
      .mockRejectedValueOnce({ response: { status: 404 } })
      .mockResolvedValueOnce({ data: OVERVIEW })

    const positions = await client.getPositionsSnapshot(ACCOUNT)

    expect(get).toHaveBeenNthCalledWith(1, `/api/simulation/accounts/${ACCOUNT}/overview`)
    expect(get).toHaveBeenNthCalledWith(2, `/api/simulation/accounts/${ACCOUNT}`)
    expect(positions).toHaveLength(1)
  })

  it('requestQuoteRefresh → POST /quotes/refresh', async () => {
    const client = makeClient()
    const post = vi.spyOn((client as any).client, 'post').mockResolvedValue({ data: { success: true } })

    await client.requestQuoteRefresh(ACCOUNT)

    expect(post).toHaveBeenCalledWith(`/api/simulation/accounts/${ACCOUNT}/quotes/refresh`)
  })
})
