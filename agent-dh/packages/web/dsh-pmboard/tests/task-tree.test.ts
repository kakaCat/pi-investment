/**
 * reqboard_task_tree（REQ-260927144541-0481 FR-3）——只读父子结构视图。
 * serves: FR-3
 *
 * 口径：TC-5 含子卡的父卡返回全部子卡且按链序；TC-6 无子卡 → [] + note；
 * TC-7 跨窗口 → REQBOARD_NOT_BOUND_TO_WINDOW（不返回空当成功）。
 */
import { describe, expect, it } from 'vitest'
import { makeHarness, req, task, type Harness } from './application/harness.js'
import { defineTaskTreeTool } from '../src/tools/index.js'

const W = 'session-w-001'
const run = (t: unknown, args: unknown): Promise<Record<string, any>> =>
  (t as { execute: (a: unknown, e: unknown) => Promise<Record<string, any>> }).execute(args, { agent: { id: W } })
const tool = (h: Harness) => defineTaskTreeTool(h.deps)

/** 父卡 + 4 张串行子卡（链序 dev → integrate → review → test，与 feature 模板一致）。 */
function seedChain(): Harness {
  // 任务落**队列**（REQ-260927202051-f6df：v9 台账已无 tasks 通道）
  const h = makeHarness({ tasks: [
    task({ id: 't-p', requirementId: 'REQ-000001', status: 'in_progress', title: '父卡' }),
    task({
      id: 't-s1', requirementId: 'REQ-000001', parentId: 't-p', stageKind: 'dev' as never, status: 'done',
      dependsOn: [], attempt: 1,
      lastRun: { at: 5, ok: true, stopReason: 'completed', valueNonEmpty: true },
      lastReport: { at: 5, reportIndex: 2, filesChanged: ['src/a.ts'], completed: ['改完 a.ts'] },
    }),
    task({ id: 't-s2', requirementId: 'REQ-000001', parentId: 't-p', stageKind: 'integrate' as never, status: 'todo', dependsOn: ['t-s1'] }),
    task({ id: 't-s3', requirementId: 'REQ-000001', parentId: 't-p', stageKind: 'review' as never, status: 'todo', dependsOn: ['t-s2'] }),
    task({ id: 't-s4', requirementId: 'REQ-000001', parentId: 't-p', stageKind: 'test' as never, status: 'todo', dependsOn: ['t-s3'] }),
  ] })
  h.repo.ledger.requirements = [req({ status: 'implementing' })]
  return h
}

describe('reqboard_task_tree（FR-3）', () => {
  it('TC-5 含 4 张子卡的父卡 → 全部子卡且按链序；节点含 stageKind/status/lastRunOk/摘要', async () => {
    const h = seedChain()
    const out = await run(tool(h), { parent_id: 't-p' })
    expect(out.success).toBe(true)
    expect(out.requirement_id).toBe('REQ-000001')
    expect(out.parents).toHaveLength(1)
    const view = out.parents[0]
    expect(view.parent.id).toBe('t-p')
    expect(view.parent.role).toBe('parent')
    expect(view.subtasks.map((s: any) => s.id)).toEqual(['t-s1', 't-s2', 't-s3', 't-s4'])
    expect(view.subtasks.map((s: any) => s.stageKind)).toEqual(['dev', 'integrate', 'review', 'test'])
    expect(view.subtasks[0].status).toBe('done')
    expect(view.subtasks[0].lastRunOk).toBe(true)
    expect(String(view.subtasks[0].reportSummary)).toContain('改完 a.ts')
    expect(view.subtasks[1].lastRunOk).toBeUndefined()
    expect(String(view.subtasks[0].cardDoc)).toBe('docs/requirements/REQ-000001/tasks/t-s1.md')
    expect(String(view.note)).toContain('4 张')
  })

  it('TC-6 未开工（无子卡）的父卡 → subtasks=[] + note 说明尚未展开', async () => {
    const h = makeHarness()
    h.repo.ledger.requirements = [req({ status: 'implementing' })]
    await h.addTasks('REQ-000001', [task({ id: 't-p', requirementId: 'REQ-000001', status: 'todo' })])
    const out = await run(tool(h), { parent_id: 't-p' })
    expect(out.success).toBe(true)
    expect(out.parents[0].subtasks).toEqual([])
    expect(out.parents[0].note).toBe('该父卡尚未开工展开子卡链')
  })

  it('不传 parent_id → 列出该需求下全部父卡及各自子卡链', async () => {
    const h = seedChain()
    await h.addTasks('REQ-000001', [task({ id: 't-p2', requirementId: 'REQ-000001', status: 'todo', title: '父卡2' })])
    const out = await run(tool(h), {})
    expect(out.parents.map((p: any) => p.parent.id).sort()).toEqual(['t-p', 't-p2'])
  })

  it('TC-7 跨窗口的任务 → REQBOARD_NOT_BOUND_TO_WINDOW（不返回空当成功）', async () => {
    const h = seedChain()
    h.repo.ledger.requirements.push(req({ id: 'REQ-000002', sourceSessionId: 'session-other' }))
    await h.addTasks('REQ-000002', [task({ id: 't-x', requirementId: 'REQ-000002' })])
    const out = await run(tool(h), { parent_id: 't-x' })
    expect(out.success).toBe(false)
    expect(String(out.error)).toContain('REQBOARD_NOT_BOUND_TO_WINDOW')
  })

  it('未绑定需求 → REQBOARD_NO_BOUND_REQ', async () => {
    const h = makeHarness()
    const out = await run(tool(h), {})
    expect(out.success).toBe(false)
    expect(String(out.error)).toContain('REQBOARD_NO_BOUND_REQ')
  })

  it('不存在的任务 → REQBOARD_TASK_NOT_FOUND', async () => {
    const h = seedChain()
    const out = await run(tool(h), { parent_id: 't-nope' })
    expect(out.success).toBe(false)
    expect(String(out.error)).toContain('REQBOARD_TASK_NOT_FOUND')
  })
})
