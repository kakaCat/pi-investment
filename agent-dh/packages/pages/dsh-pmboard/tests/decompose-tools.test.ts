/**
 * 真拆分与任务推进工具单测（reqboard_decompose / reqboard_task_move）。
 *
 * 背景（用户提问「拆分是真拆分吗」）：拆分态此前只是状态名——没有任何代码把需求变成
 * 任务，台账 tasks 恒为 0。本组测试用**真实 Store**（临时文件）锁死端到端行为：
 * 一次调用落库整批任务 DAG → 需求由 rollup 自动进入拆分/实施 → 任务全部完成后
 * 自动进验收；越权/非法/人工闸门逐条拒绝。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { ReqboardStore } from '../src/host/store.js'
import { defineDecomposeTool, defineTaskMoveTool } from '../src/host/agent-tools.js'
import type { RequirementRecord, RequirementStatus } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore

let decompose: { execute: (a: unknown, e: unknown) => Promise<any> }
let taskMove: { execute: (a: unknown, e: unknown) => Promise<any> }

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-decompose-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  // 工具必须在 store 就绪后构造（deps 捕获的是实例，不是 getter）
  decompose = defineDecomposeTool(deps()) as unknown as { execute: (a: unknown, e: unknown) => Promise<any> }
  taskMove = defineTaskMoveTool(deps()) as unknown as { execute: (a: unknown, e: unknown) => Promise<any> }
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

const deps = () => ({ store, now: () => Date.now() }) as never

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

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown, agent = W) => tool.execute(args, { agent: { id: agent } })

const TWO_TASKS = [
  { key: 'a', title: '协议层加时间线', phase: 'implement', side: 'backend', acceptance: '单测绿' },
  { key: 'b', title: '客户端渲染甘特图', phase: 'ui', side: 'frontend', depends_on: ['a'], acceptance: '截图可见' },
]

describe('reqboard_decompose（真拆分）', () => {
  it('一次调用落库整批任务：key 映射成真实 id、依赖成链、需求自动进拆分态', async () => {
    await seed('reviewing')
    const out = await run(decompose, { tasks: TWO_TASKS })
    expect(out.success).toBe(true)
    expect(out.requirement_id).toBe('REQ-abc123')
    expect(out.created).toHaveLength(2)
    expect(out.created[0].id).toMatch(/^t-[0-9a-f]{6}$/)
    expect(out.created[1].depends_on).toEqual([out.created[0].id])
    expect(out.requirement_status).toBe('decomposing')

    const ledger = store.snapshot()
    expect(ledger.tasks).toHaveLength(2)
    const [a, b] = ledger.tasks
    expect(a.statusHistory?.[0]?.status).toBe('todo')
    expect(a.statusHistory?.[0]?.by.kind).toBe('agent')
    expect(b.dependsOn).toEqual([a.id])
    expect(ledger.requirements[0].comments.some(c => c.body.includes('[拆分] 落库 2 个任务'))).toBe(true)
    expect(ledger.requirements[0].statusHistory?.map(e => e.status)).toEqual(['draft', 'decomposing'])
  })

  it('状态不允许（立项态）与未知依赖：拒绝且不写库', async () => {
    await seed('draft')
    await expect(run(decompose, { tasks: TWO_TASKS })).rejects.toThrow(/REQBOARD_BAD_STATUS/)
    expect(store.snapshot().tasks).toHaveLength(0)

    await store.mutate('requirement-moved', (l) => { l.requirements[0].status = 'reviewing'; return { requirements: [l.requirements[0]] } })
    await expect(run(decompose, { tasks: [{ key: 'x', title: '悬空依赖', depends_on: ['nope'] }] })).rejects.toThrow(/REQBOARD_INVALID_INPUT/)
    expect(store.snapshot().tasks).toHaveLength(0)
  })

  it('越权：不能拆别的窗口的需求', async () => {
    await seed('reviewing')
    await expect(run(decompose, { tasks: TWO_TASKS }, 'session-other')).rejects.toThrow(/REQBOARD_NO_BOUND_REQ/)
    await expect(run(decompose, { requirement_id: 'REQ-ffffff', tasks: TWO_TASKS })).rejects.toThrow(/REQBOARD_NOT_BOUND_TO_WINDOW/)
  })
})

describe('reqboard_task_move（任务推进）', () => {
  it('agent 能自己把任务跑完，并驱动需求自动进验收', async () => {
    await seed('reviewing')
    const out = await run(decompose, { tasks: TWO_TASKS })
    const [a, b] = out.created.map((c: { id: string }) => c.id)

    const start = await run(taskMove, { task_id: a, to: 'in_progress', reason: '开工' })
    expect(start.from).toBe('todo')
    expect(start.to).toBe('in_progress')
    expect(start.requirement_status).toBe('implementing') // 任务开工 → 需求自动进实施

    let t = store.snapshot().tasks.find(x => x.id === a)!
    expect(t.executions).toHaveLength(1)
    expect(t.executions[0].outcome).toBe('running')
    expect(t.claimedBy).toBe(W)

    for (const to of ['testing', 'in_review', 'done']) await run(taskMove, { task_id: a, to, reason: '推进' })
    t = store.snapshot().tasks.find(x => x.id === a)!
    expect(t.status).toBe('done')
    expect(t.executions[0].endedAt).toBeDefined()
    expect(t.executions[0].outcome).toBe('succeeded') // 离开 in_progress 即结算执行段
    expect(t.statusHistory?.map(e => e.status)).toEqual(['todo', 'in_progress', 'testing', 'in_review', 'done'])
    // 还有一个任务没完成 → 需求仍在实施
    expect(store.snapshot().requirements[0].status).toBe('implementing')

    for (const to of ['in_progress', 'testing', 'in_review', 'done']) await run(taskMove, { task_id: b, to })
    expect(store.snapshot().requirements[0].status).toBe('accepting')
  })

  it('人工闸门与越权：取消任务、动别人任务都被拒', async () => {
    await seed('reviewing')
    const out = await run(decompose, { tasks: TWO_TASKS })
    const a = out.created[0].id
    await expect(run(taskMove, { task_id: a, to: 'canceled' })).rejects.toThrow(/REQBOARD_HUMAN_GATE/)
    await expect(run(taskMove, { task_id: 't-ffffff', to: 'in_progress' })).rejects.toThrow(/REQBOARD_TASK_NOT_FOUND/)
    await expect(run(taskMove, { task_id: a, to: 'in_progress' }, 'session-other')).rejects.toThrow(/REQBOARD_NOT_BOUND_TO_WINDOW/)
  })
})
