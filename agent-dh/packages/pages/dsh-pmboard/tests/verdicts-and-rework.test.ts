/**
 * 验收单逐项裁决 + 回退实施单测（REQ-2e9473 t14/W6；REQ-308b9a FR-8 改语义）。
 *
 * serves: FR-8
 *
 * 走真实路由（证明逻辑在服务端）：全部通过 → 提示归档；有未过项 → **自动回退 implementing +
 * 按未过项建返工卡**（REQ-308b9a FR-8，**推翻 REQ-a8d582 FR-2 的"只记录"**）；
 * not_verifiable → 只记录、不回退、不建卡；版本不匹配 → 拒绝。
 *
 * 为什么不经 reqboard_verify_submit 造数据：本文件测的是**路由行为**，直接播种台账即可；
 * 验收单用 domain 的 buildSheet 生成，口径与提交路径同源，少一层无关依赖。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { applyVerdicts } from '../src/application/internal/verdicts.js'
import { FakeDocs } from './application/harness.js'
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

  it('T-I1: 有未过项 → 自动回退 implementing + 按未过项建返工卡（REQ-308b9a FR-8，AC-8.1/8.2）', async () => {
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
    expect(res.payload.data.rework_tasks).toHaveLength(1)
    const snap = store.snapshot()
    expect(snap.requirements[0].status).toBe('implementing')
    expect(snap.tasks).toHaveLength(before.tasks.length + 1)
    const rework = snap.tasks[snap.tasks.length - 1]!
    expect(rework.title).toMatch(/返工/)
    expect(rework.implementation).toMatch(/截图不清晰/)
    expect(rework.status).toBe('todo')
    expect(snap.requirements[0].verification!.sheet!.items.find(i => i.id === target.id)!.opinion).toBe('截图不清晰，请补高清图')
  })

  it('T-I3: 自动回退留痕——statusHistory 新增一条 + 评论存在（AC-8.4）', async () => {
    await seedAcceptingWithSheet()
    const sheet = store.snapshot().requirements[0].verification!.sheet!
    await post('/req/verdicts', {
      id: 'REQ-vd1234', version: sheet.version,
      verdicts: [{ itemId: sheet.items[0].id, status: 'failed', opinion: '有问题' }],
    })
    const r = store.snapshot().requirements[0]
    expect(r.status).toBe('implementing')
    const hist = r.statusHistory ?? []
    const last = hist[hist.length - 1]!
    expect(last.status).toBe('implementing')
    expect(String(last.reason ?? '')).toMatch(/自动回退/)
    expect(r.comments.some(c => String(c.body).includes('自动回退'))).toBe(true)
  })

  it('T-I4: not_verifiable 裁决 → 只记录、不回退、不建卡（AC-8.5）', async () => {
    await seedAcceptingWithSheet()
    const before = store.snapshot()
    const sheet = before.requirements[0].verification!.sheet!
    const res = await post('/req/verdicts', {
      id: 'REQ-vd1234', version: sheet.version,
      verdicts: [{ itemId: sheet.items[0].id, status: 'not_verifiable', opinion: '本机无该运行环境' }],
    })
    expect(res.statusCode).toBe(200)
    const snap = store.snapshot()
    expect(snap.requirements[0].status).toBe('accepting')
    expect(snap.tasks).toHaveLength(before.tasks.length)
    expect(snap.requirements[0].verification!.sheet!.items.find(i => i.id === sheet.items[0].id)!.status).toBe('not_verifiable')
  })

  it('T-I2: 回退原子性——mutate 内抛错则整笔不落（AC-8.3，故障注入）', async () => {
    await seedAcceptingWithSheet()
    const before = store.snapshot()
    const sheet = before.requirements[0].verification!.sheet!
    await expect(store.mutate('fault-inject', (l) => {
      applyVerdicts(l, l.requirements[0].id, sheet.version,
        [{ itemId: sheet.items[0].id, status: 'failed', opinion: '注入失败' }],
        { kind: 'human' }, Date.now(), () => 'c-fault')
      throw new Error('fault injection')
    })).rejects.toThrow('fault injection')
    const after = store.snapshot()
    expect(after.requirements[0].status).toBe('accepting')
    expect(after.tasks).toHaveLength(before.tasks.length)
  })

  it('退回返工端点：需求已因自动回退离开验收态 → 幂等拒绝、不重复建卡', async () => {
    await seedAcceptingWithSheet()
    const sheet = store.snapshot().requirements[0].verification!.sheet!
    const target = sheet.items.find(i => i.source.kind === 'task' && i.source.taskId === 't-vd0002')!
    // 裁决即自动回退（FR-8），此时需求已 implementing
    await post('/req/verdicts', {
      id: 'REQ-vd1234', version: sheet.version,
      verdicts: [{ itemId: target.id, status: 'failed', opinion: '截图不清晰，请补高清图' }],
    })
    const afterAuto = store.snapshot()
    expect(afterAuto.requirements[0].status).toBe('implementing')
    const cards = afterAuto.tasks.length
    // 再走「退回返工」端点 → 已不在验收态，被拒绝，不二次建卡
    const res = await post('/req/verify/rework', { id: 'REQ-vd1234', note: '再来一次' })
    expect(res.payload.success).toBe(false)
    expect(store.snapshot().tasks).toHaveLength(cards)
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

  it('T-I9: 裁决后回填 verification.md 的验收结果表（AC-7.7/7.8）', async () => {
    await seedAcceptingWithSheet()
    const docs = new FakeDocs(() => Date.now())
    const handler2 = createReqboardHandler({ store, now: () => Date.now(), docs: docs as never })
    const sheet = store.snapshot().requirements[0].verification!.sheet!
    const res = fakeRes()
    await handler2(
      fakeReq({ id: 'REQ-vd1234', version: sheet.version, verdicts: [{ itemId: sheet.items[0].id, status: 'passed' }] }, '/dashboard/api/reqboard/req/verdicts'),
      res,
    )
    expect(res.statusCode).toBe(200)
    const md = docs.files.get('docs/requirements/REQ-vd1234/verification.md')?.content ?? ''
    expect(md, md).toContain('| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |')
    expect(md, md).toContain('✓ 通过')
    expect(md, md).toContain('## 4. 验收结果')
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
