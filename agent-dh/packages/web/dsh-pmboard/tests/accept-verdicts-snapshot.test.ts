/**
 * 逐项验收裁决触发自动回退时的写时快照（REQ-260927121324-abde t4 / FR-3、FR-8）。
 *
 * 有未过项 → 同笔 mutate 内自动回退 implementing（人工验收退回）。这条**自动回退事件**
 * 必须带写时快照，并结算离开 accepting 节点的差值进 byStage——否则「验收这一段花了多少」
 * 在台账里永远缺口。会话码取需求绑定的 sourceSessionId，取不到则诚实不传（本文件只锁正面）。
 *
 * 走真实 HTTP 路由（POST /req/verdicts），证明行为在服务端收敛点，不在测试内重算。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { JsonQueueRepository } from '../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../src/repositories/QueueTaskStore.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { buildSheet } from '../src/domain/workflow/AcceptanceSheetSpec.js'
import type { RequirementRecord, TaskRecord, TokenBuckets, TokenSnapshot, VerificationSheet } from '../src/shared/protocol.js'

const W = 'session-w-001'
const B = (n: number): TokenBuckets => ({ uncachedInputTokens: n, outputTokens: n * 2, cacheReadTokens: n * 10, cacheWriteTokens: 0 })
const snap = (n: number, sessionId: string = W): TokenSnapshot => ({ sessionId, at: 1000 + n, totals: B(n), source: 'projection' })

let dir: string
let store: ReqboardStore
let taskStore: QueueTaskStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-accept-verdicts-snap-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  // 任务唯一存储 = 队列（REQ-260927202051-f6df：v9 台账已无 tasks 通道）
  taskStore = new QueueTaskStore({ repo: new JsonQueueRepository({ workspaceRoot: dir }), now: () => 100 })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

/** 播种「验收态 + 进入 accepting 时的会话快照 + 已生成验收单」。 */
async function seed(): Promise<void> {
  // 任务**不写台账**（v9 无 tasks 通道）；mutate 回调是同步契约，`createMany` 异步 → 回调外写队列。
  const seededTasks: TaskRecord[] = []
  await store.mutate('seed', (l) => {
    const r = {
      id: 'REQ-av1234', title: '验收快照', description: '', status: 'accepting', category: 'feature',
      blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'agent', sessionId: W }, updatedBy: { kind: 'agent', sessionId: W },
      statusHistory: [{ status: 'accepting', at: 1, by: { kind: 'agent', sessionId: W }, tokenSnapshot: snap(2) }],
    } as unknown as RequirementRecord
    l.requirements.push(r)
    const mk = (id: string, title: string, acceptance: string) => ({
      id, requirementId: r.id, title, description: '', phase: 'implement', side: 'backend',
      dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance, context: '',
      status: 'done', blocked: false, executions: [], comments: [], version: 1,
      statusHistory: [], createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'agent', sessionId: W }, updatedBy: { kind: 'agent', sessionId: W },
    })
    seededTasks.push(mk('t-av0001', '任务一', '单测绿') as unknown as TaskRecord, mk('t-av0002', '任务二', '截图可见') as unknown as TaskRecord)
    return { requirements: [r] }
  })
  // ① 先写任务（队列）——回调外，`createMany` 幂等
  await taskStore.createMany('REQ-av1234', seededTasks)
  await store.mutate('seed-sheet', (l) => {
    const r = l.requirements[0]!
    const built = buildSheet({
      sheetHistoryLength: 0,
      tasks: seededTasks.filter(t => t.requirementId === r.id).map(t => ({ id: t.id, title: t.title, acceptance: t.acceptance })),
      evidence: ['npx vitest run 全绿'],
      generatedAt: 1,
      generatedBy: { kind: 'agent', sessionId: W },
    })
    r.verification = {
      summary: '交付完成', evidence: ['npx vitest run 全绿'], submittedAt: 1,
      submittedBy: { kind: 'agent', sessionId: W }, sheet: built.sheet as VerificationSheet,
    }
    return { requirements: [r] }
  })
}

function fakeReq(body: unknown, url: string): any {
  const req = new EventEmitter() as any
  req.url = url
  req.method = 'POST'
  req[Symbol.asyncIterator] = async function* () {
    if (body !== undefined) yield Buffer.from(JSON.stringify(body), 'utf8')
  }
  return req
}
function fakeRes(): any {
  const res: any = new EventEmitter()
  res.statusCode = 0
  res.writeHead = (code: number) => { res.statusCode = code; return res }
  res.end = (text?: string) => { res.payload = text === undefined ? undefined : JSON.parse(text); return res }
  return res
}
async function post(handler: any, url: string, body: unknown) {
  const res = fakeRes()
  await handler(fakeReq(body, '/dashboard/api/reqboard' + url), res)
  return res
}

describe('REQ-260927121324-abde t4 · 逐项 failed 自动回退事件带快照', () => {
  it('有未过项 → 自动回退事件带写时快照，离开 accepting 的差值进 byStage', async () => {
    await seed()
    const handler = createReqboardHandler({ store, taskStore, now: () => 100, tokenSnapshot: (k: string) => (k === W ? snap(5) : undefined) })
    const sheet = store.snapshot().requirements[0]!.verification!.sheet!

    const res = await post(handler, '/req/verdicts', {
      id: 'REQ-av1234', version: sheet.version,
      verdicts: [{ itemId: sheet.items[0]!.id, status: 'failed', opinion: '证据不清晰，请补高清图' }],
    })
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.failed).toBe(1)

    const r = store.snapshot().requirements[0]!
    expect(r.status).toBe('implementing')
    const last = r.statusHistory![r.statusHistory!.length - 1]!
    expect(last.status).toBe('implementing')
    expect(String(last.reason ?? '')).toMatch(/自动回退/)
    expect(last.tokenSnapshot!.source).toBe('projection')
    expect(last.tokenSnapshot!.totals).toEqual(B(5))
    expect(r.tokenUsage!.byStage.accepting).toEqual(B(3))
    expect(r.tokenUsage!.totals).toEqual(B(3))
  })
})
