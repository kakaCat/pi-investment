/**
 * Dive 会话驱动器装配 + "订阅失败改响亮"（2026-09-26；2026-09-26 二改：两路订阅）。
 *
 * 为什么单独测：两路订阅是整套事件驱动的总开关——采集路（session/event）挂不上 =
 * 证据缓冲/工具痕迹断源；驱动路（agent/status = idle，对齐 dsh-goal-round-driver）挂不上 =
 * 立项引导 / 待立项登记 / 阶段纪律注入 / 节点结算 / 里程碑催办 / 闸门链 Phase B / 断点补写
 * 全部静默停摆。此前只有一行 info 级 FAILED（可选链不抛），这正是"门禁失效而假绿"的同款。
 *
 * @module dsh-pmboard/tests/dive-session-driver-wiring
 */
import { describe, it, expect } from 'vitest'
import { assembleDiveSessionDriver } from '../src/wiring/pm-capture-root.js'
import { emptyLedger } from '../src/shared/protocol.js'

type SessionHandler = (s: unknown, e: unknown) => void
type StatusHandler = (a: unknown, st: unknown) => void

function makeDeps(
  attachSession: (h: SessionHandler) => (() => void) | undefined,
  attachAgentStatus: (h: StatusHandler) => (() => void) | undefined = () => () => {},
) {
  const warns: string[] = []
  const infos: string[] = []
  const deps = {
    store: { snapshot: () => emptyLedger() },
    runtime: {
      pendingCapture: new Map(),
      toolTrace: new Map(),
      recentUserMsgs: new Map(),
      deliverer: { deliver: () => ({ delivered: true }) },
    },
    now: () => 1,
    injectionLog: {},
    gateChain: { enqueue: () => {}, runPending: async () => ({ ran: false }) },
    onNodeSettled: () => {},
    useCaseDeps: () => ({}),
    logger: {
      info: (m: string) => infos.push(m),
      debug: () => {},
      warn: (m: string) => warns.push(m),
    },
    plugin: 'test',
    attachSessionDriver: attachSession,
    attachAgentStatus,
  }
  return { deps, warns, infos }
}

describe('Dive 会话驱动器装配（两路订阅生命周期归 Dive）', () => {
  it('两路订阅成立 → 返回解绑函数、info 登记成功、无 warn', () => {
    const { deps, warns, infos } = makeDeps(() => () => {}, () => () => {})
    const un = assembleDiveSessionDriver(deps as never)
    expect(typeof un).toBe('function')
    expect(warns).toEqual([])
    expect(infos.some(m => m.includes('dive session driver registered'))).toBe(true)
    expect(infos.some(m => m.includes('session/event=SUCCESS') && m.includes('agent/status=SUCCESS'))).toBe(true)
  })

  it('返回的合并解绑会同时解除两路订阅', () => {
    let sessionOff = 0
    let statusOff = 0
    const { deps } = makeDeps(() => () => { sessionOff++ }, () => () => { statusOff++ })
    const un = assembleDiveSessionDriver(deps as never)
    un?.()
    expect(sessionOff).toBe(1)
    expect(statusOff).toBe(1)
  })

  it('两路都没成立 → **响亮**：返回 undefined、warn 写明后果（不再只留 info）', () => {
    const { deps, warns } = makeDeps(() => undefined, () => undefined)
    const un = assembleDiveSessionDriver(deps as never)
    expect(un).toBeUndefined()
    const hit = warns.find(w => w.includes('订阅未成立'))
    expect(hit).toBeDefined()
    expect(hit).toContain('闸门链 Phase B')
    expect(hit).toContain('agent/status')
  })

  it('只装配一路 → 响亮 warn 指出缺哪一路（半接线不得假绿）', () => {
    const { deps, warns } = makeDeps(() => () => {}, () => undefined)
    const un = assembleDiveSessionDriver(deps as never)
    expect(typeof un).toBe('function')
    const hit = warns.find(w => w.includes('仅装配了一路订阅'))
    expect(hit).toBeDefined()
    expect(hit).toContain('agent/status=MISSING')
  })
})

// ────────────────────────────────────────────────────────────────────────────
// REQ-260927100007-b8ba FR-11：采集半零投递 + 里程碑只登记（投递白名单）
// ────────────────────────────────────────────────────────────────────────────

const FR11_W = 'session-fr11-001'

/**
 * 与装配同形状的接线：真 store（内存）+ 假 deliverer（计数）+ 假 round 半（记录 queueReminder）。
 * 断言的是**装配层**契约：采集半的任何路径都不得调用 deliverer.deliver（通用 plugin 投递）。
 */
function makeFr11Harness(opts: {
  status: string
  dive?: { activation: 'armed' | 'disarmed'; phase: 'idle' | 'active' | 'paused'; roundsInStage: number }
  staleArtifact?: boolean
  noRound?: boolean
  warns?: string[]
} = { status: 'implementing' }) {
  const now = 2000000000000
  const requirement = {
    id: 'REQ-fr11', title: 't', description: '', status: opts.status, category: 'feature',
    sourceSessionId: FR11_W, blocked: false, comments: [] as Array<{ body: string }>, version: 1,
    createdAt: 1, updatedAt: now, createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    ...(opts.dive === undefined ? {} : { dive: opts.dive }),
    ...(opts.staleArtifact === true
      ? { artifacts: [{ stage: opts.status, kind: 'requirement', path: 'r.md', registeredAt: now - 31 * 60 * 1000 }] }
      : {}),
  }
  const ledger = { ...emptyLedger(), requirements: [requirement], tasks: [], triages: [] } as never as {
    requirements: Array<{ comments: Array<{ body: string }> }>
  }
  const store = {
    snapshot: () => ledger,
    mutate: async (_reason: string, fn: (l: unknown) => unknown) => ({ changed: (fn(ledger) ?? {}) as never, revision: 1 }),
  }
  let sessionHandler: SessionHandler | undefined
  let statusHandler: StatusHandler | undefined
  let deliveries = 0
  const queueReminderCalls: Array<{ requirementId: string; text: string }> = []
  const round = {
    onIdle: (_agent: unknown, tick: () => void) => { tick() },
    onSessionEvent: () => {},
    queueReminder: (requirementId: string, text: string) => { queueReminderCalls.push({ requirementId, text }) },
  }
  const deps = {
    store,
    runtime: {
      pendingCapture: new Map(),
      toolTrace: new Map(),
      recentUserMsgs: new Map(),
      deliverer: { deliver: () => { deliveries += 1; return { delivered: true } } },
    },
    now: () => now,
    injectionLog: { record: () => {} },
    gateChain: { enqueue: () => {}, runPending: async () => ({ ran: false }) },
    onNodeSettled: () => {},
    useCaseDeps: () => ({}),
    logger: { info: () => {}, debug: () => {}, warn: (m: string) => { opts.warns?.push(m) } },
    plugin: 'test',
    attachSessionDriver: (h: SessionHandler) => { sessionHandler = h; return () => {} },
    attachAgentStatus: (h: StatusHandler) => { statusHandler = h; return () => {} },
    ...(opts.noRound === true ? {} : { round }),
  }
  assembleDiveSessionDriver(deps as never)
  return {
    ledger,
    queueReminderCalls,
    deliverCalls: () => deliveries,
    human: (text: string) => sessionHandler!(
      { id: FR11_W },
      { type: 'user/message', data: { content: [{ type: 'text', text }], source: { kind: 'user' } } },
    ),
    idle: () => statusHandler!({ id: FR11_W, session: { id: FR11_W } }, 'idle'),
  }
}

describe('REQ-260927100007-b8ba FR-11：采集半零投递 / 里程碑只登记', () => {
  it('(1) 同阶段连续两条直接人类消息 → 采集半零投递（deliverer.deliver 0 次、无额外轮次）', () => {
    const h = makeFr11Harness({ status: 'implementing' })
    h.human('第一条')
    h.idle()
    h.human('第二条')
    h.idle()
    expect(h.deliverCalls()).toBe(0)
    expect(h.queueReminderCalls).toHaveLength(0)
  })

  it('(3) 非 armed+active 的里程碑催办 → 只写台账 comment，不投递会话', async () => {
    const h = makeFr11Harness({ status: 'brainstorming', staleArtifact: true })
    h.human('继续')
    h.idle()
    await new Promise((r) => setTimeout(r, 0))
    expect(h.deliverCalls()).toBe(0)
    expect(h.queueReminderCalls).toHaveLength(0)
    expect(h.ledger.requirements[0].comments).toHaveLength(1)
    expect(h.ledger.requirements[0].comments[0].body).toContain('里程碑催办')
    expect(h.ledger.requirements[0].comments[0].body).toContain('reqboard_ask_confirm')
  })

  it('(2) armed+active 的里程碑催办 → 转 round 半 queueReminder（采集半仍零直投）', () => {
    const h = makeFr11Harness({
      status: 'brainstorming',
      dive: { activation: 'armed', phase: 'active', roundsInStage: 0 },
      staleArtifact: true,
    })
    h.human('继续')
    h.idle()
    expect(h.deliverCalls()).toBe(0)
    expect(h.queueReminderCalls).toHaveLength(1)
    expect(h.queueReminderCalls[0].requirementId).toBe('REQ-fr11')
    expect(h.queueReminderCalls[0].text).toContain('里程碑提醒')
  })

  it('armed+active 但 round 半未装配 → 响亮 warn（不静默丢）', () => {
    const warns: string[] = []
    const h = makeFr11Harness({
      status: 'brainstorming',
      dive: { activation: 'armed', phase: 'active', roundsInStage: 0 },
      staleArtifact: true,
      noRound: true,
      warns,
    })
    h.human('继续')
    h.idle()
    expect(h.deliverCalls()).toBe(0)
    expect(warns.some((w) => w.includes('round 半未装配'))).toBe(true)
  })
})
