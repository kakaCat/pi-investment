// serves: FR-1, FR-4
// REQ-260927123256-196b t5（本文件的用例落点；口径见 design/test-cases.md）
/**
 * 确认弹框**缺省阻塞**（REQ-260927123256-196b t2 · serves: FR-1 / FR-4）。
 *
 * 锁死等待语义反转后的每条分支（design/test-cases.md）：
 *   · TC-1 缺省阻塞：不传宽限 + ask 永不 resolve → 200ms 仍未返回；resolve 后返回同步体且**无** pending/ticket；
 *   · TC-2 阻塞中登记未作答记录（守卫拦写），作答返回后守卫释放；
 *   · TC-7 中止（ASK_ABORTED / signal.aborted）→ pending+ticket+interrupted，status 可见，写路径仍被拒；
 *   · TC-8 取消（ASK_CANCELLED）→ 中性返回、无 pending/ticket、守卫放行、台账无落章；
 *   · TC-10 重新发起覆盖旧记录（旧记录 settle 为未确认）。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { taskStoreAt } from './queue/route-deps.js'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { SessionProbeAdapter } from '../src/adapters/SessionProbeAdapter.js'
import { RandomIdFactory } from '../src/adapters/RandomIdFactory.js'
import { UserQuestionsAdapter } from '../src/adapters/UserQuestionsAdapter.js'
import { PendingConfirmRegistry } from '../src/adapters/PendingConfirmRegistry.js'
import { defineAskConfirmTool, defineStatusTool, defineMoveTool } from '../src/tools/index.js'
import { assertNoPendingConfirm } from '../src/application/internal/support.js'
import type { AskAnswer, UseCaseDeps } from '../src/application/ports.js'
import type { RequirementRecord, StageArtifact } from '../src/shared/protocol.js'

const W = 'session-blocking-001'
const AFFIRM = '确认，推进到下一阶段 (Recommended)'
const ARGS = { target: 'artifact', kind: 'requirement', question: '需求文档已完成，是否确认进入设计？' }

let dir: string
let store: ReqboardStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-blocking-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

type AskFn = () => Promise<{ answers?: AskAnswer[] }>

function makeDeps(ask: AskFn): UseCaseDeps & { pendingConfirms: PendingConfirmRegistry } {
  const now = (): number => Date.now()
  const deps = {
    repo: store,

    taskStore: taskStoreAt(dir),
    docs: new FileDocRepository({ workspaceRoot: dir }),
    clock: { now },
    ids: new RandomIdFactory(),
    session: new SessionProbeAdapter({}),
    questions: new UserQuestionsAdapter(() => ({ ask })),
    doneThrottleMs: 0,
    pendingConfirms: new PendingConfirmRegistry({ now }),
  }
  return deps as unknown as UseCaseDeps & { pendingConfirms: PendingConfirmRegistry }
}

async function seed(): Promise<void> {
  // 产物路径真实落盘：确认落章会读产物（可打开性），缺文件会产生后台未捕获 rejection 噪声。
  mkdirSync(join(dir, 'docs/requirements/REQ-abc123'), { recursive: true })
  writeFileSync(join(dir, 'docs/requirements/REQ-abc123/requirement.md'), '# 阻塞确认\n')
  const r = {
    id: 'REQ-abc123', title: '阻塞确认', description: '', status: 'brainstorming', blocked: false,
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
const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms))

describe('缺省阻塞（FR-1）', () => {
  it('TC-1 不传宽限 + ask 永不 resolve → 200ms 仍未返回；resolve 后返回 confirmed/advanced 且无 pending/ticket', async () => {
    await seed()
    let resolveAsk: (v: { answers?: AskAnswer[] }) => void = () => {}
    const deferred = new Promise<{ answers?: AskAnswer[] }>((res) => { resolveAsk = res })
    const tool = defineAskConfirmTool(makeDeps(() => deferred)) as any

    const pending = tool.execute(ARGS, exec)
    const raced = await Promise.race([
      pending.then(() => 'returned' as const),
      sleep(200).then(() => 'still-pending' as const),
    ])
    expect(raced).toBe('still-pending')

    resolveAsk({ answers: [{ id: 'confirm', selected: [AFFIRM] }] })
    const out = await pending
    expect(out.confirmed).toBe(true)
    expect(out.advanced).toBe(true)
    expect(out.from).toBe('brainstorming')
    expect(out.to).toBe('design')
    expect('pending' in out).toBe(false)
    expect('ticket' in out).toBe(false)
    expect(first().status).toBe('design')
  })

  it('TC-2 阻塞中登记未作答记录（守卫拦写），作答返回后守卫释放', async () => {
    await seed()
    let resolveAsk: (v: { answers?: AskAnswer[] }) => void = () => {}
    const deferred = new Promise<{ answers?: AskAnswer[] }>((res) => { resolveAsk = res })
    const deps = makeDeps(() => deferred)
    const tool = defineAskConfirmTool(deps) as any

    const pending = tool.execute(ARGS, exec)
    await sleep(50)
    const live = deps.pendingConfirms.pendingForWindow(W)
    expect(live?.ticket.startsWith('pc-')).toBe(true)
    expect(() => assertNoPendingConfirm(deps, W)).toThrow(/REQBOARD_CONFIRM_PENDING/)

    resolveAsk({ answers: [{ id: 'confirm', selected: [AFFIRM] }] })
    const out = await pending
    expect(out.confirmed).toBe(true)
    expect(deps.pendingConfirms.pendingForWindow(W)).toBeUndefined()
    expect(() => assertNoPendingConfirm(deps, W)).not.toThrow()
  })

  it('TC-10 重新发起覆盖旧记录：旧记录 settle 为未确认，新确认正常落章', async () => {
    await seed()
    const deps = makeDeps(async () => ({ answers: [{ id: 'confirm', selected: [AFFIRM] }] }))
    const oldTicket = deps.pendingConfirms.register({
      windowKey: W, requirementId: 'REQ-abc123', target: 'artifact', kind: 'requirement',
    }).ticket
    const tool = defineAskConfirmTool(deps) as any
    const out = await tool.execute(ARGS, exec)
    expect(out.confirmed).toBe(true)
    expect(deps.pendingConfirms.get(oldTicket, W)?.outcome?.confirmed).toBe(false)
    expect(deps.pendingConfirms.pendingForWindow(W)).toBeUndefined()
  })
})

describe('中止 / 取消（FR-4）', () => {
  it('TC-7 中止（ASK_ABORTED + signal.aborted）→ pending+ticket+interrupted；status 可见；写路径仍被拒', async () => {
    await seed()
    const deps = makeDeps(() => Promise.reject(Object.assign(new Error('aborted'), { code: 'ASK_ABORTED' })))
    const tool = defineAskConfirmTool(deps) as any
    const out = await tool.execute(ARGS, { agent: { id: W }, signal: { aborted: true } })

    expect(out.success).toBe(false)
    expect(out.confirmed).toBe(false)
    expect(out.advanced).toBe(false)
    expect(out.pending).toBe(true)
    expect(out.interrupted).toBe(true)
    expect(typeof out.ticket).toBe('string')
    expect(String(out.ticket).startsWith('pc-')).toBe(true)
    expect(String(out.note)).toContain('reqboard_confirm_receipt(ticket="' + out.ticket + '")')
    expect(String(out.note)).toContain('看板')
    expect(String(out.note)).toContain('收到作答前不得产出下游产物')

    const status = await (defineStatusTool(deps) as any).execute({}, exec)
    expect(status.pending_confirms).toHaveLength(1)
    expect(status.pending_confirms[0].ticket).toBe(out.ticket)
    expect(status.pending_confirms[0].requirement_id).toBe('REQ-abc123')
    expect(status.pending_confirms[0].interrupted).toBe(true)
    expect(status.pending_confirms[0].recovery).toContain('reqboard_confirm_receipt')
    expect(status.pending_confirms[0].recovery).toContain('看板')

    await expect((defineMoveTool(deps) as any).execute({ to: 'in_progress' }, exec))
      .rejects.toMatchObject({ code: 'REQBOARD_CONFIRM_PENDING' })
  })

  it('TC-8 取消（ASK_CANCELLED）→ 中性返回、无 pending/ticket、守卫放行、台账无落章', async () => {
    await seed()
    const deps = makeDeps(() => Promise.reject(Object.assign(new Error('cancelled'), { code: 'ASK_CANCELLED' })))
    const tool = defineAskConfirmTool(deps) as any
    const out = await tool.execute(ARGS, exec)

    expect(out.success).toBe(false)
    expect(out.confirmed).toBe(false)
    expect(out.advanced).toBe(false)
    expect('pending' in out).toBe(false)
    expect('ticket' in out).toBe(false)
    expect(deps.pendingConfirms.pendingForWindow(W)).toBeUndefined()
    expect(() => assertNoPendingConfirm(deps, W)).not.toThrow()
    expect(first().artifacts?.[0]?.confirmedAt).toBeUndefined()
    expect(first().status).toBe('brainstorming')
  })
})
