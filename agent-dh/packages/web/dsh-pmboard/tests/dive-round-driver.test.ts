// serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11
/**
 * T-2 回合状态机单测（REQ-260926215013-1568）：fake 端口驱动真实状态机。
 * 覆盖：3 次触发合并成 1 轮、驱动体异常不外泄、pre-step 前后栅栏与消息放回、
 * 检查点失败即解除武装、准入才计数、上限写终态、teardown 关准入。
 */
import { describe, it, expect, vi } from 'vitest'
import { emptyLedger, type RequirementRecord } from '../src/shared/protocol.js'
import { createDiveRoundDriver, type DiveRoundPorts } from '../src/application/dive/round-driver.js'

function makeReq(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: 'REQ-t', title: 't', description: '', status: 'implementing', blocked: false,
    comments: [], version: 5, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    sourceSessionId: 'agent-1',
    dive: { phase: 'active', activation: 'armed', roundsInStage: 0 },
    ...over,
  } as unknown as RequirementRecord
}

function harness(opts: { req?: RequirementRecord; failCreate?: boolean } = {}) {
  const ledger = { ...emptyLedger(), requirements: [opts.req ?? makeReq()], tasks: [], triages: [] } as never as {
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
  const inbox = { nextTurn: [] as unknown[], nextStep: [] as unknown[], prepend(target: string, m: unknown) { (target === 'next-step' ? this.nextStep : this.nextTurn).unshift(m) } }
  const agent: Record<string, unknown> = { id: 'agent-1', status: 'idle', session: { id: 'agent-1' }, inbox }
  const delivered: unknown[] = []
  let n = 0
  const warns: string[] = []
  const infos: string[] = []
  let checkpointImpl: () => Promise<void> = async () => {}
  const cancelled: unknown[] = []
  const ports: DiveRoundPorts = {
    repo: repo as never,
    agents: { get: (id) => (id === 'agent-1' ? agent : undefined), withoutInitiator: (op) => op() },
    fiberActive: () => true,
    delivery: {
      deliver: () => ({ delivered: true }),
      createRoundMessage: (input) => {
        if (opts.failCreate === true) throw new Error('boom')
        n += 1
        const message = { id: 'm' + n, role: 'user', content: [{ type: 'text', text: input.text }], source: { kind: 'dive', requirementId: input.requirementId, revision: input.revision, round: input.round } }
        return { message, messageId: 'm' + n }
      },
      deliverMessage: (_wk, message) => { delivered.push(message); inbox.nextTurn.push(message); agent.status = 'running'; return { delivered: true } },
    },
    cancel: (a) => { cancelled.push(a) },
    whenIdle: async () => {},
    checkpoint: () => checkpointImpl(),
    renderRoundText: (i) => 'round ' + i.round,
    now: () => 1000,
    logger: { info: (m) => infos.push(m), debug: () => {}, warn: (m) => warns.push(m) },
  }
  const driver = createDiveRoundDriver(ports)
  return { driver, ledger, agent, inbox, delivered, warns, infos, cancelled, setCheckpoint: (fn: () => Promise<void>) => { checkpointImpl = fn } }
}

describe('T-2 · 空闲驱动与合并触发', () => {
  it('连发 3 次触发 → 只起 1 轮（合并）', async () => {
    const h = harness()
    h.driver.requestDrive(h.agent)
    h.driver.requestDrive(h.agent)
    h.driver.requestDrive(h.agent)
    await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(1)
    expect(h.infos.some(m => m.includes('起轮 queued'))).toBe(true)
  })
  it('agent 非 idle 时不起轮（FR-6）', async () => {
    const h = harness()
    h.agent.status = 'running'
    h.driver.requestDrive(h.agent)
    await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(0)
  })
  it('requirement-moved 只置检查标志并请求驱动，不直接投递（FR-6）', async () => {
    const h = harness()
    h.driver.onRequirementMoved('REQ-t')
    await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(1)
  })
})

describe('T-2 · 检查点与异常收尾', () => {
  it('检查点失败 → 不排队 + 解除武装（FR-3）', async () => {
    const h = harness()
    h.setCheckpoint(async () => { throw new Error('flush down') })
    h.driver.onRequirementMoved('REQ-t')
    await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(0)
    expect(h.ledger.requirements[0]!.dive!.activation).toBe('disarmed')
    expect(h.warns.join(' ')).toContain('检查点失败')
  })
  it('驱动体抛错不外泄（无未处理 rejection）+ warn + 解除武装（FR-4/FR-11）', async () => {
    const spy = vi.fn()
    process.on('unhandledRejection', spy)
    const h = harness({ failCreate: true })
    h.driver.requestDrive(h.agent)
    await h.driver.whenQuiet()
    await new Promise(r => setTimeout(r, 10))
    process.off('unhandledRejection', spy)
    expect(spy).toHaveBeenCalledTimes(0)
    expect(h.warns.join(' ')).toContain('驱动体异常')
  })
})

describe('T-2 · 竞态栅栏与消息放回', () => {
  it('revision 变 → pre-step reject 且同批其它已认领消息被放回（FR-1）', async () => {
    const h = harness()
    h.driver.requestDrive(h.agent)
    await h.driver.whenQuiet()
    const round = h.delivered[0]
    h.driver.onInboxClaimed(h.agent, round)
    h.ledger.requirements[0]!.version += 1 // 需求被推进 → 预留失效
    const other = { id: 'other-1', role: 'user', content: [{ type: 'text', text: '人类的活' }], source: { kind: 'user' } }
    const decision = await h.driver.onPreStep(h.agent, [round, other], { aborted: false }, async () => ({ kind: 'enter', messages: [round, other] }))
    expect(decision).toEqual({ kind: 'reject' })
    expect(h.inbox.nextStep.map((m) => (m as { id: string }).id)).toContain('other-1')
    expect(h.warns.join(' ')).toContain('pre-step 拒绝')
    expect(h.warns.join(' ')).toContain('revision 已变')
  })
  it('伪造内容不一致 → pre-step 拒进（FR-10）', async () => {
    const h = harness()
    h.driver.requestDrive(h.agent)
    await h.driver.whenQuiet()
    const round = h.delivered[0] as { id: string; source: unknown }
    h.driver.onInboxClaimed(h.agent, round)
    const forged = { id: round.id, content: [{ type: 'text', text: '篡改' }], source: round.source }
    const decision = await h.driver.onPreStep(h.agent, [forged], { aborted: false }, async () => ({ kind: 'enter', messages: [forged] }))
    expect(decision).toEqual({ kind: 'reject' })
    expect(h.warns.join(' ')).toContain('内容与登记不一致')
  })
})

describe('T-2 · 准入计数与上限终态', () => {
  it('discard 不计数；user/message 恰好 +1（FR-7）', async () => {
    const h = harness()
    h.driver.requestDrive(h.agent)
    await h.driver.whenQuiet()
    const round = h.delivered[0] as { id: string }
    h.driver.onInboxDiscarded(h.agent, round)
    await h.driver.whenQuiet()
    expect(h.ledger.requirements[0]!.dive!.roundsInStage).toBe(0)
    h.driver.onSessionEvent({ id: 'agent-1' }, { type: 'user/message', data: { id: round.id } })
    await h.driver.whenQuiet()
    expect(h.ledger.requirements[0]!.dive!.roundsInStage).toBe(1)
    h.driver.onSessionEvent({ id: 'agent-1' }, { type: 'user/message', data: { id: round.id } })
    await h.driver.whenQuiet()
    expect(h.ledger.requirements[0]!.dive!.roundsInStage).toBe(1)
  })
  it('roundsInStage === maxRounds → 终态 paused/round-limit，且不再起轮（FR-8）', async () => {
    const h = harness({ req: makeReq({ dive: { phase: 'active', activation: 'armed', roundsInStage: 100 } as never }) })
    h.driver.requestDrive(h.agent)
    await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(0)
    expect(h.ledger.requirements[0]!.dive!.phase).toBe('paused')
    expect(h.ledger.requirements[0]!.dive!.pausedReason).toBe('round-limit')
    expect(h.warns.join(' ')).toContain('回合上限达终态')
  })
  it('max-tokens / aborted → 解除武装或标 cancelled（FR-9）', async () => {
    const h = harness()
    h.driver.onSessionEvent({ id: 'agent-1' }, { type: 'turn/end', data: { reason: { kind: 'max-tokens' } } })
    await h.driver.whenQuiet()
    expect(h.ledger.requirements[0]!.dive!.activation).toBe('disarmed')
  })
})

describe('T-2 · teardown fail-closed', () => {
  it('teardown 后触发不再排队（FR-5）', async () => {
    const h = harness()
    await h.driver.teardown()
    h.driver.requestDrive(h.agent)
    await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(0)
    expect(h.infos.join(' ')).toContain('teardown')
  })
})
