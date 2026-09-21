/**
 * 计划模式（plan mode）端到端单测 —— 拆分必须在「计划已批准」之后发生。
 *
 * 背景（用户要求「superpowers 的 plan 模式版本」）：拆分的闸门要落在**计划**上，
 * 而不是落在"已拆分"这个状态上。本组测试用真实 Store + 真实路由锁死：
 *   未提交计划 → 拒绝；提交未批准 → 拒绝；人批准 → 才可落库；
 *   落库内容必须等于批准的计划（批了 A 不能落库 B）；重提交自动作废旧批准。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { definePlanSubmitTool, defineDecomposeTool, defineTaskMoveTool, defineTaskReportTool, stubDocFile } from './helpers/tool-deps.js'
import type { RequirementRecord, RequirementStatus } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore
let planTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let decompose: { execute: (a: unknown, e: unknown) => Promise<any> }
let taskMove: { execute: (a: unknown, e: unknown) => Promise<any> }
let handler: ReturnType<typeof createReqboardHandler>
let reportTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let trace: Map<string, import('../src/adapters/SessionProbeAdapter.js').ToolTraceEntry[]>

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-plan-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  trace = new Map()
  const deps = { store, now: () => Date.now(), toolTrace: trace, doneThrottleMs: 0 } as never
  planTool = definePlanSubmitTool(deps) as never
  decompose = defineDecomposeTool(deps) as never
  taskMove = defineTaskMoveTool(deps) as never
  reportTool = defineTaskReportTool(deps) as never
  handler = createReqboardHandler({ store, now: () => Date.now() })
  // REQ-2d1c74 FR-5：plan_submit 起要求提交路径真实落盘
  for (const p of ['p.md', 'docs/requirements/REQ-abc123/decomposition.md']) stubDocFile(p)
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seed(status: RequirementStatus = 'decomposing'): Promise<RequirementRecord> {
  const r = {
    id: 'REQ-abc123', title: '看板需求', description: '', status, blocked: false,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [{ status: 'draft', at: 1, by: { kind: 'human' } }],
  } as RequirementRecord
  await store.mutate('requirement-created', (l) => { l.requirements.push(r); return { requirements: [r] } })
  return r
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown, agent = W) =>
  tool.execute(args, { agent: { id: agent } })

const PLAN_TASKS = [
  { key: 'proto', title: '协议层加计划字段', phase: 'implement', side: 'backend', acceptance: 'protocol.ts 单测绿', implementation: 'protocol.ts 加 PlanRecord + 单测验证' },
  { key: 'ui', title: '看板计划卡与批准按钮', phase: 'ui', side: 'frontend', depends_on: ['proto'], acceptance: '截图可见', implementation: 'view.ts 加计划卡渲染与批准按钮' },
]

const submitPlan = (tasks: unknown = PLAN_TASKS) =>
  run(planTool, { path: 'docs/requirements/REQ-abc123/decomposition.md', summary: '目标：加计划模式；做法：先提交计划再拆', tasks })

// -- 路由：人的裁决（真 HTTP 全链路，证明闸门在服务端）-----------------------

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

// -- 测试 -----------------------------------------------------------------

describe('计划闸门（拆分前必须先有计划且获批）', () => {
  it('未提交计划 → 拆分被拒（REQBOARD_PLAN_NOT_APPROVED）', async () => {
    await seed('decomposing')
    await expect(run(decompose, {})).rejects.toThrow(/REQBOARD_PLAN_NOT_APPROVED/)
    expect(store.snapshot().tasks).toHaveLength(0)
  })

  it('已提交但未批准 → 仍被拒；落库内容为空', async () => {
    await seed('decomposing')
    const out = await submitPlan()
    expect(out.plan_status).toBe('pending_approval')
    expect(out.task_count).toBe(2)
    await expect(run(decompose, {})).rejects.toThrow(/还没有已批准的拆分计划/)
    expect(store.snapshot().tasks).toHaveLength(0)
    // 计划已进台账（供人审批）
    const req = store.snapshot().requirements[0]
    expect(req.plan?.path).toBe('docs/requirements/REQ-abc123/decomposition.md')
    expect(req.plan?.approvedAt).toBeUndefined()
    expect(req.comments.some(c => c.body.includes('[计划] 提交拆分计划'))).toBe(true)
  })

  it('人批准后 → 落库的正是批准的那张任务表（key 映射成 id、依赖成链、需求自动进拆分态）', async () => {
    await seed('decomposing')
    await submitPlan()
    const approved = await post('/req/plan/approve', { id: 'REQ-abc123' })
    expect(approved.statusCode).toBe(200)
    expect(approved.payload.data.plan.approvedBy.kind).toBe('human')

    const out = await run(decompose, {})
    expect(out.success).toBe(true)
    expect(out.created.map((c: { key: string }) => c.key)).toEqual(['proto', 'ui'])
    expect(out.created[1].depends_on).toEqual([out.created[0].id])
    expect(out.requirement_status).toBe('decomposing')
    const ledger = store.snapshot()
    expect(ledger.tasks).toHaveLength(2)
    expect(ledger.requirements[0].comments.some(c => c.body.includes('[拆分] 按已批准的拆分计划落库 2 个任务'))).toBe(true)
  })

  it('传与批准计划不一致的 tasks → 拒绝（防「批了 A 落库 B」）', async () => {
    await seed('decomposing')
    await submitPlan()
    await post('/req/plan/approve', { id: 'REQ-abc123' })
    await expect(
      run(decompose, { tasks: [{ key: 'other', title: '计划外的活' }] }),
    ).rejects.toThrow(/REQBOARD_PLAN_MISMATCH/)
    expect(store.snapshot().tasks).toHaveLength(0)
  })

  it('人退回（附理由）→ 不能拆；重新提交会作废旧批准', async () => {
    await seed('decomposing')
    await submitPlan()
    await post('/req/plan/approve', { id: 'REQ-abc123' })
    const rejected = await post('/req/plan/reject', { id: 'REQ-abc123', reason: '验收标准太虚，重写' })
    expect(rejected.statusCode).toBe(200)
    expect(rejected.payload.data.plan.rejectedReason).toBe('验收标准太虚，重写')
    await expect(run(decompose, {})).rejects.toThrow(/REQBOARD_PLAN_NOT_APPROVED/)

    // 重写后再提交：旧批准（此处为退回态）不影响，新计划仍需重新批准
    await submitPlan([{ key: 'solo', title: '重写后的单任务', acceptance: 'run x 输出 ok', implementation: '改 x.ts 后跑 run x 验证输出' }])
    const after = store.snapshot().requirements[0]
    expect(after.plan?.approvedAt).toBeUndefined()
    await expect(run(decompose, {})).rejects.toThrow(/REQBOARD_PLAN_NOT_APPROVED/)
    await post('/req/plan/approve', { id: 'REQ-abc123' })
    const out = await run(decompose, {})
    expect(out.created).toHaveLength(1)
  })

  it('退回必须给理由；没有计划的需求不能被裁决', async () => {
    await seed('decomposing')
    const noPlan = await post('/req/plan/approve', { id: 'REQ-abc123' })
    expect(noPlan.statusCode).toBe(404) // 还没有计划，无从裁决
    await submitPlan()
    const empty = await post('/req/plan/reject', { id: 'REQ-abc123', reason: '' })
    expect(empty.statusCode).toBe(400)
    expect(empty.payload.code).toBe('invalid_input')
  })

  it('计划本身的结构校验：key 重复 / 依赖悬空 / 空标题一律拒绝', async () => {
    await seed('decomposing')
    await expect(submitPlan([{ key: 'a', title: 'A' }, { key: 'a', title: 'B' }])).rejects.toThrow(/key 重复/)
    await expect(submitPlan([{ key: 'a', title: 'A', depends_on: ['nope'] }])).rejects.toThrow(/不存在的 key/)
    await expect(submitPlan([{ key: 'a', title: '' }])).rejects.toThrow()
    expect(store.snapshot().requirements[0].plan).toBeUndefined()
  })

  it('越权：不能给别的窗口的需求提交计划', async () => {
    await seed('decomposing')
    await expect(run(planTool, { path: 'p.md', summary: 's', tasks: PLAN_TASKS }, 'session-other')).rejects.toThrow(/REQBOARD_NO_BOUND_REQ/)
  })
})

describe('批准后的执行链（计划 → 任务卡 → 自动验收）', () => {
  it('任务按计划逐项 done 后，需求自动进验收', async () => {
    await seed('decomposing')
    await submitPlan()
    await post('/req/plan/approve', { id: 'REQ-abc123' })
    const out = await run(decompose, {})
    const [proto, ui] = out.created.map((c: { id: string }) => c.id)

    const started = await run(taskMove, { task_id: proto, to: 'in_progress', reason: '开工' })
    // 2026-09-14 五门裁定：任务开工不再自动 decomposing>implementing，需求停等人工确认拆分清单
    expect(started.requirement_status).toBe('decomposing')
    for (const to of ['testing', 'in_review']) await run(taskMove, { task_id: proto, to })
    // done 凭证门（t06）：汇报+痕迹后才能关
    const { recordToolTrace } = await import('../src/adapters/SessionProbeAdapter.js')
    recordToolTrace(trace, W, 'edit', Date.now())
    await run(reportTool, { task_id: proto, summary: '协议层完成', completed: ['protocol.ts 改完'] })
    await run(taskMove, { task_id: proto, to: 'done' })
    expect(store.snapshot().requirements[0].status).toBe('decomposing')

    // 模拟人确认拆分清单（human gate 通过）→ 需求进入实施态，任务事实驱动 R2 进验收
    await store.mutate('human-confirm', (l) => {
      const r = l.requirements.find(x => x.id === 'REQ-abc123')!
      r.status = 'implementing'
      return { requirements: [r] }
    })

    for (const to of ['in_progress', 'testing', 'in_review']) await run(taskMove, { task_id: ui, to })
    const { recordToolTrace: rec2 } = await import('../src/adapters/SessionProbeAdapter.js')
    rec2(trace, W, 'edit', Date.now())
    await run(reportTool, { task_id: ui, summary: 'UI 完成', completed: ['view.ts 改完'] })
    await run(taskMove, { task_id: ui, to: 'done' })
    expect(store.snapshot().requirements[0].status).toBe('accepting')
    // 任务的验收标准来自计划，一路带进任务卡
    expect(store.snapshot().tasks.map(t => t.acceptance)).toEqual(['protocol.ts 单测绿', '截图可见'])
  })
})
