// serves: FR-3
/**
 * 弹框非阻塞投递 + 回执 单测（REQ-260924213231-b1c4 T-6 / FR-3）。
 *
 * 覆盖 design/test-cases.md：TC-5（超宽限挂起，不判失败）/ TC-6（宽限内作答=旧语义）/
 * TC-7（后台落章 + 回执以台账为准）/ TC-8（未知 ticket → REQBOARD_UNKNOWN_TICKET）/
 * TC-20（已确认不重复弹框）；并锁「未装配注册表 = 旧阻塞语义」这条兼容性矩阵。
 *
 * 断言口径（任务卡 acceptance）：questions.ask 永不 resolve + 宽限 20ms → 返回 pending=true
 * 且 ticket 非空、不抛错；作答后 reqboard_confirm_receipt(ticket) 返回 confirmed=true,
 * advanced=true 且台账 confirmedAt 已写。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { SessionProbeAdapter } from '../src/adapters/SessionProbeAdapter.js'
import { RandomIdFactory } from '../src/adapters/RandomIdFactory.js'
import { UserQuestionsAdapter } from '../src/adapters/UserQuestionsAdapter.js'
import { PendingConfirmRegistry } from '../src/adapters/PendingConfirmRegistry.js'
import { defineAskConfirmTool, defineConfirmReceiptTool } from '../src/tools/index.js'
import type { AgentDeliveryPort, AskAnswer, UseCaseDeps } from '../src/application/ports.js'
import type { RequirementRecord, StageArtifact } from '../src/shared/protocol.js'

const W = 'session-pending-001'
const AFFIRM = '确认，推进到下一阶段 (Recommended)'
const ARGS = { target: 'artifact', kind: 'requirement', question: '需求文档已完成，是否确认进入设计？' }

let dir: string
let store: ReqboardStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-pending-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

type AskFn = () => Promise<{ answers?: AskAnswer[] }>

/** 真适配器构造 UseCaseDeps；pending=true 才装配挂起确认注册表（缺省 = 旧阻塞语义）。 */
function makeDeps(ask: AskFn, opts: { pending?: boolean; delivery?: AgentDeliveryPort } = {}): UseCaseDeps {
  const now = (): number => Date.now()
  const deps = {
    repo: store,
    docs: new FileDocRepository({ workspaceRoot: dir }),
    clock: { now },
    ids: new RandomIdFactory(),
    session: new SessionProbeAdapter({}),
    questions: new UserQuestionsAdapter(() => ({ ask })),
    doneThrottleMs: 0,
  } as unknown as UseCaseDeps & Record<string, unknown>
  if (opts.pending === true) deps.pendingConfirms = new PendingConfirmRegistry({ now })
  if (opts.delivery !== undefined) deps.delivery = opts.delivery
  return deps
}

/** 台账 seed：statusHistory 以当前状态收尾（真实台账口径，回执据此还原 from）。 */
async function seed(): Promise<void> {
  const r = {
    id: 'REQ-abc123', title: '非阻塞确认', description: '', status: 'brainstorming', blocked: false,
    sourceSessionId: W, comments: [], version: 2, createdAt: 1, updatedAt: 2,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [
      { status: 'draft', at: 1, by: { kind: 'human' } },
      { status: 'brainstorming', at: 2, by: { kind: 'human' } },
    ],
    artifacts: [{
      stage: 'brainstorming', kind: 'requirement',
      path: 'docs/requirements/REQ-abc123/requirement.md', registeredAt: 1,
    } as StageArtifact],
  } as RequirementRecord
  await store.mutate('requirement-created', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

const exec = { agent: { id: W } }
const first = (): RequirementRecord => store.snapshot().requirements[0]

/** 轮询等待条件成立（后台续跑含异步落盘，固定 sleep 会 flaky）。 */
async function waitFor(fn: () => boolean, ms = 3000): Promise<void> {
  const start = Date.now()
  while (!fn()) {
    if (Date.now() - start > ms) throw new Error('waitFor 超时：条件未在 ' + ms + 'ms 内成立')
    await new Promise((r) => setTimeout(r, 5))
  }
}

describe('T-6 弹框非阻塞投递（FR-3 / I-3）', () => {
  it('TC-5 超宽限：questions.ask 永不 resolve + 宽限 20ms → pending=true + ticket，不抛、不判失败', async () => {
    await seed()
    const never = new Promise<{ answers?: AskAnswer[] }>(() => {})
    const tool = defineAskConfirmTool(makeDeps(() => never, { pending: true })) as any
    const out = await tool.execute({ ...ARGS, inline_grace_ms: 20 }, exec)
    expect(out.success).toBe(true)
    expect(out.pending).toBe(true)
    expect(out.confirmed).toBe(false)
    expect(out.advanced).toBe(false)
    expect(typeof out.ticket).toBe('string')
    expect(out.ticket.startsWith('pc-')).toBe(true)
    expect(out.requirement_id).toBe('REQ-abc123')
    // 超宽限不落章：台账未被改动
    expect(first().artifacts![0].confirmedAt).toBeUndefined()
    expect(first().status).toBe('brainstorming')
  })

  it('TC-6 宽限内作答肯定项 → 旧语义逐字回归（confirmed=true, advanced=true，无 pending 键）', async () => {
    await seed()
    const tool = defineAskConfirmTool(makeDeps(async () => ({ answers: [{ id: 'confirm', selected: [AFFIRM] }] }), { pending: true })) as any
    const out = await tool.execute(ARGS, exec)
    expect(out.confirmed).toBe(true)
    expect(out.advanced).toBe(true)
    expect(out.from).toBe('brainstorming')
    expect(out.to).toBe('design')
    expect(out.pending).toBeUndefined()
    expect(out.ticket).toBeUndefined()
    expect(first().status).toBe('design')
    expect(first().artifacts![0].confirmedVia).toBe('session')
  })

  it('宽限内作答非肯定项 → 不落章不推进，回执带用户意见', async () => {
    await seed()
    const tool = defineAskConfirmTool(makeDeps(async () => ({ answers: [{ id: 'confirm', selected: ['需要修改'], custom: '接口再想想' }] }), { pending: true })) as any
    const out = await tool.execute(ARGS, exec)
    expect(out.confirmed).toBe(false)
    expect(out.advanced).toBe(false)
    expect(out.user_choice).toBe('需要修改')
    expect(out.user_feedback).toBe('接口再想想')
    expect(first().artifacts![0].confirmedAt).toBeUndefined()
  })

  it('未装配注册表 = 旧阻塞语义：inline_grace_ms 不生效，等作答才返回', async () => {
    await seed()
    const slow: AskFn = async () => {
      await new Promise((r) => setTimeout(r, 30))
      return { answers: [{ id: 'confirm', selected: [AFFIRM] }] }
    }
    const tool = defineAskConfirmTool(makeDeps(slow)) as any // 不装配 pendingConfirms
    const out = await tool.execute({ ...ARGS, inline_grace_ms: 1 }, exec)
    expect(out.confirmed).toBe(true)
    expect(out.pending).toBeUndefined()
  })

  it('inline_grace_ms 非法 → REQBOARD_INVALID_INPUT（不静默回落）', async () => {
    await seed()
    const tool = defineAskConfirmTool(makeDeps(async () => ({ answers: [] }), { pending: true })) as any
    await expect(tool.execute({ ...ARGS, inline_grace_ms: -1 }, exec)).rejects.toMatchObject({ code: 'REQBOARD_INVALID_INPUT' })
  })
})

describe('T-6 回执（FR-3 / I-4）', () => {
  it('TC-7 超宽限 ticket → 作答后台落章 → reqboard_confirm_receipt 返回 confirmed=true, advanced=true', async () => {
    await seed()
    let resolveAsk: (v: { answers?: AskAnswer[] }) => void = () => {}
    const deferred = new Promise<{ answers?: AskAnswer[] }>((res) => { resolveAsk = res })
    const delivered: string[] = []
    const deps = makeDeps(() => deferred, {
      pending: true,
      delivery: { deliver: (w, m) => { delivered.push(w + ':' + m.text); return { delivered: true } } },
    })
    const askTool = defineAskConfirmTool(deps) as any
    const receiptTool = defineConfirmReceiptTool(deps) as any

    const pendingOut = await askTool.execute({ ...ARGS, inline_grace_ms: 20 }, exec)
    expect(pendingOut.pending).toBe(true)
    const ticket = String(pendingOut.ticket)

    // 人 5 分钟后作答 → 后台续跑（落章 + 推进 + 回填 + 唤醒）
    resolveAsk({ answers: [{ id: 'confirm', selected: [AFFIRM] }] })
    // 等**完整**后台落章（落章 + 推进两段 mutate），只等 confirmedAt 会撞上中间态。
    await waitFor(() => first().artifacts?.[0]?.confirmedAt !== undefined && first().status === 'design')

    const req = first()
    expect(req.status).toBe('design')
    expect(req.artifacts![0].confirmedVia).toBe('session')

    const out = await receiptTool.execute({ ticket }, exec)
    expect(out.success).toBe(true)
    expect(out.confirmed).toBe(true)
    expect(out.advanced).toBe(true)
    expect(out.from).toBe('brainstorming')
    expect(out.to).toBe('design')
    expect(out.requirement_id).toBe('REQ-abc123')
    // 唤醒窗口：投递过一次且带取回执命令
    expect(delivered).toHaveLength(1)
    expect(delivered[0]).toContain('reqboard_confirm_receipt')
  })

  it('TC-8 未知 ticket → REQBOARD_UNKNOWN_TICKET', async () => {
    await seed()
    const tool = defineConfirmReceiptTool(makeDeps(async () => ({ answers: [] }), { pending: true })) as any
    await expect(tool.execute({ ticket: 'pc-无' }, exec)).rejects.toMatchObject({ code: 'REQBOARD_UNKNOWN_TICKET' })
  })

  it('ticket 跨窗口不可取用（窗口绑定）→ REQBOARD_UNKNOWN_TICKET', async () => {
    await seed()
    const deps = makeDeps(async () => ({ answers: [] }), { pending: true })
    const ticket = deps.pendingConfirms!.register({
      windowKey: 'session-other', requirementId: 'REQ-abc123', target: 'artifact', kind: 'requirement',
    }).ticket
    const tool = defineConfirmReceiptTool(deps) as any
    await expect(tool.execute({ ticket }, exec)).rejects.toMatchObject({ code: 'REQBOARD_UNKNOWN_TICKET' })
  })

  it('挂起尚未作答 → 回执如实返回 confirmed=false（不判失败、不猜）', async () => {
    await seed()
    const never = new Promise<{ answers?: AskAnswer[] }>(() => {})
    const deps = makeDeps(() => never, { pending: true })
    const askTool = defineAskConfirmTool(deps) as any
    const receiptTool = defineConfirmReceiptTool(deps) as any
    const pendingOut = await askTool.execute({ ...ARGS, inline_grace_ms: 20 }, exec)
    const out = await receiptTool.execute({ ticket: String(pendingOut.ticket) }, exec)
    expect(out.success).toBe(true)
    expect(out.confirmed).toBe(false)
    expect(out.advanced).toBe(false)
    expect(String(out.note)).toContain('尚未作答')
  })

  it('后台作答为否定项 → 回执带 user_choice 且节点未推进', async () => {
    await seed()
    let resolveAsk: (v: { answers?: AskAnswer[] }) => void = () => {}
    const deferred = new Promise<{ answers?: AskAnswer[] }>((res) => { resolveAsk = res })
    const deps = makeDeps(() => deferred, { pending: true })
    const askTool = defineAskConfirmTool(deps) as any
    const receiptTool = defineConfirmReceiptTool(deps) as any
    const pendingOut = await askTool.execute({ ...ARGS, inline_grace_ms: 20 }, exec)
    resolveAsk({ answers: [{ id: 'confirm', selected: ['暂停'] }] })
    await waitFor(() => first().comments.some((c) => c.body.includes('未确认')))
    const out = await receiptTool.execute({ ticket: String(pendingOut.ticket) }, exec)
    expect(out.confirmed).toBe(false)
    expect(out.advanced).toBe(false)
    expect(out.user_choice).toBe('暂停')
    expect(first().status).toBe('brainstorming')
  })
})

describe('T-6 防重弹（回归）', () => {
  it('TC-20 产物已确认 → 不再弹框（弹框端口 0 次），返回「已确认」', async () => {
    await seed()
    let asked = 0
    const tool = defineAskConfirmTool(makeDeps(async () => {
      asked += 1
      return { answers: [{ id: 'confirm', selected: [AFFIRM] }] }
    }, { pending: true })) as any
    await tool.execute(ARGS, exec)
    const out = await tool.execute(ARGS, exec)
    expect(asked).toBe(1)
    expect(out.confirmed).toBe(true)
    expect(out.advanced).toBe(false)
    expect(String(out.note)).toContain('已确认')
  })
})
