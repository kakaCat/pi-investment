/**
 * 验收单逐项裁决 + 退回返工单测（REQ-2e9473 t14/W6；REQ-a8d582 FR-2 改语义）。
 *
 * serves: FR-2
 *
 * 走真实路由（证明逻辑在服务端）：全部通过 → 提示归档；有未过项 → **只记录**（留在验收态、
 * 不自动打回、不建返工卡）；人点「退回返工」→ 才回 implementing 并按未过项建卡；版本不匹配 → 拒绝。
 *
 * 为什么不经 reqboard_verify_submit 造数据：本文件测的是**路由行为**，直接播种台账即可；
 * 验收单用 domain 的 buildSheet 生成，口径与提交路径同源，少一层无关依赖。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { EventEmitter } from 'node:events'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { buildSheet } from '../src/domain/workflow/AcceptanceSheetSpec.js'
import type { RequirementRecord, VerificationSheet } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore
let handler: ReturnType<typeof createReqboardHandler>

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-verdicts-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  handler = createReqboardHandler({ store, now: () => Date.now() })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

/** 播种一条"验收态 + 已生成验收单"的需求（2 个任务 → 3 个验收项）。 */
async function seedAcceptingWithSheet(): Promise<void> {
  await store.mutate('seed', (l) => {
    const r = {
      id: 'REQ-vd1234', title: '看板需求', description: '', status: 'implementing', category: 'feature',
      blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
    } as unknown as RequirementRecord
    l.requirements.push(r)
    const mk = (id: string, title: string, acceptance: string) => ({
      id, requirementId: r.id, title, description: '', phase: 'implement', side: 'backend',
      dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance, context: '',
      status: 'done', blocked: false, executions: [], comments: [], version: 1,
      statusHistory: [], createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'agent', sessionId: W }, updatedBy: { kind: 'agent', sessionId: W },
    })
    l.tasks.push(mk('t-vd0001', '任务一', '单测绿') as never, mk('t-vd0002', '任务二', '截图可见') as never)
    return { requirements: [r] }
  })
  await store.mutate('seed-sheet', (l) => {
    const r = l.requirements[0]
    const built = buildSheet({
      sheetHistoryLength: 0,
      tasks: l.tasks.filter(t => t.requirementId === r.id).map(t => ({ id: t.id, title: t.title, acceptance: t.acceptance })),
      evidence: ['npx vitest run 全绿'],
      generatedAt: 1,
      generatedBy: { kind: 'agent', sessionId: W },
    })
    r.status = 'accepting'
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
async function post(url: string, body: unknown) {
  const res = fakeRes()
  await handler(fakeReq(body, '/dashboard/api/reqboard' + url), res)
  return res
}

describe('验收单逐项裁决（t14 / REQ-a8d582 FR-2）', () => {
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

  it('有未过项 → **只记录**：仍在 accepting、不建返工卡、note 指向「退回返工」', async () => {
    await seedAcceptingWithSheet()
    const before = store.snapshot()
    const sheet = before.requirements[0].verification!.sheet!
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
    // REQ-a8d582 FR-2：不再自动打回、不再自动建卡（退回是人的动作）
    expect(res.payload.data.rework_tasks).toEqual([])
    expect(res.payload.data.note).toMatch(/退回返工/)
    const snap = store.snapshot()
    expect(snap.requirements[0].status).toBe('accepting')
    expect(snap.tasks).toHaveLength(before.tasks.length)
    expect(snap.requirements[0].verification!.sheet!.items.find(i => i.id === target.id)!.opinion).toBe('截图不清晰，请补高清图')
  })

  it('退回返工（人的动作）→ 回 implementing + 按未过项建返工卡（含意见）', async () => {
    await seedAcceptingWithSheet()
    const sheet = store.snapshot().requirements[0].verification!.sheet!
    const target = sheet.items.find(i => i.source.kind === 'task' && i.source.taskId === 't-vd0002')!
    await post('/req/verdicts', {
      id: 'REQ-vd1234', version: sheet.version,
      verdicts: [{ itemId: target.id, status: 'failed', opinion: '截图不清晰，请补高清图' }],
    })
    const beforeRework = store.snapshot()
    const res = await post('/req/verify/rework', { id: 'REQ-vd1234', note: '请按验收意见返工' })
    expect(res.statusCode).toBe(200)
    const snap = store.snapshot()
    expect(snap.requirements[0].status).toBe('implementing')
    expect(snap.tasks).toHaveLength(beforeRework.tasks.length + 1)
    const rework = snap.tasks[snap.tasks.length - 1]!
    expect(rework.title).toMatch(/返工/)
    expect(rework.implementation).toMatch(/截图不清晰/)
    expect(rework.context).toMatch(/t-vd0002/)
    expect(rework.status).toBe('todo')
    // 状态已不在验收态时再次调用 → 被拒绝（不会二次建卡）
    const again = await post('/req/verify/rework', { id: 'REQ-vd1234', note: '再来一次' })
    expect(again.payload.success).toBe(false)
    expect(store.snapshot().tasks).toHaveLength(beforeRework.tasks.length + 1)
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
