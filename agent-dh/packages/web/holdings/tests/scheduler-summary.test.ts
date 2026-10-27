import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PortfolioAggregationService } from '../src/services/portfolio-aggregation'

/**
 * 调度摘要消费契约锁（2026-10-27，RFC 017 P1，w-7e3880c6）
 *
 * 锁三件事：
 *  ① 优先 /api/scheduler/tasks/summary（contract_version=2）：lastStatus 直接信任
 *     （服务端已归一化假成功），不再解 payload；
 *  ② summary 不可用（404/超时）→ 回退旧 /tasks 端点 + 客户端 resolveLastRun 归一化
 *     （前后端可独立部署的兼容期契约）；
 *  ③ summary 响应不携带 payload/result——消费方不得再读取 lastRun.payload。
 */

const V2 = 'http://v2.test'

const ACCOUNT_STATUS = {
  success: true,
  data: {
    account_name: 'acct_sum', cash_available: 1, cash_frozen: 0, position_value: 0,
    total_value: 1, last_updated: '2026-10-27T09:00:00', price_stale: false,
    positions_count: 0, positions: [],
  },
}
const ACCOUNTS = { success: true, data: { accounts: [], total: 0 } }
const TRADES = { success: true, data: [] }
const WATCH_RULES = { success: true, data: { rules: [] } }

const SUMMARY_TASKS = {
  success: true,
  contract_version: 2,
  tasks: [{
    id: '1', name: 'v13_daily_check', enabled: true, scheduleExpr: '0 9 * * 1-5',
    command: 'v13_daily_check', description: 'V13 每日检查',
    lastStatus: 'failed', lastStatusSource: 'inner_result',
    lastAt: '2026-10-27T09:00:00+08:00', lastError: 'engine down',
    nextRunAt: '2026-10-28T09:00:00+08:00', todayTriggered: 1, todaySuccess: 0,
  }],
  count: 1, page: 1, pageSize: 200,
}
const LEGACY_TASKS = {
  success: true,
  tasks: [{
    id: 1, name: 'v13_daily_check', is_enabled: true, cron_expression: '0 9 * * 1-5',
    command: 'v13_daily_check', description: 'V13 每日检查', params: {},
    next_run_at: '2026-10-28T09:00:00+08:00',
    lastRun: {
      status: 'success', triggeredAt: '2026-10-27T09:00:00+08:00',
      payload: { details: { details: { status: 'failed', error: 'legacy-inner-boom' } } },
    },
    todayTriggered: 1, todaySuccess: 0,
  }],
  count: 1, total: 1, page: 1, pageSize: 200,
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function makeFetch(mode: 'summary' | 'legacy404' | 'legacyTimeout') {
  return async (url: string): Promise<Response> => {
    if (url.includes('/api/scheduler/tasks/summary')) {
      if (mode === 'summary') return jsonResponse(SUMMARY_TASKS)
      if (mode === 'legacy404') return jsonResponse({ success: false, error: 'Not Found' }, 404)
      throw new Error('请求超时(>4000ms)')
    }
    if (url.includes('/api/scheduler/tasks')) return jsonResponse(LEGACY_TASKS)
    if (url.includes('/api/simulation/accounts/acct_sum')) return jsonResponse(ACCOUNT_STATUS)
    if (url.includes('/api/simulation/accounts')) return jsonResponse(ACCOUNTS)
    if (url.includes('/api/simulation/trades')) return jsonResponse(TRADES)
    if (url.includes('/api/watch/rules')) return jsonResponse(WATCH_RULES)
    throw new Error('未打桩的 URL: ' + url)
  }
}

function makeService(): PortfolioAggregationService {
  return new PortfolioAggregationService({ v2BaseURL: V2, agentOsBaseURL: '', requestTimeoutMs: 4000 })
}

beforeEach(() => {
  vi.stubGlobal('fetch', makeFetch('summary'))
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('scheduler summary 消费（RFC 017 P1）', () => {
  it('summary 可用 → 用服务端归一化 lastStatus，字段映射正确（白盒经 fetchSchedulerTasks）', async () => {
    const svc = makeService() as any
    const tasks = await svc.fetchSchedulerTasks(V2, { timeoutMs: 4000 })
    expect(tasks).toHaveLength(1)
    expect(tasks[0].lastStatus).toBe('failed')
    expect(tasks[0].lastAt).toBe('2026-10-27T09:00:00+08:00')
    expect(tasks[0].lastError).toBe('engine down')
    expect(tasks[0].strategy).toBe('v13')
    expect(tasks[0].todayTriggered).toBe(1)
  })

  it('summary 404 → 回退旧端点 + 客户端归一化（假成功纠正不丢）', async () => {
    vi.stubGlobal('fetch', makeFetch('legacy404'))
    const svc = makeService() as any
    const tasks = await svc.fetchSchedulerTasks(V2, { timeoutMs: 4000 })
    expect(tasks).toHaveLength(1)
    expect(tasks[0].lastStatus).toBe('failed')
    expect(tasks[0].lastError).toBe('legacy-inner-boom')
  })

  it('summary 超时 → 回退旧端点（兼容期双跑契约）', async () => {
    vi.stubGlobal('fetch', makeFetch('legacyTimeout'))
    const svc = makeService() as any
    const tasks = await svc.fetchSchedulerTasks(V2, { timeoutMs: 4000 })
    expect(tasks).toHaveLength(1)
    expect(tasks[0].lastStatus).toBe('failed')
  })

  it('summary 与旧端点都不通 → scheduler 块报错进 meta.errors，core 不受影响', async () => {
    vi.stubGlobal('fetch', (async (url: string) => {
      if (url.includes('/api/scheduler/tasks')) throw new Error('请求超时(>4000ms)')
      return makeFetch('summary')(url)
    }) as typeof fetch)
    const svc = makeService()
    const { data, meta } = await svc.aggregate('acct_sum')
    expect(data.summary.totalValue).toBe(1)
    expect(meta.errors?.scheduler?.code).toBe('UPSTREAM_UNAVAILABLE')
  })
})
