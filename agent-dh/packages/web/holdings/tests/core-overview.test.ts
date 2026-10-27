import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PortfolioAggregationService } from '../src/services/portfolio-aggregation'

/**
 * P2 core/overview 契约锁（2026-10-27，RFC 017 P2，w-7e3880c6）
 *
 * 锁四件事：
 *  ① core 走 /overview（只读 DB 快照），并从 meta 透出 price_as_of/price_stale；
 *  ② core 请求**不产生** scheduler/trades/watch 网络调用（辅助块不再搭顺风车）；
 *  ③ 旧后端无 /overview（404）→ 回退旧状态接口（前后端可独立部署）；
 *  ④ 只请求 automation 时不拉 overview（分块按需，互不阻塞）。
 */

const V2 = 'http://v2.test'
const ACCOUNT = 'acct_ov'

const OVERVIEW = {
  success: true,
  data: {
    account_name: ACCOUNT,
    cash_available: 1000, cash_frozen: 0, position_value: 2000, total_value: 3000,
    last_updated: '2026-10-27T18:00:00', price_as_of: '2026-10-27T17:59:00', price_stale: true,
    positions_count: 1,
    positions: [{
      symbol: '600519', name: '贵州茅台', shares_total: 100, shares_available: 100,
      avg_cost: 1500, current_price: 1520, market_value: 2000,
      profit_total: 500, profit_total_rate: 0.01, profit_today: 0,
      price_updated_at: '2026-10-27T17:59:00',
    }],
  },
  meta: { source: 'db_snapshot', snapshot_as_of: '2026-10-27T18:00:00',
          price_as_of: '2026-10-27T17:59:00', price_stale: true },
}
const STATUS = {
  success: true,
  data: { ...OVERVIEW.data, last_updated: '2026-10-27T18:00:00' },
}
const ACCOUNTS = { success: true, data: { accounts: [], total: 0 } }
const SCHEDULER = { success: true, contract_version: 2, tasks: [] }
const TRADES = { success: true, data: [] }
const WATCH = { success: true, data: { rules: [] } }

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** 记录请求过的 URL；overview 可按 need 返回 404 模拟旧后端。 */
function makeFetch(urls: string[], overviewStatus = 200) {
  return async (url: string): Promise<Response> => {
    urls.push(url)
    if (url.includes('/api/scheduler/tasks')) return jsonResponse(SCHEDULER)
    if (url.includes('/api/simulation/trades')) return jsonResponse(TRADES)
    if (url.includes('/api/watch/rules')) return jsonResponse(WATCH)
    if (url === V2 + '/api/simulation/accounts') return jsonResponse(ACCOUNTS)
    if (url.endsWith('/overview')) {
      return overviewStatus === 404
        ? jsonResponse({ success: false, error: 'Not Found' }, 404)
        : jsonResponse(OVERVIEW)
    }
    if (url.includes('/api/simulation/accounts/')) return jsonResponse(STATUS)
    throw new Error('未打桩的 URL: ' + url)
  }
}

function makeService(): PortfolioAggregationService {
  return new PortfolioAggregationService({ v2BaseURL: V2, agentOsBaseURL: '', requestTimeoutMs: 4000 })
}

let urls: string[] = []
beforeEach(() => { urls = []; vi.stubGlobal('fetch', makeFetch(urls)) })
afterEach(() => { vi.unstubAllGlobals() })

describe('P2 core 走 overview 快照', () => {
  it('core 返回 price_as_of/price_stale，且不产生 scheduler/trades/watch 调用', async () => {
    const svc = makeService()
    const { data } = await svc.aggregate(ACCOUNT, { parts: ['accounts', 'currentAccount', 'summary', 'positions', 'compliance'] })

    expect(data.summary?.totalValue).toBe(3000)
    expect(data.positions).toHaveLength(1)
    expect(data.priceAsOf).toBe('2026-10-27T17:59:00')
    expect(data.priceStale).toBe(true)
    expect(data.snapshotAsOf).toBe('2026-10-27T18:00:00')

    expect(urls.some((u) => u.endsWith('/overview'))).toBe(true)
    expect(urls.some((u) => u.includes('/api/scheduler/tasks'))).toBe(false)
    expect(urls.some((u) => u.includes('/api/simulation/trades'))).toBe(false)
    expect(urls.some((u) => u.includes('/api/watch/rules'))).toBe(false)
  })

  it('旧后端 404 → 回退旧状态接口，core 照常可用（兼容期）', async () => {
    vi.stubGlobal('fetch', makeFetch(urls, 404))
    const svc = makeService()
    const { data } = await svc.aggregate(ACCOUNT, { parts: ['accounts', 'currentAccount', 'summary', 'positions'] })
    expect(data.summary?.totalValue).toBe(3000)
    expect(urls.some((u) => u.endsWith('/overview'))).toBe(true)
    // 回退走旧账户状态接口（非 overview）
    expect(urls.some((u) => u.endsWith('/api/simulation/accounts/' + ACCOUNT))).toBe(true)
  })

  it('只请求 automation 时不拉 overview，且 core 字段缺省（分块按需）', async () => {
    const svc = makeService()
    const { data } = await svc.aggregate(ACCOUNT, { parts: ['automation'] })
    expect(data.summary).toBeUndefined()
    expect(data.positions).toBeUndefined()
    expect(data.automation).toBeDefined()
    expect(urls.some((u) => u.endsWith('/overview'))).toBe(false)
    expect(urls.some((u) => u.includes('/api/scheduler/tasks'))).toBe(true)
  })
})
