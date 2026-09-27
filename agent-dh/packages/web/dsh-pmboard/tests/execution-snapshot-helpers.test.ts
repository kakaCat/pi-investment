import { describe, it, expect } from 'vitest'
import { makeHarness, req, task } from './application/harness.js'
import {
  closeExecutions,
  openExecution,
  refreshRunningExecution,
  safeWindowKey,
  snapshotForWindow,
  snapshotProviderFor,
} from '../src/application/internal/token-usage.js'
import {
  emptyBuckets,
  type TokenBuckets,
  type TokenSnapshot,
} from '../src/shared/protocol.js'

const B = (n: number): TokenBuckets => ({ uncachedInputTokens: n, outputTokens: n * 2, cacheReadTokens: n * 10, cacheWriteTokens: 0 })
const snap = (n: number, sessionId = 'session-w-001'): TokenSnapshot => ({ sessionId, at: 1000 + n, totals: B(n), source: 'projection' })
const unavailable = (): TokenSnapshot => ({ at: 1, totals: emptyBuckets(), source: 'unavailable' })

describe('REQ-260927121324-abde t1 · 执行快照收敛助手', () => {
  it('openExecution 落 running 记录并写 start（delta 待闭合时算）', () => {
    const t = task()
    const e = openExecution(t, { id: 'e-1', sessionId: 's', trigger: 'manual', at: 10 }, snap(2, 's'))
    expect(t.executions).toHaveLength(1)
    expect(e).toBe(t.executions[0])
    expect(e.outcome).toBe('running')
    expect(e.startedAt).toBe(10)
    expect(e.tokenUsage!.start!.totals).toEqual(B(2))
    expect(e.tokenUsage!.delta).toBeUndefined()
  })

  it('openExecution born-failed（outcome=failed）不写 start，直接以终止记录落账', () => {
    const t = task()
    const e = openExecution(t, { id: 'e-1', trigger: 'auto', at: 10, outcome: 'failed', error: 'gate' }, snap(2))
    expect(e.outcome).toBe('failed')
    expect(e.endedAt).toBe(10)
    expect(e.error).toBe('gate')
    expect(e.tokenUsage).toBeUndefined()
  })

  it('openExecution 无快照（snap=undefined）只落记录、不写 token 字段', () => {
    const t = task()
    const e = openExecution(t, { id: 'e-1', trigger: 'manual', at: 10 })
    expect(e.tokenUsage).toBeUndefined()
  })

  it('closeExecutions 闭合全部 running 并写 end/delta；返回条数', () => {
    const t = task()
    openExecution(t, { id: 'e-1', sessionId: 's', trigger: 'manual', at: 10 }, snap(2, 's'))
    openExecution(t, { id: 'e-2', sessionId: 's', trigger: 'manual', at: 11 }, snap(2, 's'))
    const closed = closeExecutions(t, { at: 20, outcome: 'succeeded' }, snap(5, 's'))
    expect(closed).toBe(2)
    for (const e of t.executions) {
      expect(e.outcome).toBe('succeeded')
      expect(e.endedAt).toBe(20)
      expect(e.tokenUsage!.end!.totals).toEqual(B(5))
      expect(e.tokenUsage!.delta).toEqual(B(3))
    }
  })

  it('closeExecutions 无快照只闭合记录（不写 end/delta）；已闭合的不再动', () => {
    const t = task()
    openExecution(t, { id: 'e-1', trigger: 'manual', at: 10 }, snap(2))
    const born = openExecution(t, { id: 'e-2', trigger: 'auto', at: 11, outcome: 'failed', error: 'x' })
    const closed = closeExecutions(t, { at: 20, outcome: 'failed', error: 'boom' })
    expect(closed).toBe(1)
    expect(born.outcome).toBe('failed')
    expect(t.executions[0]!.endedAt).toBe(20)
    expect(t.executions[0]!.error).toBe('boom')
    // snap=undefined：只闭合记录，不写 end/delta（start 是开工时已落的，保持不变）
    expect(t.executions[0]!.tokenUsage!.start!.totals).toEqual(B(2))
    expect(t.executions[0]!.tokenUsage!.end).toBeUndefined()
    expect(t.executions[0]!.tokenUsage!.delta).toBeUndefined()
  })

  it('refreshRunningExecution 刷新最近一条同会话 running 的 end/delta，不改 outcome', () => {
    const t = task()
    openExecution(t, { id: 'e-1', sessionId: 'other', trigger: 'manual', at: 10 }, snap(1, 'other'))
    openExecution(t, { id: 'e-2', sessionId: 's', trigger: 'manual', at: 11 }, snap(1, 's'))
    expect(refreshRunningExecution(t, snap(4, 's'), 's')).toBe(true)
    const e2 = t.executions[1]!
    expect(e2.outcome).toBe('running')
    expect(e2.tokenUsage!.end!.totals).toEqual(B(4))
    expect(e2.tokenUsage!.delta).toEqual(B(3))
    // 异会话那条没被动
    expect(t.executions[0]!.tokenUsage!.end).toBeUndefined()
  })

  it('refreshRunningExecution 无命中（无同会话 running）返回 false，不写', () => {
    const t = task()
    openExecution(t, { id: 'e-1', sessionId: 'other', trigger: 'manual', at: 10 }, snap(1, 'other'))
    expect(refreshRunningExecution(t, snap(4, 's'), 's')).toBe(false)
    expect(t.executions[0]!.tokenUsage!.end).toBeUndefined()
  })

  it('refreshRunningExecution 缺省 sessionId：刷新最近一条 running（不限会话）', () => {
    const t = task()
    openExecution(t, { id: 'e-1', sessionId: 'a', trigger: 'manual', at: 10 }, snap(1, 'a'))
    openExecution(t, { id: 'e-2', sessionId: 'b', trigger: 'manual', at: 11 }, snap(2, 'b'))
    expect(refreshRunningExecution(t, snap(5, 'b'))).toBe(true)
    // 命中最近一条（e-2）；e-1 保持不动（各自只刷自己的 end/delta）
    expect(t.executions[1]!.outcome).toBe('running')
    expect(t.executions[1]!.tokenUsage!.end!.totals).toEqual(B(5))
    expect(t.executions[1]!.tokenUsage!.delta).toEqual(B(3))
    expect(t.executions[0]!.tokenUsage!.end).toBeUndefined()
  })

  it('snapshotForWindow：窗口码缺失/空串 → undefined（不伪造）', () => {
    const h = makeHarness()
    h.session.tokenSnapshot = snap(3)
    expect(snapshotForWindow(h.deps, undefined)).toBeUndefined()
    expect(snapshotForWindow(h.deps, '')).toBeUndefined()
    expect(snapshotForWindow(h.deps, 'session-w-001')!.totals).toEqual(B(3))
  })

  it('snapshotForWindow：端口抛错 → unavailable（不阻断主流程）', () => {
    const h = makeHarness()
    h.session.tokenTotals = () => { throw new Error('boom') }
    const s = snapshotForWindow(h.deps, 'session-w-001')
    expect(s!.source).toBe('unavailable')
    expect(s!.totals).toEqual(emptyBuckets())
  })

  it('safeWindowKey：真实窗口码直取；system/空/缺 agent/抛错 → undefined', () => {
    const h = makeHarness()
    expect(safeWindowKey(h.deps, { agent: { id: 'session-w-001' } })).toBe('session-w-001')
    expect(safeWindowKey(h.deps, { agent: { id: 'system' } })).toBeUndefined()
    expect(safeWindowKey(h.deps, { agent: { id: '' } })).toBeUndefined()
    expect(safeWindowKey(h.deps, undefined)).not.toBe('system')
    h.session.windowKey = () => { throw new Error('REQBOARD_AGENT_REQUIRED') }
    expect(safeWindowKey(h.deps, {})).toBeUndefined()
  })

  it('safeWindowKey：端口返回非字符串 → undefined（脏值不当窗口码）', () => {
    const h = makeHarness()
    h.session.windowKey = () => 123 as unknown as string
    expect(safeWindowKey(h.deps, { agent: { id: 'x' } })).toBeUndefined()
  })

  it('snapshotProviderFor：显式窗口码优先，退回 req.sourceSessionId，都无 → undefined', () => {
    const h = makeHarness()
    const seen: string[] = []
    h.session.tokenTotals = (k: string) => { seen.push(k); return snap(7, k) }
    const explicit = snapshotProviderFor(h.deps, 'win-a')
    expect(explicit(req({ sourceSessionId: 'req-sess' }))!.totals).toEqual(B(7))
    expect(seen).toEqual(['win-a'])
    const fallback = snapshotProviderFor(h.deps)
    expect(fallback(req({ sourceSessionId: 'req-sess' }))!.totals).toEqual(B(7))
    expect(seen).toEqual(['win-a', 'req-sess'])
    expect(fallback(req({ sourceSessionId: undefined }))).toBeUndefined()
    expect(seen).toEqual(['win-a', 'req-sess'])
  })

  it('快照不可得（unavailable）落账但 delta 不产出（禁止编造）', () => {
    const t = task()
    openExecution(t, { id: 'e-1', sessionId: 's', trigger: 'manual', at: 10 }, unavailable())
    closeExecutions(t, { at: 20, outcome: 'succeeded' }, unavailable())
    const e = t.executions[0]!
    expect(e.tokenUsage!.start!.source).toBe('unavailable')
    expect(e.tokenUsage!.end!.source).toBe('unavailable')
    expect(e.tokenUsage!.delta).toBeUndefined()
  })
})
