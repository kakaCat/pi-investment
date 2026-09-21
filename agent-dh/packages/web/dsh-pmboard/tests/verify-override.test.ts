/**
 * serves: FR-1, FR-4
 *
 * 覆盖式通过单测（REQ-a8d582 FR-4）：有不合格项或**尚无验收材料**时，验收通过必须带
 * confirm_override（覆盖说明），并留痕进台账 acceptanceOverride + 评论 + 状态事件。
 *
 * 覆盖 = 例外：全过且材料齐全的通过**不该**带覆盖记录（否则台账全是噪声，复盘读不出例外）。
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
  dir = mkdtempSync(join(tmpdir(), 'pmboard-override-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  handler = createReqboardHandler({ store, now: () => Date.now() })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

function baseReq(id: string): RequirementRecord {
  return {
    id, title: '看板需求', description: '', status: 'accepting', category: 'feature',
    blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
  } as unknown as RequirementRecord
}

/** 播种验收态需求 + 一张验收单；failFirst=true 时把第一个任务项判为不通过。 */
async function seed(id: string, opts: { sheet: boolean; failFirst?: boolean }): Promise<void> {
  await store.mutate('seed', (l) => {
    const r = baseReq(id)
    l.requirements.push(r)
    if (opts.sheet === false) return { requirements: [r] }
    const task = {
      id: 't-ov0001', requirementId: r.id, title: '任务一', description: '', phase: 'implement', side: 'backend',
      dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance: '单测绿', context: '',
      status: 'done', blocked: false, executions: [], comments: [], version: 1, statusHistory: [],
      createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'agent', sessionId: W }, updatedBy: { kind: 'agent', sessionId: W },
    }
    l.tasks.push(task as never)
    const built = buildSheet({
      sheetHistoryLength: 0,
      tasks: [{ id: task.id, title: task.title, acceptance: task.acceptance }],
      evidence: ['npx vitest run 全绿'],
      generatedAt: 1,
      generatedBy: { kind: 'agent', sessionId: W },
    })
    const sheet = built.sheet as VerificationSheet
    if (opts.failFirst === true) {
      sheet.items[0]!.status = 'failed'
      sheet.items[0]!.opinion = '截图不清晰'
      sheet.items[0]!.decidedAt = 2
      sheet.items[0]!.decidedBy = { kind: 'human' }
    } else {
      for (const i of sheet.items) i.status = 'passed'
    }
    r.verification = {
      summary: '交付完成', evidence: ['npx vitest run 全绿'], submittedAt: 1,
      submittedBy: { kind: 'agent', sessionId: W }, sheet,
    }
    // 全过且材料齐全 → 同时登记 verification 产物（走非覆盖路径时产物闸门要求它）
    if (opts.failFirst !== true) {
      r.artifacts = [{ stage: 'accepting', kind: 'verification', path: 'docs/requirements/' + id + '/verification.md', registeredAt: 1, registeredBy: { kind: 'agent', sessionId: W } }]
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

describe('验收通过的覆盖语义（REQ-a8d582 FR-4）', () => {
  it('有不合格项且不带覆盖说明 → 400 + verify_override_required，状态不变', async () => {
    await seed('REQ-ov0001', { sheet: true, failFirst: true })
    const res = await post('/req/verify/pass', { id: 'REQ-ov0001' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('verify_override_required')
    expect(res.payload.error).toMatch(/不通过 1 项/)
    const r = store.snapshot().requirements[0]!
    expect(r.status).toBe('accepting')
    expect(r.acceptanceOverride).toBeUndefined()
  })

  it('带覆盖说明 → archived，且台账/评论/状态事件三处留痕', async () => {
    await seed('REQ-ov0002', { sheet: true, failFirst: true })
    // 播种的验收单里：任务项被判不通过，需求级项仍未裁决（pending 1）
    const detail = '看板覆盖通过：验收单 v1，不通过 1 项 / 未裁决 1 项'
    const res = await post('/req/verify/pass', { id: 'REQ-ov0002', confirm_override: detail })
    expect(res.statusCode).toBe(200)
    const r = store.snapshot().requirements[0]!
    expect(r.status).toBe('archived')
    expect(r.acceptanceOverride).toMatchObject({ detail, failed: 1, pending: 1, noMaterials: false })
    expect(r.acceptanceOverride!.by.kind).toBe('human')
    expect(r.acceptanceOverride!.at).toBeGreaterThan(0)
    expect(r.comments.some(c => c.body.includes(detail))).toBe(true)
    expect((r.statusHistory ?? []).some(e => (e.reason ?? '').includes(detail))).toBe(true)
  })

  it('尚无验收材料 + 覆盖说明 → archived（不报 missing_artifact），且标记 noMaterials', async () => {
    await seed('REQ-ov0003', { sheet: false })
    const res = await post('/req/verify/pass', {
      id: 'REQ-ov0003',
      confirm_override: '看板覆盖通过：尚无验收材料（无验收证据）',
    })
    expect(res.statusCode).toBe(200)
    const r = store.snapshot().requirements[0]!
    expect(r.status).toBe('archived')
    expect(r.acceptanceOverride).toMatchObject({ failed: 0, pending: 0, noMaterials: true })
  })

  it('尚无验收材料且不带覆盖说明 → 拒绝（按钮可见 ≠ 可以静默通过）', async () => {
    await seed('REQ-ov0004', { sheet: false })
    const res = await post('/req/verify/pass', { id: 'REQ-ov0004' })
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('verify_override_required')
    expect(res.payload.error).toMatch(/尚无验收材料/)
    expect(store.snapshot().requirements[0]!.status).toBe('accepting')
  })

  it('全过且材料齐全 → 不带覆盖照常通过，且**不写**覆盖记录（不回归）', async () => {
    await seed('REQ-ov0005', { sheet: true, failFirst: false })
    const res = await post('/req/verify/pass', { id: 'REQ-ov0005' })
    expect(res.statusCode).toBe(200)
    const r = store.snapshot().requirements[0]!
    expect(r.status).toBe('archived')
    expect(r.acceptanceOverride).toBeUndefined()
  })
})
