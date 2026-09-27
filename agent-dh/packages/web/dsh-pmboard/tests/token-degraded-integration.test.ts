/**
 * 联调（integrate）：读路径 degraded 语义 —— 快照「缺失」与「不可得」同等计入（FR-7）。
 *
 * 被测变更：src/application/query/QueryRequirementToken.ts
 *   hasUnavailableSnapshot → hasSnapshotGap；degraded = req.tokenUsage 为 undefined || hasSnapshotGap(req, ledger)。
 *   ① 需求侧：状态事件缺 tokenSnapshot，或 source 非 projection → gap；
 *   ② 任务侧：执行运行中（endedAt 缺失）要求 start 可得；已闭合要求 start/end 均为 projection。
 *
 * 联调接口（HTTP 边界，真路由 + 真台账仓储 + 真 JSON 响应）：
 *   GET /dashboard/api/reqboard/requirements/:id/token
 *   请求样例：GET /dashboard/api/reqboard/requirements/REQ-gap-missing/token
 *   期望响应：200 { success: true, data: { requirementId: 'REQ-gap-missing', degraded: true, byStage: [ ... 7 项 ] } }
 *
 * 口径不变：byStage / executions / totals 装配逻辑与对外形状（degraded 仍是 boolean）均未改。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { taskStoreAt } from './queue/route-deps.js'
import { mkdtempSync, rmSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import type {
  ExecutionRecord,
  ReqboardLedger,
  RequirementRecord,
  RequirementTokenUsage,
  StatusEvent,
  TaskRecord,
  TokenBuckets,
  TokenSnapshot,
} from '../src/shared/protocol.js'

const B = (n: number): TokenBuckets => ({ uncachedInputTokens: n, outputTokens: n * 2, cacheReadTokens: n * 10, cacheWriteTokens: 0 })
const proj = (n: number): TokenSnapshot => ({ sessionId: 'session-w-001', at: n, totals: B(n), source: 'projection' })
const unavail = (n: number): TokenSnapshot => ({ sessionId: 'session-w-001', at: n, totals: B(0), source: 'unavailable' })
const USAGE: RequirementTokenUsage = { byStage: { draft: B(3), implementing: B(7) }, totals: B(10), updatedAt: 9 }

function ev(status: string, at: number, tokenSnapshot?: TokenSnapshot): StatusEvent {
  return { status, at, by: { kind: 'agent', sessionId: 'session-w-001' }, ...(tokenSnapshot !== undefined ? { tokenSnapshot } : {}) }
}
function exec(id: string, over: Partial<ExecutionRecord> = {}): ExecutionRecord {
  return { id, sessionId: 'session-w-001', trigger: 'manual', startedAt: 1, endedAt: 2, outcome: 'succeeded', ...over }
}
function task(id: string, requirementId: string, executions: ExecutionRecord[]): TaskRecord {
  return {
    id, requirementId, title: '任务 ' + id, description: 'd', phase: 'implement', side: 'backend',
    dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance: 'a', context: '', status: 'in_progress',
    blocked: false, executions, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'agent', sessionId: 'session-w-001' }, updatedBy: { kind: 'agent', sessionId: 'session-w-001' },
    statusHistory: [],
  } as TaskRecord
}
function makeReq(id: string, history: StatusEvent[], tokenUsage?: RequirementTokenUsage): RequirementRecord {
  return {
    id, title: '需求 ' + id, description: 'd', category: 'feature', status: 'implementing',
    blocked: false, sourceSessionId: 'session-w-001', comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: history,
    ...(tokenUsage !== undefined ? { tokenUsage } : {}),
  } as RequirementRecord
}

interface Case {
  readonly id: string
  readonly expectDegraded: boolean
  readonly why: string
  readonly history: StatusEvent[]
  readonly tokenUsage?: RequirementTokenUsage
  readonly execs: ExecutionRecord[]
}

const CASES: readonly Case[] = [
  {
    id: 'REQ-ok-all-proj', expectDegraded: false, why: '需求侧全 projection + 已闭合执行 start/end 均 projection → 无缺口',
    history: [ev('draft', 1, proj(1)), ev('implementing', 5, proj(4))],
    tokenUsage: USAGE,
    execs: [exec('e-1', { tokenUsage: { start: proj(2), end: proj(5), delta: B(3) } })],
  },
  {
    id: 'REQ-gap-missing', expectDegraded: true, why: '状态事件**缺 tokenSnapshot**（人从看板点按钮推进）→ 缺口（本次变更主项）',
    history: [ev('draft', 1), ev('implementing', 5, proj(4))],
    tokenUsage: USAGE,
    execs: [],
  },
  {
    id: 'REQ-gap-unavail', expectDegraded: true, why: '状态事件 source=unavailable（投影不可得）→ 缺口',
    history: [ev('draft', 1, proj(1)), ev('implementing', 5, unavail(0))],
    tokenUsage: USAGE,
    execs: [],
  },
  {
    id: 'REQ-run-open-ok', expectDegraded: false, why: '执行运行中（endedAt 缺失）只要求 start 可得 → start=projection 无缺口',
    history: [ev('implementing', 5, proj(4))],
    tokenUsage: USAGE,
    execs: [exec('e-1', { endedAt: undefined, outcome: 'running', tokenUsage: { start: proj(2) } })],
  },
  {
    id: 'REQ-run-open-gap', expectDegraded: true, why: '执行运行中但 start 不可得（无 tokenUsage）→ 缺口',
    history: [ev('implementing', 5, proj(4))],
    tokenUsage: USAGE,
    execs: [exec('e-1', { endedAt: undefined, outcome: 'running' })],
  },
  {
    id: 'REQ-closed-gap-end', expectDegraded: true, why: '执行已闭合（endedAt 有值）但缺 end 快照 → 缺口',
    history: [ev('implementing', 5, proj(4))],
    tokenUsage: USAGE,
    execs: [exec('e-1', { tokenUsage: { start: proj(2), delta: B(3) } })],
  },
  {
    id: 'REQ-no-events', expectDegraded: false, why: '无任何状态事件/执行（从未进入的节点不判缺失）→ 不误报',
    history: [],
    tokenUsage: USAGE,
    execs: [],
  },
]

function buildLedger(): ReqboardLedger {
  return {
    // v9：台账无 tasks 通道；schemaVersion 必须为 9（否则新的 reader 会撞迁移门）
    schemaVersion: 9,
    revision: 1,
    requirements: CASES.map(c => makeReq(c.id, c.history, c.tokenUsage)),
    triages: [],
  } as ReqboardLedger
}

/**
 * v9：执行记录随任务落**队列**。
 * 原判据 = "ledger.tasks 里带 executions 的卡"；新判据 = "队列里同一张卡的同一条执行"——
 * 每条执行仍是同一个 `task(...)` 构造（`tokenUsage` 形状未动），只是存储位置换了。
 */
function seedQueueTasks(root: string): Promise<unknown> {
  const store = taskStoreAt(root)
  return Promise.all(
    CASES.filter(c => c.execs.length > 0).map(c =>
      store.createMany(c.id, c.execs.map((e, i) => task(`t-${c.id.slice(4, 10)}-${i}`, c.id, [e]))),
    ),
  )
}

let dir: string
let store: ReqboardStore
let handler: ReturnType<typeof createReqboardHandler>

beforeEach(async () => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-token-degraded-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  await store.replaceAll('seed-degraded', buildLedger())
  await seedQueueTasks(dir)
  handler = createReqboardHandler({ taskStore: taskStoreAt(dir), store, now: () => Date.now() })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

function fakeRes(): any {
  const res: any = new EventEmitter()
  res.statusCode = 0
  res.payload = undefined
  res.writeHead = (code: number) => { res.statusCode = code; return res }
  res.end = (text?: string) => { res.payload = text === undefined ? undefined : JSON.parse(text); return res }
  return res
}
function fakeGet(url: string): any {
  const req = new EventEmitter() as any
  req.url = url
  req.method = 'GET'
  req[Symbol.asyncIterator] = async function* () { /* GET 无体 */ }
  return req
}
async function get(url: string) {
  const res = fakeRes()
  await handler(fakeGet('/dashboard/api/reqboard' + url), res)
  return res
}

describe('联调 · GET /dashboard/api/reqboard/requirements/:id/token（degraded：缺失与不可得同等计入）', () => {
  it.each(CASES.map(c => [c.id, c.expectDegraded, c.why] as const))(
    '%s → degraded=%s（%s）',
    async (id, expectDegraded, why) => {
      const res = await get(`/requirements/${id}/token`)
      const actual = res.payload?.data?.degraded
      // 联调证据：请求样例 → 期望 → 实际
      console.log(`[联调] GET /dashboard/api/reqboard/requirements/${id}/token | 期望 degraded=${expectDegraded} | 实际 degraded=${actual} | status=${res.statusCode} | 场景：${why}`)
      expect(res.statusCode).toBe(200)
      expect(res.payload.success).toBe(true)
      expect(res.payload.data.requirementId).toBe(id)
      expect(res.payload.data.byStage).toHaveLength(7)
      expect(typeof actual).toBe('boolean')
      expect(actual).toBe(expectDegraded)
    },
  )

  it('对外形状不变：byStage/executions/totals 装配与改动前一致（REQ-ok-all-proj）', async () => {
    const res = await get('/requirements/REQ-ok-all-proj/token')
    expect(res.payload.data.degraded).toBe(false)
    expect(res.payload.data.totals).toEqual(B(10))
    const byKey = Object.fromEntries(res.payload.data.byStage.map((s: any) => [s.stage, s]))
    expect(byKey.draft.buckets).toEqual(B(3))
    expect(byKey.implementing.buckets).toEqual(B(7))
    expect(byKey.design.buckets).toBeUndefined()
    expect(byKey.implementing.executions).toHaveLength(1)
    expect(byKey.implementing.executions[0].delta).toEqual(B(3))
  })

  it('degraded 为 true 时 totals/byStage 仍照常装配（缺口不吞数据）', async () => {
    const res = await get('/requirements/REQ-gap-missing/token')
    expect(res.payload.data.degraded).toBe(true)
    expect(res.payload.data.totals).toEqual(B(10))
    expect(res.payload.data.byStage).toHaveLength(7)
  })
})
