// serves: FR-1, FR-2, FR-5, FR-6, FR-9, FR-11
/**
 * T-5 接线单测（REQ-260926215013-1568）：七路回合订阅接线 + requirement-moved 不再直接续跑 + teardown 关闸。
 * 用假事件总线驱动真实的 wireDiveRoundSubscriptions 与 round 状态机。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { emptyLedger, type RequirementRecord } from '../src/shared/protocol.js'
import { createDiveRoundDriver, type DiveRoundPorts } from '../src/application/dive/round-driver.js'
import { wireDiveRoundSubscriptions, DIVE_ROUND_EVENTS } from '../src/application/dive/round-subscriptions.js'

function makeReq(): RequirementRecord {
  return {
    id: 'REQ-t', title: 't', description: '', status: 'implementing', blocked: false,
    comments: [], version: 5, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    sourceSessionId: 'agent-1', dive: { phase: 'active', activation: 'armed', roundsInStage: 0 },
  } as unknown as RequirementRecord
}

function harness() {
  const ledger = { ...emptyLedger(), requirements: [makeReq()], tasks: [], triages: [] } as never as {
    schemaVersion: number; revision: number; requirements: RequirementRecord[]; tasks: unknown[]; triages: unknown[]
  }
  const repo = {
    snapshot: () => ledger,
    read: async (fn: (v: unknown) => unknown) => fn(ledger),
    mutate: async (_r: string, fn: (l: unknown) => unknown) => {
      const before = JSON.stringify(ledger)
      const changed = fn(ledger) ?? {}
      if (JSON.stringify(ledger) !== before) ledger.revision += 1
      return { changed: changed as never, revision: ledger.revision }
    },
    replaceAll: async (_r: string, next: never) => { Object.assign(ledger, next) },
  }
  const inbox = { nextTurn: [] as unknown[], nextStep: [] as unknown[], prepend(t: string, m: unknown) { (t === 'next-step' ? this.nextStep : this.nextTurn).unshift(m) } }
  const agent: Record<string, unknown> = { id: 'agent-1', status: 'running', session: { id: 'agent-1' }, inbox }
  const delivered: unknown[] = []
  let n = 0
  const warns: string[] = []
  const ports: DiveRoundPorts = {
    repo: repo as never,
    agents: { get: (id) => (id === 'agent-1' ? agent : undefined), withoutInitiator: (op) => op() },
    fiberActive: () => true,
    delivery: {
      deliver: () => ({ delivered: true }),
      createRoundMessage: (input) => { n += 1; const message = { id: 'm' + n, role: 'user', content: [{ type: 'text', text: input.text }], source: { kind: 'dive', requirementId: input.requirementId, revision: input.revision, round: input.round } }; return { message, messageId: 'm' + n } },
      deliverMessage: (_w, m) => { delivered.push(m); inbox.nextTurn.push(m); agent.status = 'running'; return { delivered: true } },
    },
    cancel: () => {},
    whenIdle: async () => {},
    checkpoint: async () => {},
    renderRoundText: (i) => 'round ' + i.round,
    now: () => 1000,
    logger: { info: () => {}, debug: () => {}, warn: (m) => warns.push(m) },
  }
  const driver = createDiveRoundDriver(ports)
  const listeners = new Map<string, (...a: unknown[]) => unknown>()
  const bus = { on: (event: string, listener: (...a: unknown[]) => unknown) => { listeners.set(event, listener); return () => { listeners.delete(event) } } }
  const off = wireDiveRoundSubscriptions(bus, driver, { debug: () => {}, warn: (m) => warns.push(m) })
  return { driver, agent, delivered, warns, listeners, off, bus }
}

describe('T-5 · 七路回合订阅', () => {
  it('七个宿主事件全部订阅成立，且无告警（FR-11 响亮）', () => {
    const h = harness()
    expect([...h.listeners.keys()].sort()).toEqual([...DIVE_ROUND_EVENTS].sort())
    expect(h.warns).toEqual([])
  })
  it('宿主不提供事件总线 → 七条响亮告警，不静默降级（FR-11）', () => {
    const h = harness()
    const warns: string[] = []
    wireDiveRoundSubscriptions({}, h.driver, { debug: () => {}, warn: (m) => warns.push(m) })
    expect(warns.length).toBe(DIVE_ROUND_EVENTS.length)
    expect(warns.join(' ')).toContain('未成立')
  })
  it('requirement-moved 只置检查标志：忙时不投递，空闲后才起 1 轮（FR-6）', async () => {
    const h = harness()
    h.listeners.get('reqboard/requirement-moved')!({ requirementId: 'REQ-t' })
    await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(0) // agent 仍 running
    h.agent.status = 'idle'
    h.driver.onIdle(h.agent, () => {})
    await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(1)
  })
  it('pre-step 事件转交 round 半：伪造内容被拒（FR-1/FR-10）', async () => {
    const h = harness()
    h.agent.status = 'idle'
    h.driver.onIdle(h.agent, () => {})
    await h.driver.whenQuiet()
    const round = h.delivered[0] as { id: string; source: unknown }
    h.listeners.get('agent/inbox/claimed')!({ agent: h.agent, message: round })
    const forged = { id: round.id, content: [{ type: 'text', text: '篡改' }], source: round.source }
    const decision = await h.listeners.get('agent/pre-step')!({ agent: h.agent, messages: [forged], signal: { aborted: false } }, async () => ({ kind: 'enter', messages: [forged] }))
    expect(decision).toEqual({ kind: 'reject' })
    expect(h.warns.join(' ')).toContain('内容与登记不一致')
  })
  it('teardown 后触发不再投递（FR-5）', async () => {
    const h = harness()
    await h.driver.teardown()
    h.agent.status = 'idle'
    h.listeners.get('reqboard/requirement-moved')!({ requirementId: 'REQ-t' })
    h.driver.onIdle(h.agent, () => {})
    await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(0)
  })
})

describe('T-5 · 服务不再直接 followup', () => {
  it('ReqboardDiveManager.ts 里 0 处 followup（续跑不再由事件直投）', () => {
    const p = fileURLToPath(new URL('../src/application/dive/ReqboardDiveManager.ts', import.meta.url))
    const text = readFileSync(p, 'utf8')
    expect((text.match(/followup/g) ?? []).length).toBe(0)
  })
})
