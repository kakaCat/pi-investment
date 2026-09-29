/**
 * reqboard_task_adopt 归属补救（2026-09-28，用户现场需求）。
 * serves: 归属补救
 *
 * 口径：补 parentId + stageKind 后角色由「存量卡」翻成「子卡」（合法边随之收紧为三态）；
 * 所有既有闸门不放松——跨需求 / 父卡是子卡 / 名下有子卡 / 已有归属 / 自指依赖 /
 * 状态不在子卡生命周期 / 挂载后新增 INV-1..4 违规，全部拒绝且**零副作用**（不写盘）。
 */
import { describe, expect, it } from 'vitest'
import { makeHarness, req, task } from './application/harness.js'
import { defineTaskAdoptTool, defineTaskMoveTool } from '../src/tools/index.js'

const W = 'session-w-001'
const run = (t: unknown, args: unknown): Promise<Record<string, any>> =>
  (t as { execute: (a: unknown, e: unknown) => Promise<Record<string, any>> }).execute(args, { agent: { id: W } })
const executor = async (t: unknown, args: unknown): Promise<{ code?: string; msg: string }> => {
  try { await run(t, args); return { msg: '' } } catch (e) { return { code: (e as { code?: string }).code, msg: String((e as Error).message ?? e) } }
}

/** 父卡 t-p（顶层、in_progress）+ 若干平行卡。 */
function base(extra: Record<string, unknown>[] = []) {
  const h = makeHarness({ tasks: [
    task({ id: 't-p', requirementId: 'REQ-000001', status: 'in_progress', title: '父卡' }),
    ...extra.map((o) => task(o as never)),
  ] })
  h.repo.ledger.requirements = [req({ status: 'implementing' })]
  return h
}

describe('reqboard_task_adopt（归属补救）', () => {
  it('缺归属的卡挂到父卡下 → parentId/stageKind 落库 + 角色翻成子卡 + 双侧留痕', async () => {
    const h = base([{ id: 't-x', requirementId: 'REQ-000001', status: 'todo', title: '无归属卡' }])
    const out = await run(defineTaskAdoptTool(h.deps), { task_id: 't-x', parent_id: 't-p', stage_kind: 'dev', reason: '拆分时漏写归属' })
    expect(out.success).toBe(true)
    expect(out.role).toBe('subtask')
    expect(out.previous_parent_id).toBe('')
    expect(out.stage_kind).toBe('dev')

    const x = (await h.tasksOf('REQ-000001')).find((t) => t.id === 't-x')!
    expect(x.parentId).toBe('t-p')
    expect(x.stageKind).toBe('dev')
    expect(x.status).toBe('todo') // 状态不动
    expect((x.comments ?? []).some((c) => String(c.body).includes('[归属]'))).toBe(true)
    expect(h.repo.ledger.requirements[0]!.comments.some((c: any) => String(c.body).includes('[归属补救]'))).toBe(true)

    // 角色翻转的可观测判据：子卡合法边里没有 in_review（存量五段才有）
    const err = await executor(defineTaskMoveTool(h.deps), { task_id: 't-x', to: 'in_review' })
    expect(err.msg).toContain('子卡')
  })

  it('已有归属且未 force → 拒（本入口只补缺失）', async () => {
    const h = base([
      { id: 't-s', requirementId: 'REQ-000001', status: 'todo', parentId: 't-p', stageKind: 'dev', title: '既有子卡' },
      { id: 't-p2', requirementId: 'REQ-000001', status: 'todo', title: '另一父卡' },
    ])
    const err = await executor(defineTaskAdoptTool(h.deps), { task_id: 't-s', parent_id: 't-p2', stage_kind: 'dev' })
    expect(err.code).toBe('REQBOARD_ADOPT_ALREADY')
    expect(err.msg).toContain('force=true')
    expect((await h.tasksOf('REQ-000001')).find((t) => t.id === 't-s')!.parentId).toBe('t-p')
  })

  it('已有归属 + force=true → 改挂成功且记下原父卡', async () => {
    const h = base([
      { id: 't-s', requirementId: 'REQ-000001', status: 'todo', parentId: 't-p', stageKind: 'dev', title: '既有子卡' },
      { id: 't-p2', requirementId: 'REQ-000001', status: 'todo', title: '另一父卡' },
    ])
    const out = await run(defineTaskAdoptTool(h.deps), { task_id: 't-s', parent_id: 't-p2', stage_kind: 'dev', force: true, reason: '挂错父卡' })
    expect(out.previous_parent_id).toBe('t-p')
    expect((await h.tasksOf('REQ-000001')).find((t) => t.id === 't-s')!.parentId).toBe('t-p2')
  })

  it('父卡本身是子卡 → 拒（本仓只有父子两层）', async () => {
    const h = base([
      { id: 't-s', requirementId: 'REQ-000001', status: 'todo', parentId: 't-p', stageKind: 'dev', title: '子卡' },
      { id: 't-x', requirementId: 'REQ-000001', status: 'todo', title: '无归属卡' },
    ])
    const err = await executor(defineTaskAdoptTool(h.deps), { task_id: 't-x', parent_id: 't-s', stage_kind: 'dev' })
    expect(err.code).toBe('REQBOARD_ADOPT_PARENT_IS_SUBTASK')
  })

  it('该卡名下有子卡 → 拒（否则子卡链悬空）', async () => {
    const h = base([
      { id: 't-x', requirementId: 'REQ-000001', status: 'todo', title: '有子卡的顶层卡' },
      { id: 't-c', requirementId: 'REQ-000001', status: 'todo', parentId: 't-x', stageKind: 'dev', title: '子卡' },
    ])
    const err = await executor(defineTaskAdoptTool(h.deps), { task_id: 't-x', parent_id: 't-p', stage_kind: 'dev' })
    expect(err.code).toBe('REQBOARD_ADOPT_HAS_CHILDREN')
  })

  it('自指依赖（该卡 dependsOn 含目标父卡）→ 拒', async () => {
    const h = base([{ id: 't-x', requirementId: 'REQ-000001', status: 'todo', title: '无归属卡', dependsOn: ['t-p'] }])
    const err = await executor(defineTaskAdoptTool(h.deps), { task_id: 't-x', parent_id: 't-p', stage_kind: 'dev' })
    expect(err.code).toBe('REQBOARD_ADOPT_DEPENDENCY')
  })

  it('状态不在子卡生命周期（in_review）→ 拒', async () => {
    const h = base([{ id: 't-x', requirementId: 'REQ-000001', status: 'in_review', title: '待复核卡' }])
    const err = await executor(defineTaskAdoptTool(h.deps), { task_id: 't-x', parent_id: 't-p', stage_kind: 'dev' })
    expect(err.code).toBe('REQBOARD_ADOPT_STATUS')
    expect(err.msg).toContain('in_progress')
  })

  it('stageKind 缺省且卡上没有 → 拒（INV-2）', async () => {
    const h = base([{ id: 't-x', requirementId: 'REQ-000001', status: 'todo', title: '无归属卡' }])
    const err = await executor(defineTaskAdoptTool(h.deps), { task_id: 't-x', parent_id: 't-p' })
    expect(err.code).toBe('REQBOARD_INVALID_INPUT')
    expect(err.msg).toContain('stage_kind')
  })

  it('同父卡下 stageKind 重复 → 拒（INV-3，挂载后新增违规）', async () => {
    const h = base([
      { id: 't-s1', requirementId: 'REQ-000001', status: 'todo', parentId: 't-p', stageKind: 'dev', title: '既有 dev 子卡' },
      { id: 't-x', requirementId: 'REQ-000001', status: 'todo', title: '无归属卡' },
    ])
    const err = await executor(defineTaskAdoptTool(h.deps), { task_id: 't-x', parent_id: 't-p', stage_kind: 'dev' })
    expect(err.code).toBe('REQBOARD_ADOPT_INVARIANT')
    // 零副作用：没有落库
    expect((await h.tasksOf('REQ-000001')).find((t) => t.id === 't-x')!.parentId).toBeUndefined()
  })

  it('跨需求挂载 → 拒（队列文件不能分裂）', async () => {
    const h = makeHarness({ tasks: [
      task({ id: 't-p', requirementId: 'REQ-000001', status: 'in_progress', title: '父卡' }),
      task({ id: 't-x', requirementId: 'REQ-000001', status: 'todo', title: '本需求卡' }),
      task({ id: 't-other', requirementId: 'REQ-000002', status: 'todo', title: '他需求卡' }),
    ] })
    h.repo.ledger.requirements = [req({ status: 'implementing' }), req({ id: 'REQ-000002', status: 'implementing' })]
    const err = await executor(defineTaskAdoptTool(h.deps), { task_id: 't-x', parent_id: 't-other', stage_kind: 'dev' })
    expect(err.code).toBe('REQBOARD_INVALID_INPUT')
  })
})
