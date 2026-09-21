/**
 * serves: FR-1, FR-2, FR-3, FR-4
 *
 * 端到端场景（REQ-a8d582 · 设计 test-cases.md TC-9）：**跨层**跑通
 * 「看板按钮的文案装配 → HTTP → 台账 → 看板重新渲染」这条链路。
 *
 * 链路：播种"实施完成 + 验收单已交" → 人逐项裁决打 1 项不通过（HTTP /req/verdicts）→
 * 断言自动回退实施 + 物化返工卡（REQ-308b9a 已**推翻** REQ-a8d582 FR-2 的"留在验收态"，
 * REQ-f0579a t1 据此改写本段）→ 模拟返工完成重新提交验收 → 用**看板按钮自己的**
 * verifyConfirmCopy 装配覆盖说明（FR-1）→ HTTP /req/verify/pass（FR-4）→ 台账 archived +
 * 三处留痕 → 用同一台账做客户端渲染，证明「验收通过」按钮不再出现、人工审核结论可见（FR-3 的终态）。
 *
 * 边界（诚实标注）：浏览器 leg 覆盖的是**文案装配与渲染函数**；DOM 事件绑定（window.confirm
 * 的点击链路）不在本用例范围，由 tests/board-info-fixes.test.ts 的文案用例与人手实测覆盖。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { EventEmitter } from 'node:events'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { buildSheet } from '../src/domain/workflow/AcceptanceSheetSpec.js'
import { buildReqDetail } from '../src/client/view.ts'
import { verifyConfirmCopy } from '../src/client/board-mount.ts'
import type { RequirementRecord } from '../src/shared/protocol.js'
import type { RequirementRecord as ClientRequirementRecord } from '../src/client/types.ts'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore
let handler: ReturnType<typeof createReqboardHandler>

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-e2e-override-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  handler = createReqboardHandler({ store, now: () => Date.now() })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

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

/** 播种"实施完成 + 已交验收材料"的需求（1 个任务 → 2 个验收项）。 */
async function seedDelivered(): Promise<void> {
  await store.mutate('seed', (l) => {
    const r = {
      id: 'REQ-e2e001', title: '验收通过二次确认', description: '', status: 'implementing', category: 'feature',
      blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
    } as unknown as RequirementRecord
    l.requirements.push(r)
    const task = {
      id: 't-e2e001', requirementId: r.id, title: '验收态按钮常显', description: '', phase: 'implement', side: 'frontend',
      dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance: 'npx vitest run 全绿', context: '',
      status: 'done', blocked: false, executions: [], comments: [], version: 1, statusHistory: [],
      createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'agent', sessionId: W }, updatedBy: { kind: 'agent', sessionId: W },
    }
    l.tasks.push(task as never)
    const built = buildSheet({
      sheetHistoryLength: 0,
      tasks: [{ id: task.id, title: task.title, acceptance: task.acceptance }],
      evidence: ['npx vitest run → 全绿'],
      generatedAt: 1,
      generatedBy: { kind: 'agent', sessionId: W },
    })
    r.status = 'accepting'
    r.verification = {
      summary: '按钮常显 + 二次确认已交付', evidence: ['npx vitest run → 全绿'], submittedAt: 1,
      submittedBy: { kind: 'agent', sessionId: W }, sheet: built.sheet as never,
    }
    return { requirements: [r] }
  })
}

describe('端到端：从验收单裁决到覆盖通过归档（TC-9）', () => {
  it('裁决不通过仍留在验收态 → 看板文案 → 覆盖通过 → 台账与渲染三处一致', async () => {
    await seedDelivered()
    const sheet = store.snapshot().requirements[0]!.verification!.sheet!
    const item = sheet.items.find(i => i.source.kind === 'task')!

    // ① 鉴别人打"不通过"：REQ-308b9a（推翻 REQ-a8d582 FR-2）——自动回退实施 + 物化返工卡
    const v = await post('/req/verdicts', {
      id: 'REQ-e2e001', version: sheet.version,
      verdicts: [{ itemId: item.id, status: 'failed', opinion: '按钮在无材料时仍然不显示' }],
    })
    expect(v.statusCode).toBe(200)
    expect(store.snapshot().requirements[0]!.status).toBe('implementing')
    const reworkTasks = store.snapshot().tasks.filter(t => t.requirementId === 'REQ-e2e001' && t.id !== 't-e2e001')
    expect(reworkTasks.length).toBe(1)

    // ①b 模拟执行窗口完成返工并重新提交验收：回到验收态（验收单裁决结果持久——不通过 1 / 未裁决 1）
    await store.mutate('seed', (l) => {
      const r = l.requirements[0]!
      r.status = 'accepting'
      return { requirements: [r] }
    })

    // ② 看板按钮自己的文案装配（FR-1）
    const clientReq = store.snapshot().requirements[0] as unknown as ClientRequirementRecord
    const copy = verifyConfirmCopy(clientReq)
    expect(copy.message).toContain('不通过 1')
    expect(copy.overrideDetail).toBeDefined()

    // ③ 人确认后按覆盖通过（FR-4）
    const pass = await post('/req/verify/pass', { id: 'REQ-e2e001', confirm_override: copy.overrideDetail })
    expect(pass.statusCode).toBe(200)
    const after = store.snapshot().requirements[0]!
    expect(after.status).toBe('archived')
    expect(after.acceptanceOverride!.detail).toBe(copy.overrideDetail)
    expect(after.acceptanceOverride!.failed).toBe(1)
    expect(after.comments.some(c => c.body.includes(copy.overrideDetail!))).toBe(true)
    expect((after.statusHistory ?? []).some(e => (e.reason ?? '').includes('带覆盖'))).toBe(true)

    // ④ 同一台账做客户端渲染：按钮消失、人工审核结论可见
    const html = buildReqDetail(after as unknown as ClientRequirementRecord, [], Date.now())
    expect(html).not.toContain('data-action="verify-pass"')
    expect(html).toContain('人工审核通过')
  })
})
