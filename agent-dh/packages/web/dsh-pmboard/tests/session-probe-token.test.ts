import { describe, it, expect } from 'vitest'
import { SessionProbeAdapter } from '../src/adapters/SessionProbeAdapter.js'
import { emptyBuckets, type TokenBuckets } from '../src/shared/protocol.js'

const BUCKETS: TokenBuckets = { uncachedInputTokens: 123, outputTokens: 45, cacheReadTokens: 678, cacheWriteTokens: 9 }

interface Opts {
  agents?: () => unknown
  sessionProjections?: () => unknown
}

function make(opts: Opts): SessionProbeAdapter {
  return new SessionProbeAdapter({ now: () => 1000, ...opts })
}

/** 默认：窗口 w-1 有会话 session-1（3 条事件），投影返回 {totals} 形状。 */
function agentsWith(session: unknown) {
  return () => ({ get: (id: string) => (id === 'w-1' ? { session } : undefined) })
}
function projectionsWith(state: unknown) {
  return () => ({ stateOf: (_s: unknown, kind: string) => (kind === 'tokenUsage' ? state : undefined) })
}

describe('SessionProbe.tokenTotals（REQ-a33899 t2）', () => {
  it('投影可得 → source=projection，四桶逐字段一致，取到 sessionId 与 seq', () => {
    const session = { id: 'session-1', snapshotEvents: () => [0, 1, 2] }
    const adapter = make({ agents: agentsWith(session), sessionProjections: projectionsWith({ totals: BUCKETS, last: null }) })
    expect(adapter.tokenTotals('w-1')).toEqual({ sessionId: 'session-1', seq: 2, at: 1000, totals: BUCKETS, source: 'projection' })
  })

  it('投影状态是裸四桶（无 totals 包裹）也识别', () => {
    const session = { id: 'session-1' }
    const adapter = make({ agents: agentsWith(session), sessionProjections: projectionsWith(BUCKETS) })
    const snap = adapter.tokenTotals('w-1')
    expect(snap.source).toBe('projection')
    expect(snap.totals).toEqual(BUCKETS)
    expect(snap.seq).toBeUndefined()
  })

  it('服务不可得（agents / projections 都缺）→ source=unavailable、全 0、不抛', () => {
    const adapter = make({})
    expect(adapter.tokenTotals('w-1')).toEqual({ at: 1000, totals: emptyBuckets(), source: 'unavailable' })
  })

  it('窗口无会话 → unavailable', () => {
    const adapter = make({ agents: () => ({ get: () => undefined }), sessionProjections: projectionsWith({ totals: BUCKETS }) })
    expect(adapter.tokenTotals('w-x').source).toBe('unavailable')
  })

  it('投影抛错 → unavailable（错误不向外传播）', () => {
    const session = { id: 'session-1' }
    const adapter = make({
      agents: agentsWith(session),
      sessionProjections: () => ({ stateOf: () => { throw new Error('projection unavailable') } }),
    })
    expect(adapter.tokenTotals('w-1').source).toBe('unavailable')
  })

  it('投影形状不符（缺桶）→ unavailable，不猜 0', () => {
    const session = { id: 'session-1' }
    const adapter = make({ agents: agentsWith(session), sessionProjections: projectionsWith({ totals: { uncachedInputTokens: 1 } }) })
    const snap = adapter.tokenTotals('w-1')
    expect(snap.source).toBe('unavailable')
    expect(snap.totals).toEqual(emptyBuckets())
  })
})
