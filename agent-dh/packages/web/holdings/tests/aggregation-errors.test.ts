import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CoreDataUnavailableError, PortfolioAggregationService } from '../src/services/portfolio-aggregation'
import type { HoldingsData } from '../src/types'

/**
 * 失败语义契约锁（2026-10-27，RFC 017 P0，w-7e3880c6）
 *
 * 背景事故（2026-10-26 实测）：accountStatus 上游超时后，旧实现返回
 * success=true + 空持仓 + 零值摘要——用户看到「加载 4 秒后资产清零」。
 * 真实空仓、上游失败、账户不存在是三种不同状态，必须可区分：
 *  - core（accountStatus）失败 → 抛 CoreDataUnavailableError（路由转 503）
 *  - accounts 失败 → 省略响应 accounts 键 + meta.errors.accounts（前端保留缓存列表）
 *  - 辅助块（成交/盯盘/调度/Agent OS）失败 → success=true + meta.errors.<part>
 *
 * 故障注入方式：按 URL 打桩全局 fetch。
 * 每个测试用**独立账户名**：聚合层对成交/盯盘有 30s 模块级冷缓存
 * （coldCached key=trades:<account>），共享账户会让缓存跨测试复用、
 * 「上游失败」被缓存的成功结果吞掉——这本身就是缓存契约的一部分，此处绕开。
 */

const V2 = 'http://v2.test'

const ACCOUNT_STATUS = (account: string) => ({
  success: true,
  data: {
    account_name: account,
    cash_available: 49000,
    cash_frozen: 0,
    position_value: 1000,
    total_value: 50000,
    last_updated: '2026-10-27T09:00:00',
    price_stale: false,
    positions_count: 1,
    positions: [{
      symbol: '600519', name: '贵州茅台', shares_total: 100, shares_available: 100,
      avg_cost: 1500, current_price: 1520, market_value: 152000,
      profit_total: 2000, profit_total_rate: 0.0133, profit_today: 0,
    }],
  },
})
const ACCOUNTS = {
  success: true,
  data: {
    accounts: [{ account_name: 'acct_any', display_name: '账户A', strategy_name: '', status: 'active', cash_available: 49000, position_value: 1000, total_value: 50000, cumulative_return: 0, positions_count: 1 }],
    total: 1,
  },
}
const SCHEDULER = { success: true, tasks: [] }
const TRADES = { success: true, data: [] }
const WATCH_RULES = { success: true, data: { rules: [] } }

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

/** 组装 fetch 桩：overrides 的 key 为 URL 子串（先匹配先生效），其余按默认应答。 */
function makeFetch(_account: string, overrides: Record<string, Error> = {}) {
  return async (url: string): Promise<Response> => {
    for (const [key, val] of Object.entries(overrides)) {
      if (url.includes(key)) throw val
    }
    // 先精确匹配列表端点，再按路径段匹配状态端点（避免列表应答被子串误判给状态端点）
    if (url === V2 + '/api/simulation/accounts') return jsonResponse(ACCOUNTS)
    const statusMatch = url.match(/\/api\/simulation\/accounts\/([^/?]+)/)
    if (statusMatch) return jsonResponse(ACCOUNT_STATUS(statusMatch[1]))
    if (url.includes('/api/scheduler/tasks')) return jsonResponse(SCHEDULER)
    if (url.includes('/api/simulation/trades')) return jsonResponse(TRADES)
    if (url.includes('/api/watch/rules')) return jsonResponse(WATCH_RULES)
    throw new Error('未打桩的 URL: ' + url)
  }
}

function makeService(): PortfolioAggregationService {
  return new PortfolioAggregationService({
    v2BaseURL: V2,
    agentOsBaseURL: '', // 跳过 Agent OS（独立请求，路由内自带 allSettled 容忍）
    requestTimeoutMs: 4000,
  })
}

beforeEach(() => {
  vi.stubGlobal('fetch', makeFetch('nobody'))
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('core 失败语义（假空数据修复）', () => {
  it('accountStatus 超时 → 抛 CoreDataUnavailableError（路由转 503），绝不返回零值摘要', async () => {
    const acct = 'acct_core'
    vi.stubGlobal('fetch', makeFetch(acct, {
      [`/api/simulation/accounts/${acct}`]: new Error('请求超时(>4000ms)'),
    }))
    const svc = makeService()
    let caught: unknown = null
    try {
      await svc.aggregate(acct)
    } catch (e) {
      caught = e
    }
    expect(caught).toBeInstanceOf(CoreDataUnavailableError)
    const err = caught as CoreDataUnavailableError
    expect(err.code).toBe('CORE_DATA_UNAVAILABLE')
    expect(err.accountName).toBe(acct)
  })

  it('accounts 失败但 accountStatus 成功 → 省略 accounts 键 + meta.errors.accounts，summary 为真实数据', async () => {
    const acct = 'acct_accts'
    // 仅 accounts 列表端点失败（状态端点是其子路径，精确尾段区分）
    vi.stubGlobal('fetch', (async (url: string) => {
      if (url === V2 + '/api/simulation/accounts') throw new Error('请求超时(>4000ms)')
      return makeFetch(acct)(url)
    }) as typeof fetch)

    const svc = makeService()
    const { data, meta } = await svc.aggregate(acct)

    // 假空数据修复的核心断言：accounts 键被省略（而非空数组），前端缓存列表得以保留
    expect('accounts' in data).toBe(false)
    expect(meta.errors?.accounts?.code).toBe('UPSTREAM_UNAVAILABLE')
    // summary 必须是真实数据，不是 getDefaultSummary() 零值
    expect(data.summary.totalValue).toBe(50000)
    expect(data.positions).toHaveLength(1)
  })

  it('辅助块（scheduler/trades/watch）失败 → core 不受影响 + meta.errors 按块记录', async () => {
    const acct = 'acct_aux'
    vi.stubGlobal('fetch', makeFetch(acct, {
      '/api/scheduler/tasks': new Error('请求超时(>4000ms)'),
      '/api/simulation/trades': new Error('请求超时(>4000ms)'),
      '/api/watch/rules': new Error('请求超时(>4000ms)'),
    }))
    const svc = makeService()
    const { data, meta } = await svc.aggregate(acct)

    expect(data.summary.totalValue).toBe(50000)
    expect(data.positions).toHaveLength(1)
    expect(data.accounts).toHaveLength(1)
    // 辅助块容忍为空（保持既有渲染契约）
    expect(data.watchRules).toEqual([])
    expect(data.tradeHistory).toEqual([])
    // 但错误必须可见（meta.errors），不得静默
    expect(meta.errors?.scheduler?.code).toBe('UPSTREAM_UNAVAILABLE')
    expect(meta.errors?.activity?.code).toBe('UPSTREAM_UNAVAILABLE')
    expect(meta.errors?.watch?.code).toBe('UPSTREAM_UNAVAILABLE')
  })

  it('全部正常 → accounts 存在且无 errors', async () => {
    const acct = 'acct_ok'
    const svc = makeService()
    const { data, meta } = await svc.aggregate(acct)
    expect(data.accounts).toHaveLength(1)
    expect(data.currentAccount).toBe(acct)
    expect(data.summary.totalValue).toBe(50000)
    expect(meta.errors).toBeUndefined()
    expect(meta.asOf).toBeTruthy()
  })

  it('真实空仓与失败可区分：账户确认无持仓时 positions=[] 且 summary 为真实资产', async () => {
    const acct = 'acct_empty'
    vi.stubGlobal('fetch', (async (url: string) => {
      if (url.includes(`/api/simulation/accounts/${acct}`)) {
        return jsonResponse({
          ...ACCOUNT_STATUS(acct),
          data: { ...ACCOUNT_STATUS(acct).data, position_value: 0, total_value: 49000, positions_count: 0, positions: [] },
        })
      }
      return makeFetch(acct)(url)
    }) as typeof fetch)
    const svc = makeService()
    const { data } = await svc.aggregate(acct)
    expect(data.positions).toEqual([])
    expect(data.summary.positions).toBe(0)
    expect(data.summary.totalValue).toBe(49000)
    expect(data.summary.cash).toBe(49000)
  })
})

describe('HoldingsData 契约', () => {
  it('loadNotice 字段可选（客户端降级提示，core 失败但缓存可用时写入）', () => {
    const data = { loadNotice: '数据刷新失败，显示上次有效数据' } as HoldingsData
    expect(String(data.loadNotice ?? '')).toBe('数据刷新失败，显示上次有效数据')
    const empty = {} as HoldingsData
    expect(String(empty.loadNotice ?? '')).toBe('')
  })
})
