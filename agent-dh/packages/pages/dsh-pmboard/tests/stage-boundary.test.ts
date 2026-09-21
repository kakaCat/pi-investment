/**
 * W7 阶段产物边界单测（REQ-2e9473 t17）：计划可不含任务表（设计一套文档）；
 * decompose 承担任务卡创作（薄卡拒落）；未批准计划不得落库（design 阶段落库被拒）。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { definePlanSubmitTool, defineDecomposeTool, stubDocFile } from './helpers/tool-deps.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore
let planTool: { execute: (a: unknown, e: unknown) => Promise<any> }
let decompose: { execute: (a: unknown, e: unknown) => Promise<any> }

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-boundary-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  const deps = { store, now: () => Date.now() } as never
  planTool = definePlanSubmitTool(deps) as never
  decompose = defineDecomposeTool(deps) as never
  // REQ-2d1c74 FR-5：plan_submit 起要求提交路径真实落盘
  for (const p of ['p.md', 'docs/requirements/REQ-w7test/decomposition.md']) stubDocFile(p)
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seed(status = 'decomposing'): Promise<void> {
  const r = {
    id: 'REQ-w7test', title: '阶段边界', description: '', status, category: 'feature', blocked: false,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => { l.requirements.push(r); return { requirements: [r] } })
}
const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown) =>
  tool.execute(args, { agent: { id: W } })

const CREATIVE = [
  { key: 'a', title: '建协议', acceptance: 'protocol.ts 单测绿', implementation: 'protocol.ts 加字段并单测' },
  { key: 'b', title: '接前端', depends_on: ['a'], acceptance: '截图可见', implementation: 'view.ts 加渲染' },
]

describe('W7 阶段产物边界（t17）', () => {
  it('不含任务表的计划可提交（兜底逃生舱：落库时创作任务卡）', async () => {
    await seed()
    const out = await run(planTool, { path: 'docs/requirements/REQ-w7test/decomposition.md', summary: '设计：架构+四视角+风险' })
    expect(out.plan_status).toBe('pending_approval')
    expect(out.task_count).toBe(0)
    expect(out.note).toMatch(/落库时由 reqboard_decompose 传 tasks 创作/)
    expect(store.snapshot().requirements[0].plan!.tasks).toHaveLength(0)
  })

  it('传了任务表仍走严格校验（薄卡被拒）', async () => {
    await seed()
    await expect(run(planTool, {
      path: 'p.md', summary: 's',
      tasks: [{ key: 'a', title: 'x', acceptance: '单测绿' }], // 缺 implementation
    })).rejects.toThrow(/缺实施方案/)
  })

  it('空任务表计划 + 未传 tasks → decompose 拒绝（REQBOARD_TASKS_REQUIRED）', async () => {
    await seed()
    await run(planTool, { path: 'p.md', summary: '设计' })
    await store.mutate('approve', (l) => {
      const r = l.requirements[0]
      r.plan!.approvedAt = 1000
      r.plan!.approvedBy = { kind: 'human' }
      return { requirements: [r] }
    })
    await expect(run(decompose, {})).rejects.toThrow(/REQBOARD_TASKS_REQUIRED/)
    expect(store.snapshot().tasks).toHaveLength(0)
  })

  it('空任务表计划 + 创作型 tasks → 落库成功（含实施卡，需求进拆分态）', async () => {
    await seed()
    await run(planTool, { path: 'p.md', summary: '设计' })
    await store.mutate('approve', (l) => {
      const r = l.requirements[0]
      r.plan!.approvedAt = 1000
      r.plan!.approvedBy = { kind: 'human' }
      return { requirements: [r] }
    })
    const out = await run(decompose, { tasks: CREATIVE })
    expect(out.created).toHaveLength(2)
    expect(out.requirement_status).toBe('decomposing')
    const tasks = store.snapshot().tasks
    expect(tasks.map(t => t.implementation)).toEqual(['protocol.ts 加字段并单测', 'view.ts 加渲染'])
    expect(tasks[1].dependsOn).toEqual([tasks[0].id])
  })

  it('创作型薄卡（缺 implementation）→ 拒绝落库', async () => {
    await seed()
    await run(planTool, { path: 'p.md', summary: '设计' })
    await store.mutate('approve', (l) => {
      const r = l.requirements[0]
      r.plan!.approvedAt = 1000
      r.plan!.approvedBy = { kind: 'human' }
      return { requirements: [r] }
    })
    await expect(run(decompose, { tasks: [{ key: 'a', title: 'x', acceptance: '单测绿' }] })).rejects.toThrow(/缺实施方案/)
    expect(store.snapshot().tasks).toHaveLength(0)
  })

  it('计划未批准 → 落库被拒（故障注入）', async () => {
    await seed()
    await run(planTool, { path: 'p.md', summary: '设计' })
    await expect(run(decompose, { tasks: CREATIVE })).rejects.toThrow(/REQBOARD_PLAN_NOT_APPROVED/)
    expect(store.snapshot().tasks).toHaveLength(0)
  })
})
