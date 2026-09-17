/**
 * 验收单逐项裁决 + 返工回路单测（REQ-2e9473 t14/W6）。
 * 走真实路由（证明逻辑在服务端）：全部通过 → 提示归档；有未过项 → 打回 implementing +
 * 自动生成关联返工任务；部分裁决 → 挂起；版本不匹配 → 拒绝。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { EventEmitter } from 'node:events'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { defineVerifySubmitTool } from './helpers/tool-deps.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore
let handler: ReturnType<typeof createReqboardHandler>
let verify: { execute: (a: unknown, e: unknown) => Promise<any> }

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-verdicts-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  handler = createReqboardHandler({ store, now: () => Date.now() })
  verify = defineVerifySubmitTool({ store, now: () => Date.now() } as never) as never
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seedAcceptingWithSheet(): Promise<void> {
  const r = {
    id: 'REQ-vd1234', title: '看板需求', description: '', status: 'implementing', category: 'feature',
    blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => {
    l.requirements.push(r)
    const mk = (id: string, title: string, acceptance: string) => ({
      id, requirementId: r.id, title, description: '', phase: 'implement', side: 'backend',
      dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance, context: '',
      status: 'done', blocked: false, executions: [], comments: [], version: 1,
      createdAt: 1, updatedAt: 1, createdBy: { kind: 'agent', sessionId: W }, updatedBy: { kind: 'agent', sessionId: W },
    })
    l.tasks.push(mk('t-vd0001', '任务一', '单测绿') as never, mk('t-vd0002', '任务二', '截图可见') as never)
    return { requirements: [r] }
  })
  // 提交验收单（rollup 会把需求推进 accepting）
  await verify.execute({ summary: '交付完成', evidence: ['npx vitest run 全绿'] }, { agent: { id: W } })
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
async function post(url: string, body: unknown) {
  const res = fakeRes()
  await handler(fakeReq(body, '/dashboard/api/reqboard' + url), res)
  return res
}

describe('验收单逐项裁决（t14）', () => {
  it('全部通过 → 留在 accepting，note 提示可点「验收通过」归档', async () => {
    await seedAcceptingWithSheet()
    const sheet = store.snapshot().requirements[0].verification!.sheet!
    const verdicts = sheet.items.map(i => ({ itemId: i.id, status: 'passed' }))
    const res = await post('/req/verdicts', { id: 'REQ-vd1234', version: sheet.version, verdicts })
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.passed).toBe(3)
    expect(res.payload.data.failed).toBe(0)
    expect(res.payload.data.note).toMatch(/验收通过/)
    expect(store.snapshot().requirements[0].status).toBe('accepting')
  })

  it('有未过项 → 打回 implementing + 生成关联返工任务（含意见）', async () => {
    await seedAcceptingWithSheet()
    const sheet = store.snapshot().requirements[0].verification!.sheet!
    const target = sheet.items.find(i => i.source.kind === 'task' && i.source.taskId === 't-vd0002')!
    const res = await post('/req/verdicts', {
      id: 'REQ-vd1234', version: sheet.version,
      verdicts: [
        { itemId: sheet.items[0].id, status: 'passed' },
        { itemId: target.id, status: 'failed', opinion: '截图不清晰，请补高清图' },
      ],
    })
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.failed).toBe(1)
    expect(res.payload.data.rework_tasks).toHaveLength(1)
    const snap = store.snapshot()
    expect(snap.requirements[0].status).toBe('implementing')
    const rework = snap.tasks.find(t => t.id === res.payload.data.rework_tasks[0])!
    expect(rework.title).toMatch(/返工/)
    expect(rework.implementation).toMatch(/截图不清晰/)
    expect(rework.context).toMatch(/t-vd0002/)
    expect(rework.status).toBe('todo')
  })

  it('部分裁决（仍有待验项）→ 挂起，状态不变', async () => {
    await seedAcceptingWithSheet()
    const sheet = store.snapshot().requirements[0].verification!.sheet!
    const res = await post('/req/verdicts', {
      id: 'REQ-vd1234', version: sheet.version,
      verdicts: [{ itemId: sheet.items[0].id, status: 'passed' }],
    })
    expect(res.payload.data.pending).toBe(2)
    expect(res.payload.data.note).toMatch(/挂起|断点/)
    expect(store.snapshot().requirements[0].status).toBe('accepting')
  })

  it('版本不匹配 → 拒绝（防并发错版）', async () => {
    await seedAcceptingWithSheet()
    const res = await post('/req/verdicts', {
      id: 'REQ-vd1234', version: 99,
      verdicts: [{ itemId: 'v99-1', status: 'passed' }],
    })
    expect(res.payload.success).toBe(false)
    expect(res.payload.error).toMatch(/版本不匹配/)
  })

  it('不通过项缺意见 → 拒绝', async () => {
    await seedAcceptingWithSheet()
    const sheet = store.snapshot().requirements[0].verification!.sheet!
    const res = await post('/req/verdicts', {
      id: 'REQ-vd1234', version: sheet.version,
      verdicts: [{ itemId: sheet.items[0].id, status: 'failed' }],
    })
    expect(res.payload.success).toBe(false)
    expect(res.payload.error).toMatch(/意见/)
  })
})
