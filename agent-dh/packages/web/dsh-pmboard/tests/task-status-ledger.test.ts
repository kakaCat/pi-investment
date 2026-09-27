/**
 * reqboard_task_status 台账数据源（REQ-260927144541-0481 FR-4）。
 * serves: FR-4
 *
 * 口径：TC-8 跑过链的卡读到真实 run 结果；TC-9 无 lastRun → run/workflow 缺省、不报错、不伪造。
 * 关键：测试**不放任何卡文档**（FakeDocs 为空）——读数不依赖卡文档，死数据源才算真删掉。
 */
import { describe, expect, it } from 'vitest'
import { makeHarness, req, task } from './application/harness.js'
import { defineTaskStatusTool } from '../src/tools/index.js'

const W = 'session-w-001'
const run = (t: unknown, args: unknown): Promise<Record<string, any>> =>
  (t as { execute: (a: unknown, e: unknown) => Promise<Record<string, any>> }).execute(args, { agent: { id: W } })

describe('reqboard_task_status（FR-4：改读台账 lastRun/lastReport）', () => {
  it('TC-8 跑过链的子卡 → 读到真实 run 结果与汇报摘要（不依赖卡文档）', async () => {
    const h = makeHarness({ tasks: [task({
      id: 't-s1', requirementId: 'REQ-000001', status: 'in_review',
      lastRun: { at: 7, ok: false, stopReason: 'error', valueNonEmpty: false, reason: 'engine_unavailable' },
      lastReport: { at: 7, reportIndex: 1, filesChanged: ['src/a.ts', 'src/b.ts'], completed: ['改完 a.ts'] },
    })] })
    h.repo.ledger.requirements = [req({ status: 'implementing' })]
    const out = await run(defineTaskStatusTool(h.deps), { task_id: 't-s1' })
    expect(out.success).toBe(true)
    expect(out.status).toBe('in_review')
    expect(out.progress).toBe(85)
    expect(out.run.ok).toBe(false)
    expect(out.run.stopReason).toBe('error')
    expect(out.run.reason).toBe('engine_unavailable')
    expect(out.report.completedCount).toBe(1)
    expect(out.report.filesChangedCount).toBe(2)
    // workflow 键保留（既有消费者契约），内容换成真实 run 摘要
    expect(out.workflow.stopReason).toBe('error')
  })

  it('TC-9 无 lastRun 的卡 → run/workflow 缺省，不报错、不伪造', async () => {
    const h = makeHarness({ tasks: [task({ id: 't-a', requirementId: 'REQ-000001', status: 'todo' })] })
    h.repo.ledger.requirements = [req({ status: 'implementing' })]
    const out = await run(defineTaskStatusTool(h.deps), { task_id: 't-a' })
    expect(out.success).toBe(true)
    expect(out.run).toBeUndefined()
    expect(out.workflow).toBeUndefined()
    expect(out.progress).toBe(0)
  })

  it('任务不存在 → success=false + 明确 error（不返回空当成功）', async () => {
    const h = makeHarness()
    const out = await run(defineTaskStatusTool(h.deps), { task_id: 't-nope' })
    expect(out.success).toBe(false)
    expect(String(out.error)).toContain('t-nope')
  })
})
