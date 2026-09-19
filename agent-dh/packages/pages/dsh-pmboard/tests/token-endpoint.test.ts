import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { assembleRequirementToken } from '../src/application/query/QueryRequirementToken.js'
import { emptyBuckets, type ReqboardLedger, type TokenBuckets } from '../src/shared/protocol.js'

const B = (n: number): TokenBuckets => ({ uncachedInputTokens: n, outputTokens: n * 2, cacheReadTokens: n * 10, cacheWriteTokens: 0 })
const snap = (n: number) => ({ sessionId: 'session-w-001', at: n, totals: B(n), source: 'projection' as const })

function seededLedger(): ReqboardLedger {
  return {
    schemaVersion: 7,
    revision: 1,
    requirements: [{
      id: 'REQ-abc123', title: 'Token 需求', description: 'd', category: 'feature', status: 'implementing',
      blocked: false, sourceSessionId: 'session-w-001', comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
      statusHistory: [
        { status: 'draft', at: 1, by: { kind: 'agent', sessionId: 'session-w-001' }, tokenSnapshot: snap(1) },
        { status: 'implementing', at: 5, by: { kind: 'agent', sessionId: 'session-w-001' }, tokenSnapshot: snap(4) },
      ],
      tokenUsage: { byStage: { draft: B(3), implementing: B(7) }, totals: B(10), updatedAt: 9 },
    }],
    tasks: [{
      id: 't-abc123', requirementId: 'REQ-abc123', title: '任务甲', description: 'd', phase: 'implement', side: 'backend',
      dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance: 'a', context: '', status: 'in_progress',
      blocked: false, executions: [{
        id: 'e-abc123', sessionId: 'session-w-001', trigger: 'manual', startedAt: 1, endedAt: 2, outcome: 'succeeded',
        tokenUsage: { start: snap(2), end: snap(5), delta: B(3) },
      }],
      comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'agent', sessionId: 'session-w-001' }, updatedBy: { kind: 'agent', sessionId: 'session-w-001' },
      statusHistory: [],
    }],
    triages: [],
  }
}

let dir: string
let store: ReqboardStore
beforeEach(async () => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-token-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  await store.replaceAll('seed', seededLedger())
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
async function get(handler: any, url: string) {
  const res = fakeRes()
  await handler(fakeGet('/dashboard/api/reqboard' + url), res)
  return res
}

describe('REQ-a33899 t4 · assembleRequirementToken 投影', () => {
  it('节点有快照 → buckets 就位；无快照 → undefined（不是 0）；执行挂在 implementing', () => {
    const view = assembleRequirementToken(seededLedger().requirements[0]!, { tasks: seededLedger().tasks })
    const byKey = Object.fromEntries(view.byStage.map(s => [s.stage, s]))
    expect(byKey.draft!.buckets).toEqual(B(3))
    expect(byKey.implementing!.buckets).toEqual(B(7))
    expect(byKey.design!.buckets).toBeUndefined()
    expect(byKey.implementing!.executions).toHaveLength(1)
    expect(byKey.implementing!.executions[0]!.delta).toEqual(B(3))
    expect(byKey.design!.executions).toHaveLength(0)
    expect(view.totals).toEqual(B(10))
    expect(view.degraded).toBe(false)
  })

  it('需求无 tokenUsage → totals 全 0 且 degraded=true（无快照不等于花了 0）', () => {
    const r = { ...seededLedger().requirements[0]!, tokenUsage: undefined }
    const view = assembleRequirementToken(r, { tasks: [] })
    expect(view.totals).toEqual(emptyBuckets())
    expect(view.degraded).toBe(true)
    expect(view.byStage.every(s => s.buckets === undefined)).toBe(true)
  })
})

describe('REQ-a33899 t4 · HTTP 接口', () => {
  it('GET /requirements/:id/token → 200 返回 byStage + executions', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const res = await get(handler, '/requirements/REQ-abc123/token')
    expect(res.statusCode).toBe(200)
    expect(res.payload.success).toBe(true)
    expect(res.payload.data.requirementId).toBe('REQ-abc123')
    expect(res.payload.data.byStage).toHaveLength(7)
    const impl = res.payload.data.byStage.find((s: any) => s.stage === 'implementing')
    expect(impl.executions[0].taskId).toBe('t-abc123')
  })

  it('GET /requirements/:id/token 不存在 → 404 not_found', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const res = await get(handler, '/requirements/REQ-ffffff/token')
    expect(res.statusCode).toBe(404)
    expect(res.payload.code).toBe('not_found')
  })

  it('GET /state 带 tokenTotals（无快照的需求不出现该键）', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const res = await get(handler, '/state')
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.tokenTotals['REQ-abc123']).toBe(130) // B(10) 三桶和 = 13×10
  })

  it('GET /session/:sid/progress 的 nodes 带每节点 tokens（无快照则省略）', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const res = await get(handler, '/session/session-w-001/progress')
    expect(res.statusCode).toBe(200)
    const nodes = res.payload.data.nodes
    expect(Array.isArray(nodes)).toBe(true)
    const draft = nodes.find((n: any) => n.key === 'draft')
    const design = nodes.find((n: any) => n.key === 'design')
    expect(draft.tokens.total).toBe(39) // B(3) 三桶和 = 13×3
    expect(design.tokens).toBeUndefined()
  })
})
