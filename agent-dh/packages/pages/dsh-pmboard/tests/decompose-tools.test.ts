/**
 * 真拆分与任务推进的**边界**测试（正常路径见 plan-mode.test.ts）。
 *
 * 计划模式下 decompose 只落库"已批准的计划"，所以本文件的重点是闸门与越权边界：
 *   - 立项态不能提交计划（方案还没谈）；
 *   - decompose 只能落库本窗口需求；
 *   - tasks 与批准计划不一致 → 拒绝；
 *   - task_move：跨窗口越权、任务不存在、取消任务（人工闸门）一律拒绝；
 *   - 开工自动开执行段、离开 in_progress 自动结算。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { ReqboardStore } from '../src/host/store.js'
import { definePlanSubmitTool, defineDecomposeTool, defineTaskMoveTool } from '../src/host/agent-tools.js'
import type { RequirementRecord, RequirementStatus } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore
let planTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let decompose: { execute: (a: unknown, e: unknown) => Promise<any> }
let taskMove: { execute: (a: unknown, e: unknown) => Promise<any> }

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-decompose-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  const deps = { store, now: () => Date.now() } as never
  planTool = definePlanSubmitTool(deps) as never
  decompose = defineDecomposeTool(deps) as never
  taskMove = defineTaskMoveTool(deps) as never
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seed(status: RequirementStatus = 'reviewing', sourceSessionId: string | undefined = W): Promise<RequirementRecord> {
  const r = {
    id: 'REQ-abc123', title: '看板需求', description: '', status, blocked: false,
    ...(sourceSessionId !== undefined ? { sourceSessionId } : {}),
    comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [{ status: 'draft', at: 1, by: { kind: 'human' } }],
  } as RequirementRecord
  await store.mutate('requirement-created', (l) => { l.requirements.push(r); return { requirements: [r] } })
  return r
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown, agent = W) =>
  tool.execute(args, { agent: { id: agent } })

const TWO_TASKS = [
  { key: 'a', title: '协议层加时间线', phase: 'implement', side: 'backend', acceptance: '单测绿' },
  { key: 'b', title: '客户端渲染甘特图', phase: 'ui', side: 'frontend', depends_on: ['a'], acceptance: '截图可见' },
]

/** 提交计划并**直接以人身份批准**（本文件不测裁决路径，那在 plan-mode.test.ts）。 */
async function planAndApprove(tasks: unknown = TWO_TASKS): Promise<void> {
  const out = await run(planTool, { path: 'docs/requirements/REQ-abc123/plan.md', summary: '摘要', tasks })
  expect(out.plan_status).toBe('pending_approval')
  await store.mutate('requirement-updated', (l) => {
    const r = l.requirements[0]
    if (r.plan !== undefined) { r.plan.approvedAt = 1000; r.plan.approvedBy = { kind: 'human' } }
    return { requirements: [r] }
  })
}

describe('reqboard_decompose 边界', () => {
  it('立项态不能提交计划（方案还没谈），decompose 也被拒', async () => {
    await seed('draft')
    await expect(run(planTool, { path: 'p.md', summary: 's', tasks: TWO_TASKS })).rejects.toThrow(/REQBOARD_BAD_STATUS/)
    await expect(run(decompose, {})).rejects.toThrow(/REQBOARD_BAD_STATUS/) // 先是状态闸，再是计划闸
    expect(store.snapshot().tasks).toHaveLength(0)
  })

  it('越权：不能拆别的窗口的需求', async () => {
    await seed('reviewing')
    await planAndApprove()
    await expect(run(decompose, {}, 'session-other')).rejects.toThrow(/REQBOARD_NO_BOUND_REQ/)
    await expect(run(decompose, { requirement_id: 'REQ-ffffff' })).rejects.toThrow(/REQBOARD_NOT_BOUND_TO_WINDOW/)
    expect(store.snapshot().tasks).toHaveLength(0)
  })

  it('传与批准计划不一致的 tasks → 拒绝且不写库', async () => {
    await seed('reviewing')
    await planAndApprove()
    await expect(run(decompose, { tasks: [{ key: 'x', title: '计划外' }] })).rejects.toThrow(/REQBOARD_PLAN_MISMATCH/)
    expect(store.snapshot().tasks).toHaveLength(0)
  })

  it('按计划落库：key 映射成真实 id、依赖成链、任务验收标准来自计划', async () => {
    await seed('reviewing')
    await planAndApprove()
    const out = await run(decompose, {})
    expect(out.created).toHaveLength(2)
    expect(out.created[0].id).toMatch(/^t-[0-9a-f]{6}$/)
    expect(out.created[1].depends_on).toEqual([out.created[0].id])
    expect(out.requirement_status).toBe('decomposing')
    const ledger = store.snapshot()
    expect(ledger.tasks.map(t => t.acceptance)).toEqual(['单测绿', '截图可见'])
    expect(ledger.tasks[0].statusHistory?.[0]?.by.kind).toBe('agent')
    expect(ledger.requirements[0].statusHistory?.map(e => e.status)).toEqual(['draft', 'decomposing'])
  })
})

describe('reqboard_task_move 边界', () => {
  it('越权/不存在/人工闸门一律拒绝', async () => {
    await seed('reviewing')
    await planAndApprove()
    const out = await run(decompose, {})
    const a = out.created[0].id
    await expect(run(taskMove, { task_id: a, to: 'canceled' })).rejects.toThrow(/REQBOARD_HUMAN_GATE/)
    await expect(run(taskMove, { task_id: 't-ffffff', to: 'in_progress' })).rejects.toThrow(/REQBOARD_TASK_NOT_FOUND/)
    await expect(run(taskMove, { task_id: a, to: 'in_progress' }, 'session-other')).rejects.toThrow(/REQBOARD_NOT_BOUND_TO_WINDOW/)
    await expect(run(taskMove, { task_id: a, to: 'done' })).rejects.toThrow(/invalid_transition/)
  })

  it('开工自动开执行段，离开 in_progress 自动结算；全部完成后需求进验收', async () => {
    await seed('reviewing')
    await planAndApprove()
    const out = await run(decompose, {})
    const [a, b] = out.created.map((c: { id: string }) => c.id)

    const start = await run(taskMove, { task_id: a, to: 'in_progress', reason: '开工' })
    expect(start.requirement_status).toBe('implementing')
    let t = store.snapshot().tasks.find(x => x.id === a)!
    expect(t.executions).toHaveLength(1)
    expect(t.executions[0].outcome).toBe('running')
    expect(t.claimedBy).toBe(W)

    for (const to of ['testing', 'in_review', 'done']) await run(taskMove, { task_id: a, to })
    t = store.snapshot().tasks.find(x => x.id === a)!
    expect(t.executions[0].endedAt).toBeDefined()
    expect(t.executions[0].outcome).toBe('succeeded')
    expect(t.statusHistory?.map(e => e.status)).toEqual(['todo', 'in_progress', 'testing', 'in_review', 'done'])
    expect(store.snapshot().requirements[0].status).toBe('implementing')

    for (const to of ['in_progress', 'testing', 'in_review', 'done']) await run(taskMove, { task_id: b, to })
    expect(store.snapshot().requirements[0].status).toBe('accepting')
  })
})
