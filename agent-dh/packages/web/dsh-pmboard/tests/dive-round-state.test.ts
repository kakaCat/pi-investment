// serves: FR-1, FR-5, FR-7, FR-8, FR-10
/**
 * T-1 契约单测（REQ-260926215013-1568）：回合来源、相位值域与驱动状态纯判定。
 * 覆盖：非 dive 来源不认、round 必须 = roundsInStage+1、内容不一致返回 false、
 * 竞态栅栏 fail-closed、上限来源与回落。
 */
import { describe, it, expect } from 'vitest'
import { isDiveRoundSource, type RequirementRecord } from '../src/shared/protocol.js'
import {
  deepEqualJson, sameQueued, roundReservationValid, roundLimitFor, renderDiveRoundText,
  isDrivableRequirement, type DriverState, type RoundAttempt,
} from '../src/application/dive/round-state.js'

const content = [{ type: 'text', text: '继续' }]

function req(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: 'REQ-t', title: 't', description: '', status: 'implementing', blocked: false,
    comments: [], version: 5, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    dive: { phase: 'active', activation: 'armed', roundsInStage: 0 },
    ...over,
  } as unknown as RequirementRecord
}
function attempt(over: Partial<RoundAttempt> = {}): RoundAttempt {
  return {
    requirementId: 'REQ-t', revision: 5, round: 1, messageId: 'm1', content,
    phase: 'claimed', cancelled: false, stale: false, ...over,
  }
}
function state(over: Partial<DriverState> = {}): DriverState {
  return { agent: {}, competingQueued: false, needsCheckpoint: false, requested: false, stopping: false, attempt: attempt(), ...over }
}
const src = { kind: 'dive', requirementId: 'REQ-t', revision: 5, round: 1 } as const
const check = (over: Record<string, unknown> = {}) => roundReservationValid({
  state: state(), content, source: src, req: req(), fiberActive: true, agentLive: true, ...over,
} as never)

describe('T-1 · 回合来源与内容不变量', () => {
  it('非 dive 来源不认', () => {
    expect(isDiveRoundSource({ kind: 'user' })).toBe(false)
    expect(isDiveRoundSource({ kind: 'plugin', plugin: 'x' })).toBe(false)
    expect(isDiveRoundSource(undefined)).toBe(false)
    expect(isDiveRoundSource({ kind: 'dive', requirementId: 'REQ-t', revision: 1, round: 0 })).toBe(false)
    expect(isDiveRoundSource({ kind: 'dive', requirementId: 'REQ-t', revision: 1, round: 1 })).toBe(true)
  })
  it('内容不一致返回 false（逐字比对）', () => {
    expect(deepEqualJson(content, [{ type: 'text', text: '继续' }])).toBe(true)
    expect(deepEqualJson(content, [{ type: 'text', text: '继续2' }])).toBe(false)
    expect(sameQueued(content, src, attempt())).toBe(true)
    expect(sameQueued([{ type: 'text', text: '篡改' }], src, attempt())).toBe(false)
  })
  it('source 字段不符（round/revision/requirement）不认', () => {
    expect(sameQueued(content, { ...src, round: 2 }, attempt())).toBe(false)
    expect(sameQueued(content, { ...src, revision: 6 }, attempt())).toBe(false)
    expect(sameQueued(content, { ...src, requirementId: 'REQ-x' }, attempt())).toBe(false)
  })
})

describe('T-1 · 竞态栅栏（round 必须 = roundsInStage+1）', () => {
  it('合法预留放行', () => expect(check()).toBe(true))
  it('未认领（queued）拒绝', () => expect(check({ state: state({ attempt: attempt({ phase: 'queued' }) }) })).toBe(false))
  it('stale / cancelled 拒绝', () => {
    expect(check({ state: state({ attempt: attempt({ stale: true }) }) })).toBe(false)
    expect(check({ state: state({ attempt: attempt({ cancelled: true }) }) })).toBe(false)
  })
  it('需求 revision 变了 → 拒绝', () => expect(check({ req: req({ version: 6 }) })).toBe(false))
  it('round 必须等于 roundsInStage+1 → 否则拒绝', () => {
    expect(check({ req: req({ dive: { phase: 'active', activation: 'armed', roundsInStage: 1 } as never }) })).toBe(false)
    expect(check({
      source: { ...src, round: 2 },
      state: state({ attempt: attempt({ round: 2 }) }),
      req: req({ dive: { phase: 'active', activation: 'armed', roundsInStage: 1 } as never }),
    })).toBe(true)
  })
  it('非 armed+active / 非 active fiber / agent 不活 → 拒绝', () => {
    expect(check({ req: req({ dive: { phase: 'paused', activation: 'armed', roundsInStage: 0 } as never }) })).toBe(false)
    expect(check({ req: req({ dive: { phase: 'active', activation: 'disarmed', roundsInStage: 0 } as never }) })).toBe(false)
    expect(check({ fiberActive: false })).toBe(false)
    expect(check({ agentLive: false })).toBe(false)
    expect(check({ state: state({ stopping: true }) })).toBe(false)
  })
})

describe('T-1 · 相位值域与上限来源', () => {
  it('phase=paused 可表达（FR-8 终态）', () => {
    const r = req({ dive: { phase: 'paused', activation: 'armed', roundsInStage: 3 } as never })
    expect(r.dive?.phase).toBe('paused')
    expect(isDrivableRequirement(r)).toBe(false)
  })
  it('roundLimitFor 取 stage-configs 权威值、未知回落 10', () => {
    expect(roundLimitFor('implementing')).toBe(100)
    expect(roundLimitFor('decomposing')).toBe(5)
    expect(roundLimitFor('nonsense')).toBe(10)
  })
  it('renderDiveRoundText 含回合号与状态', () => {
    const t = renderDiveRoundText({ requirementId: 'REQ-t', round: 2, status: 'implementing' })
    expect(t).toContain('第 2 回合'); expect(t).toContain('implementing')
  })
})
