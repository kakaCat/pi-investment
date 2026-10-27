/**
 * watch 分块载荷：聚合层必须输出 slim 契约（活跃 + 视图字段），
 * 不能把 v2 的 30+ 内部字段原样透传给看板。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PortfolioAggregationService } from '../src/services/portfolio-aggregation'

const V2 = 'http://v2.test'
const ACCOUNT = 'acct_watch'

const RAW_RULES = [
  {
    id: 1,
    symbol: '600519',
    enabled: true,
    account: 'agent_brain',
    context: '贵州茅台(600519) 止损监控 ' + 'x'.repeat(1000),
    conditions: [{ type: 'price_break', params: { price: 1400, direction: 'below', cooldown_sec: 60 } }],
    created_at: '2026-10-01T00:00:00Z',
    triggered_count: 3,
    internal_field: 'must-not-leak',
  },
  {
    id: 2,
    symbol: '000001',
    enabled: false,
    account: 'agent_brain',
    context: '停用规则',
    conditions: [],
  },
]

beforeEach(() => {
  vi.stubGlobal('fetch', async (url: string): Promise<Response> => {
    if (url.includes('/api/watch/rules')) {
      return new Response(JSON.stringify({ success: true, data: { rules: RAW_RULES } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    throw new Error('未打桩的 URL: ' + url)
  })
})
afterEach(() => { vi.unstubAllGlobals() })

describe('watch 分块 slim 契约', () => {
  it('只返回活跃规则，且不带内部字段', async () => {
    const svc = new PortfolioAggregationService({ v2BaseURL: V2, agentOsBaseURL: '', requestTimeoutMs: 4000 })
    const { data } = await svc.aggregate(ACCOUNT, { parts: ['watchRules'] })

    expect(data.watchRules).toHaveLength(1)
    const rule: any = data.watchRules![0]
    expect(rule.symbol).toBe('600519')
    expect(rule.context.length).toBeLessThanOrEqual(400)
    expect(rule.internal_field).toBeUndefined()
    expect(rule.created_at).toBeUndefined()
    expect(rule.triggered_count).toBeUndefined()
    expect(rule.conditions[0].params).toEqual({ price: 1400, direction: 'below' })
    expect(rule.conditions[0].params.cooldown_sec).toBeUndefined()
  })
})
