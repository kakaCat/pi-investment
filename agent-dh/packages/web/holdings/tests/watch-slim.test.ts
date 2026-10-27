import { describe, expect, it } from 'vitest'
import { slimWatchRules, WATCH_CONTEXT_MAX_CHARS } from '../src/services/watch-slim'

const NOW = Date.parse('2026-10-27T00:00:00Z')
const LONG_CONTEXT = '洛阳钼业(603993) ' + '很长的监控理由'.repeat(200)

const RAW = [
  {
    id: 1,
    symbol: '603993.SH',
    enabled: true,
    account: 'agent_brain',
    context: LONG_CONTEXT,
    expires_at: '2026-12-01T00:00:00Z',
    conditions: [
      { type: 'price_break', params: { price: 13.55, direction: 'below', cooldown_sec: 1800 }, operator: 'below', threshold: 13.55 },
      { type: 'volume_surge', params: { multiple: 1.5 } },
    ],
    created_at: '2026-10-01T00:00:00Z',
    triggered_count: 9,
    internal_field: 'must-not-leak',
    value_ledger: { huge: 'x'.repeat(500) },
  },
  {
    id: 2,
    symbol: '600519',
    enabled: false,
    account: 'agent_brain',
    context: '已停用规则',
    conditions: [],
  },
  {
    id: 3,
    symbol: '600036',
    enabled: true,
    account: 'agent_brain',
    context: '已过期规则',
    expires_at: '2026-01-01T00:00:00Z',
    conditions: [],
  },
  {
    id: 4,
    symbol: '000963',
    enabled: true,
    account: null,
    context: { note: '通用观察' },
    conditions: [{ type: 'pct_change', operator: 'above', threshold: 5 }],
  },
]

describe('slimWatchRules：看板载荷最小契约', () => {
  it('只保留活跃规则（停用/过期剔除）', () => {
    const out = slimWatchRules(RAW, NOW)
    expect(out.map((r) => r.id)).toEqual([1, 4])
    expect(out.every((r) => r.enabled)).toBe(true)
  })

  it('只保留视图字段，内部字段不外泄', () => {
    const [first] = slimWatchRules(RAW, NOW)
    expect(Object.keys(first).sort()).toEqual(
      ['account', 'conditions', 'context', 'enabled', 'expires_at', 'id', 'symbol'].sort(),
    )
    expect((first as any).created_at).toBeUndefined()
    expect((first as any).triggered_count).toBeUndefined()
    expect((first as any).internal_field).toBeUndefined()
    expect((first as any).value_ledger).toBeUndefined()
  })

  it('context 截断到视图上限，conditions 剥掉调度参数', () => {
    const [first] = slimWatchRules(RAW, NOW)
    expect(typeof first.context).toBe('string')
    expect((first.context as string).length).toBe(WATCH_CONTEXT_MAX_CHARS)
    expect(first.context).toContain('洛阳钼业(603993)')

    expect(first.conditions[0]).toEqual({
      type: 'price_break',
      operator: 'below',
      threshold: 13.55,
      params: { price: 13.55, direction: 'below' },
    })
    expect((first.conditions[0] as any).cooldown_sec).toBeUndefined()
    expect(first.conditions[1]).toEqual({ type: 'volume_surge' })
  })

  it('载荷显著小于原始规则', () => {
    const fullBytes = Buffer.byteLength(JSON.stringify(RAW))
    const slimBytes = Buffer.byteLength(JSON.stringify(slimWatchRules(RAW, NOW)))
    expect(slimBytes).toBeLessThan(fullBytes / 2)
  })
})
