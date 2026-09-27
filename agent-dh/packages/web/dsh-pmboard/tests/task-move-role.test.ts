/**
 * reqboard_task_move 角色感知报错 + acceptance 修订接线（REQ-260927144541-0481 FR-5）。
 * serves: FR-5
 *
 * 口径：TC-10 用 legacy 边推父卡 → 报错含当前角色与合法边；TC-11 只传 acceptance →
 * 台账 task.acceptance 更新 + 卡文档「得到什么结果」同步，且不改状态（不接线这条必红）。
 */
import { describe, expect, it } from 'vitest'
import { makeHarness, req, task } from './application/harness.js'
import { defineTaskMoveTool } from '../src/tools/index.js'

const W = 'session-w-001'
const run = (t: unknown, args: unknown): Promise<Record<string, any>> =>
  (t as { execute: (a: unknown, e: unknown) => Promise<Record<string, any>> }).execute(args, { agent: { id: W } })

/** 父卡（名下有一张子卡 → role=parent）+ 一张子卡。 */
function seedParent() {
  // 任务落**队列**（REQ-260927202051-f6df：v9 台账已无 tasks 通道）
  const h = makeHarness({ tasks: [
    task({ id: 't-p', requirementId: 'REQ-000001', status: 'in_progress', title: '父卡' }),
    task({ id: 't-s', requirementId: 'REQ-000001', parentId: 't-p', stageKind: 'dev' as never, status: 'todo' }),
  ] })
  h.repo.ledger.requirements = [req({ status: 'implementing' })]
  return h
}

describe('reqboard_task_move（FR-5）', () => {
  it('TC-10 用 legacy 边推父卡（in_progress→in_review）→ 报错含「父卡」与合法边', async () => {
    const h = seedParent()
    const t = defineTaskMoveTool(h.deps)
    const err = await run(t, { task_id: 't-p', to: 'in_review' }).catch((e: Error) => e)
    const msg = String((err as Error).message ?? err)
    expect(msg).toContain('父卡')
    expect(msg).toContain('合法边')
    expect(msg).toContain('in_progress→in_review')
    // 零副作用：状态未变（任务从**队列**读，v9 台账已无 tasks）
    expect((await h.tasksOf('REQ-000001')).find((x) => x.id === 't-p')!.status).toBe('in_progress')
  })

  it('子卡的角色与合法边也被说清（子卡不进联调/测试/复核）', async () => {
    const h = seedParent()
    const err = await run(defineTaskMoveTool(h.deps), { task_id: 't-s', to: 'testing' }).catch((e: Error) => e)
    const msg = String((err as Error).message ?? err)
    expect(msg).toContain('子卡')
    expect(msg).toContain('合法边')
  })

  it('TC-11 只传 acceptance → 台账更新 + 卡文档同步 + 状态不变', async () => {
    const h = makeHarness({ tasks: [task({ id: 't-a', requirementId: 'REQ-000001', status: 'todo', acceptance: '功能正常' })] })
    h.repo.ledger.requirements = [req({ status: 'implementing' })]
    const card = 'docs/requirements/REQ-000001/tasks/t-a.md'
    h.docs.put(card, ['# t-a', '', '## 在做什么', 'x', '', '## 得到什么结果', '', '功能正常', '', '## 下一步', 'y', ''].join('\n'))

    const out = await run(defineTaskMoveTool(h.deps), {
      task_id: 't-a',
      acceptance: '命令：node_modules/.bin/vitest run tests/a.test.ts → 看到 1 passed',
    })
    expect(out.success).toBe(true)
    const queueTasks = await h.tasksOf('REQ-000001')
    expect(queueTasks[0]!.acceptance).toContain('vitest run')
    expect(queueTasks[0]!.status).toBe('todo')
    const doc = await h.docs.read(card)
    expect(doc).toContain('vitest run')
    expect(doc).not.toContain('功能正常')
  })

  it('既不传 to 也不传 acceptance → 明确拒绝（不静默当成功）', async () => {
    const h = seedParent()
    const out = await run(defineTaskMoveTool(h.deps), { task_id: 't-p' })
    expect(out.success).toBe(false)
    expect(String(out.error)).toContain('acceptance')
  })

  it('acceptance 是空话 → REQBOARD_INVALID_INPUT（沿用计划期门槛）', async () => {
    const h = makeHarness({ tasks: [task({ id: 't-a', requirementId: 'REQ-000001', status: 'todo' })] })
    h.repo.ledger.requirements = [req({ status: 'implementing' })]
    const err = await run(defineTaskMoveTool(h.deps), { task_id: 't-a', acceptance: '功能正常' }).catch((e: Error) => e)
    expect(String((err as Error).message ?? err)).toContain('REQBOARD_INVALID_INPUT')
  })
})
