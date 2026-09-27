/**
 * 看板 task/move 写时快照（REQ-260927121324-abde t4 / FR-4、FR-5）——行为用例。
 *
 * 两条对偶断言（缺失 ≠ 0 的最小可验证面）：
 *  ① **带 sessionId**：开工落执行记录并写 start；离开 in_progress 时经唯一入口闭合、
 *     写 end/delta（同会话相减）→ 读路径无缺口（degraded=false）；
 *  ② **无 sessionId**：什么都不写（不落执行记录、不碰 token 字段），读路径如实报
 *     degraded=true、totals 全 0——「不知道」绝不用 0 冒充。
 *
 * 走真实 HTTP 路由（不起真服务器），证明行为在**看板写路径**（不是用例内部）。
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
import {
  emptyBuckets,
  type ReqboardLedger,
  type TaskRecord,
  type TokenBuckets,
  type TokenSnapshot,
} from '../src/shared/protocol.js'

const W = 'session-w-001'
const B = (n: number): TokenBuckets => ({ uncachedInputTokens: n, outputTokens: n * 2, cacheReadTokens: n * 10, cacheWriteTokens: 0 })
const snap = (n: number, sessionId: string = W): TokenSnapshot => ({ sessionId, at: 1000 + n, totals: B(n), source: 'projection' })

let dir: string
let store: ReqboardStore
let taskStore: QueueTaskStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-task-move-snap-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  // 任务唯一存储 = 队列（REQ-260927202051-f6df：v9 台账已无 tasks 通道）
  taskStore = new QueueTaskStore({ repo: new JsonQueueRepository({ workspaceRoot: dir }), now: () => 100 })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

/**
 * 播种：implementing 需求 + 待开始任务。
 * withSnapshot=true 模拟「有会话进入该节点」（进入事件带 projection 快照）；
 * false 模拟「人从看板无会话推进」（事件缺快照，读路径必然 degraded）。
 */
function ledger(withSnapshot: boolean): ReqboardLedger {
  return {
    schemaVersion: 9,
    revision: 1,
    requirements: [{
      id: 'REQ-tm1234', title: '看板流转', description: '', category: 'feature', status: 'implementing',
      blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
      statusHistory: [{
        status: 'implementing', at: 1, by: { kind: 'human', sessionId: W },
        ...(withSnapshot ? { tokenSnapshot: snap(2) } : {}),
      }],
      ...(withSnapshot ? { tokenUsage: { byStage: { implementing: B(2) }, totals: B(2), updatedAt: 1 } } : {}),
    }],
    triages: [],
  } as unknown as ReqboardLedger
}

/** 待开始任务（落**队列**，v9 台账无 tasks 通道）。 */
const TASK = {
  id: 't-tm0001', requirementId: 'REQ-tm1234', title: '任务', description: '', phase: 'implement', side: 'backend',
  dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance: 'a', context: '', status: 'todo',
  blocked: false, executions: [], comments: [], version: 1, createdAt: 1, updatedAt: 1,
  createdBy: { kind: 'agent', sessionId: W }, updatedBy: { kind: 'agent', sessionId: W }, statusHistory: [],
} as unknown as TaskRecord

/** 播种看板：v9 台账（仅需求）+ 队列任务（任务唯一存储）。 */
async function seedBoard(withSnapshot: boolean): Promise<void> {
  await store.replaceAll('seed', ledger(withSnapshot))
  await taskStore.createMany('REQ-tm1234', [TASK])
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
function fakeGet(url: string): any {
  const req = new EventEmitter() as any
  req.url = url
  req.method = 'GET'
  req[Symbol.asyncIterator] = async function* () { /* GET 无体 */ }
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
async function get(handler: any, url: string) {
  const res = fakeRes()
  await handler(fakeGet('/dashboard/api/reqboard' + url), res)
  return res
}

describe('REQ-260927121324-abde t4 · 看板 task/move 的写时快照', () => {
  it('带 sessionId：开工写 start、完工写 end/delta，读路径无缺口', async () => {
    await seedBoard(true)
    let current = snap(2)
    const handler = createReqboardHandler({ store, taskStore, now: () => 100, tokenSnapshot: (k: string) => (k === W ? current : undefined) })

    const open = await post(handler, '/task/move', { id: 't-tm0001', to: 'in_progress', sessionId: W })
    expect(open.statusCode).toBe(200)
    let task = (await taskStore.listByRequirement('REQ-tm1234'))[0]!
    expect(task.executions).toHaveLength(1)
    expect(task.executions[0]!.tokenUsage!.start!.totals).toEqual(B(2))
    expect(task.executions[0]!.tokenUsage!.delta).toBeUndefined()

    current = snap(5)
    const close = await post(handler, '/task/move', { id: 't-tm0001', to: 'testing', sessionId: W })
    expect(close.statusCode).toBe(200)
    task = (await taskStore.listByRequirement('REQ-tm1234'))[0]!
    const exec = task.executions[0]!
    expect(exec.outcome).toBe('succeeded')
    expect(exec.endedAt).toBeDefined()
    expect(exec.tokenUsage!.end!.totals).toEqual(B(5))
    expect(exec.tokenUsage!.delta).toEqual(B(3))

    const token = await get(handler, '/requirements/REQ-tm1234/token')
    expect(token.statusCode).toBe(200)
    expect(token.payload.data.degraded).toBe(false)
  })

  it('无 sessionId：不写任何 token 字段，读路径如实 degraded（缺失不用 0 冒充）', async () => {
    await seedBoard(false)
    // 快照源其实可得——但只要请求没带会话，就不该去猜属于谁
    const handler = createReqboardHandler({ store, taskStore, now: () => 100, tokenSnapshot: () => snap(9) })

    await post(handler, '/task/move', { id: 't-tm0001', to: 'in_progress' })
    await post(handler, '/task/move', { id: 't-tm0001', to: 'testing' })
    const task = (await taskStore.listByRequirement('REQ-tm1234'))[0]!
    expect(task.executions).toHaveLength(0)
    expect(task.executions.some(e => e.tokenUsage !== undefined)).toBe(false)

    const token = await get(handler, '/requirements/REQ-tm1234/token')
    expect(token.statusCode).toBe(200)
    expect(token.payload.data.degraded).toBe(true)
    expect(token.payload.data.totals).toEqual(emptyBuckets())
  })
})
