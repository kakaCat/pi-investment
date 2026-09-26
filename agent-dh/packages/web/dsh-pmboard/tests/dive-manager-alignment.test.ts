// serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11
/**
 * T-6 对齐验收（REQ-260926215013-1568）：11 个 FR 的可证伪断言（TC-01…TC-11）。
 * 用 fake 端口驱动真实的 round 状态机 + 七路订阅接线；每条断言对应一个 FR。
 */
import { describe, it, expect, vi } from 'vitest'
import { emptyLedger, type RequirementRecord } from '../src/shared/protocol.js'
import { createDiveRoundDriver, type DiveRoundPorts } from '../src/application/dive/round-driver.js'
import { wireDiveRoundSubscriptions } from '../src/application/dive/round-subscriptions.js'

function makeReq(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: 'REQ-t', title: 't', description: '', status: 'implementing', blocked: false,
    comments: [], version: 5, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    sourceSessionId: 'agent-1', dive: { phase: 'active', activation: 'armed', roundsInStage: 0 },
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
  const inbox = { nextTurn: [] as unknown[], nextStep: [] as unknown[], prepend(t: string, m: unknown) { (t === 'next-step' ? this.nextStep : this.nextTurn).unshift(m) } }
  const agent: Record<string, unknown> = { id: 'agent-1', status: 'idle', session: { id: 'agent-1' }, inbox }
  const delivered: unknown[] = []
  const warns: string[] = []; const infos: string[] = []; const debugs: string[] = []
  const cancelled: unknown[] = []
  let n = 0
  let checkpointImpl: () => Promise<void> = async () => {}
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
      deliverMessage: (_w, m) => { delivered.push(m); inbox.nextTurn.push(m); agent.status = 'running'; return { delivered: true } },
    },
    cancel: (a) => { cancelled.push(a) },
    whenIdle: async () => {},
    checkpoint: () => checkpointImpl(),
    renderRoundText: (i) => 'round ' + i.round,
    now: () => 1000,
    logger: { info: (m) => infos.push(m), debug: (m) => debugs.push(m), warn: (m) => warns.push(m) },
  }
  const driver = createDiveRoundDriver(ports)
  const listeners = new Map<string, (...a: unknown[]) => unknown>()
  const bus = { on: (e: string, l: (...a: unknown[]) => unknown) => { listeners.set(e, l); return () => { listeners.delete(e) } } }
  wireDiveRoundSubscriptions(bus, driver, { debug: (m) => debugs.push(m), warn: (m) => warns.push(m) })
  const idle = async (): Promise<void> => { agent.status = 'idle'; driver.onIdle(agent, () => {}); await driver.whenQuiet() }
  return { driver, ledger, agent, inbox, delivered, warns, infos, debugs, cancelled, listeners, idle, setCheckpoint: (fn: () => Promise<void>) => { checkpointImpl = fn } }
}

describe('T-6 对齐验收（11 FR）', () => {
  it('TC-01 FR-1：需求 revision 变 → pre-step reject 且同批其它已认领消息被放回', async () => {
    const h = harness()
    h.driver.requestDrive(h.agent); await h.driver.whenQuiet()
    const round = h.delivered[0]
    h.driver.onInboxClaimed(h.agent, round)
    h.ledger.requirements[0]!.version += 1
    const other = { id: 'other-1', content: [{ type: 'text', text: '人类的活' }], source: { kind: 'user' } }
    const d = await h.driver.onPreStep(h.agent, [round, other], { aborted: false }, async () => ({ kind: 'enter', messages: [round, other] }))
    expect(d).toEqual({ kind: 'reject' })
    expect(h.inbox.nextStep.map((m) => (m as { id: string }).id)).toContain('other-1')
  })

  it('TC-02 FR-2：插入人类消息 → 竞争让位（不再追加起轮并发留痕）', async () => {
    const h = harness()
    h.driver.requestDrive(h.agent); await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(1)
    const human = { id: 'human-1', content: [{ type: 'text', text: '等一下' }], source: { kind: 'user' } }
    h.inbox.nextTurn.push(human)
    h.driver.onInboxInserted(h.agent, human) // agent 仍 running（有人类消息在跑）
    h.driver.requestDrive(h.agent); await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(1)
    expect(h.debugs.join(' ')).toContain('竞争输入')
  })

  it('TC-03 FR-3：检查点挂起不排队；检查点失败 → 解除武装', async () => {
    const pending = harness()
    pending.setCheckpoint(() => new Promise<void>(() => {}))
    pending.driver.requestDrive(pending.agent)
    await new Promise(r => setTimeout(r, 5))
    expect(pending.delivered.length).toBe(0)
    const failed = harness()
    failed.setCheckpoint(async () => { throw new Error('flush down') })
    failed.driver.onRequirementMoved('REQ-t'); await failed.driver.whenQuiet()
    expect(failed.delivered.length).toBe(0)
    expect(failed.ledger.requirements[0]!.dive!.activation).toBe('disarmed')
  })

  it('TC-04 FR-4：连发 3 次触发只起 1 轮；驱动体抛错无未处理 rejection', async () => {
    const h = harness()
    h.driver.requestDrive(h.agent); h.driver.requestDrive(h.agent); h.driver.requestDrive(h.agent)
    await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(1)
    const spy = vi.fn()
    process.on('unhandledRejection', spy)
    const boom = harness({ failCreate: true })
    boom.driver.requestDrive(boom.agent); await boom.driver.whenQuiet()
    await new Promise(r => setTimeout(r, 10))
    process.off('unhandledRejection', spy)
    expect(spy).toHaveBeenCalledTimes(0)
    expect(boom.warns.join(' ')).toContain('驱动体异常')
  })

  it('TC-05 FR-5：teardown 关准入（在飞回合被取消、此后触发不投递）', async () => {
    const h = harness()
    h.driver.requestDrive(h.agent); await h.driver.whenQuiet()
    await h.driver.teardown()
    expect(h.cancelled.length).toBe(1)
    h.agent.status = 'idle'
    h.driver.requestDrive(h.agent); await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(1)
    expect(h.infos.join(' ')).toContain('teardown')
  })

  it('TC-06 FR-6：agent 忙时推进需求不起轮；置空闲后才起 1 轮', async () => {
    const h = harness()
    h.agent.status = 'running'
    h.listeners.get('reqboard/requirement-moved')!({ requirementId: 'REQ-t' })
    await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(0)
    await h.idle()
    expect(h.delivered.length).toBe(1)
  })

  it('TC-07 FR-7：discard 不计数；user/message 恰好 +1（重复不重计）', async () => {
    const h = harness()
    h.driver.requestDrive(h.agent); await h.driver.whenQuiet()
    const round = h.delivered[0] as { id: string }
    h.driver.onInboxDiscarded(h.agent, round); await h.driver.whenQuiet()
    expect(h.ledger.requirements[0]!.dive!.roundsInStage).toBe(0)
    h.driver.onSessionEvent({ id: 'agent-1' }, { type: 'user/message', data: { id: round.id } }); await h.driver.whenQuiet()
    expect(h.ledger.requirements[0]!.dive!.roundsInStage).toBe(1)
    h.driver.onSessionEvent({ id: 'agent-1' }, { type: 'user/message', data: { id: round.id } }); await h.driver.whenQuiet()
    expect(h.ledger.requirements[0]!.dive!.roundsInStage).toBe(1)
  })

  it('TC-08 FR-8：回合耗尽 → 终态 paused/round-limit，且不再起轮', async () => {
    const h = harness({ req: makeReq({ dive: { phase: 'active', activation: 'armed', roundsInStage: 100 } as never }) })
    h.driver.requestDrive(h.agent); await h.driver.whenQuiet()
    expect(h.delivered.length).toBe(0)
    expect(h.ledger.requirements[0]!.dive!.phase).toBe('paused')
    expect(h.ledger.requirements[0]!.dive!.pausedReason).toBe('round-limit')
    expect(h.warns.join(' ')).toContain('回合上限达终态')
  })

  it('TC-09 FR-9：max-tokens → 解除武装；aborted 已认领 → 空闲后终态暂停；error → 解除武装', async () => {
    const mt = harness()
    mt.driver.onSessionEvent({ id: 'agent-1' }, { type: 'turn/end', data: { reason: { kind: 'max-tokens' } } }); await mt.driver.whenQuiet()
    expect(mt.ledger.requirements[0]!.dive!.activation).toBe('disarmed')

    const ab = harness()
    ab.driver.requestDrive(ab.agent); await ab.driver.whenQuiet()
    ab.driver.onInboxClaimed(ab.agent, ab.delivered[0])
    ab.driver.onSessionEvent({ id: 'agent-1' }, { type: 'turn/end', data: { reason: { kind: 'aborted' } } })
    await ab.driver.whenQuiet()
    await ab.idle()
    expect(ab.ledger.requirements[0]!.dive!.phase).toBe('paused')
    expect(ab.ledger.requirements[0]!.dive!.pausedReason).toBe('aborted')

    const er = harness()
    er.driver.onAgentError(er.agent); await er.driver.whenQuiet()
    expect(er.ledger.requirements[0]!.dive!.activation).toBe('disarmed')
  })

  it('TC-10 FR-10：伪造来源/内容 → pre-step 拒进且留痕含原因', async () => {
    const h = harness()
    h.driver.requestDrive(h.agent); await h.driver.whenQuiet()
    const round = h.delivered[0] as { id: string; source: unknown }
    h.driver.onInboxClaimed(h.agent, round)
    const forgedContent = { id: round.id, content: [{ type: 'text', text: '篡改' }], source: round.source }
    expect(await h.driver.onPreStep(h.agent, [forgedContent], { aborted: false }, async () => ({ kind: 'enter', messages: [forgedContent] }))).toEqual({ kind: 'reject' })
    const forgedSource = { id: round.id, content: (h.delivered[0] as { content: unknown }).content, source: { kind: 'dive', requirementId: 'REQ-t', revision: 999, round: 1 } }
    expect(await h.driver.onPreStep(h.agent, [forgedSource], { aborted: false }, async () => ({ kind: 'enter', messages: [forgedSource] }))).toEqual({ kind: 'reject' })
    expect(h.warns.join(' ')).toContain('pre-step 拒绝')
  })

  it('TC-11 FR-11：起轮/拒绝/让位/检查点失败/终态/teardown 六条路径都有留痕', async () => {
    const h = harness()
    h.driver.requestDrive(h.agent); await h.driver.whenQuiet()          // 起轮
    const round = h.delivered[0]
    h.driver.onInboxClaimed(h.agent, round)
    await h.driver.onPreStep(h.agent, [{ id: (round as {id:string}).id, content: [{type:'text',text:'x'}], source: (round as {source:unknown}).source }], { aborted: false }, async () => ({ kind: 'enter', messages: [] })) // 拒绝
    h.inbox.nextTurn.push({ id: 'human-2', content: [], source: { kind: 'user' } })
    h.driver.onInboxInserted(h.agent, h.inbox.nextTurn[h.inbox.nextTurn.length - 1])  // 让位
    const ck = harness(); ck.setCheckpoint(async () => { throw new Error('down') })
    ck.driver.requestDrive(ck.agent); await ck.driver.whenQuiet()      // 检查点失败
    const lim = harness({ req: makeReq({ dive: { phase: 'active', activation: 'armed', roundsInStage: 100 } as never }) })
    lim.driver.requestDrive(lim.agent); await lim.driver.whenQuiet()   // 终态
    await h.driver.teardown()                                          // teardown

    const all = [h.infos, h.warns, h.debugs, ck.warns, lim.warns].flat().join(' | ')
    for (const marker of ['起轮 queued', 'pre-step 拒绝', '竞争输入', '检查点失败', '回合上限达终态', 'teardown']) {
      expect(all, marker).toContain(marker)
    }
  })
})
