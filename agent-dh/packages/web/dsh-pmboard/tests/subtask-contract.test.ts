/**
 * 子卡数据契约与不变量测试（REQ-4842fe t3）——对应 design/test-cases.md §2.1/2.6/2.7。
 *
 * 口径：新字段全部可缺省（旧台账读出即旧行为）；悬空 parentId / 角色字段互斥 / 重复展开
 * 三条不变量由纯函数机械校验（INV-1/2/3）。
 */
import { describe, it, expect } from 'vitest'
import {
  taskRoleOf,
  isSubtask,
  subtasksOf,
  checkSubtaskInvariants,
  assertSubtaskInvariants,
  type TaskRecord,
} from '../src/shared/protocol.js'
import { makeHarness, task, req } from './application/harness.js'

const codeOf = (fn: () => void): string | undefined => {
  try { fn(); return undefined } catch (err) { return (err as { code?: string }).code }
}

/** 子卡工厂：挂在给定父卡下。 */
function sub(id: string, parentId: string, stageKind: string, over: Partial<TaskRecord> = {}): TaskRecord {
  return task({ id, requirementId: 'REQ-000001', parentId, stageKind: stageKind as TaskRecord['stageKind'], ...over })
}

describe('角色判定与派生（FR-2）', () => {
  it('无 parentId = legacy/普通卡；有 = 子卡', () => {
    expect(taskRoleOf({})).toBe('legacy')
    expect(taskRoleOf({ parentId: '' })).toBe('legacy')
    expect(taskRoleOf({ parentId: 't-1' })).toBe('subtask')
    expect(isSubtask({ parentId: 't-1' })).toBe(true)
    expect(isSubtask({})).toBe(false)
  })

  it('subtasksOf 由 parentId 反查派生（父卡不存子卡列表）', () => {
    const parent = task({ id: 't-p', requirementId: 'REQ-000001' })
    const tasks = [parent, sub('t-1', 't-p', 'dev'), sub('t-2', 't-p', 'review'), task({ id: 't-x' })]
    expect(subtasksOf(tasks, 't-p').map(t => t.id)).toEqual(['t-1', 't-2'])
  })
})

describe('不变量校验（INV-1/2/3）', () => {
  it('2.7 悬空 parentId → INV-1（且 assert 抛 subtask_invariant，消息含 INV-1）', () => {
    const tasks = [sub('t-1', 't-missing', 'dev')]
    const v = checkSubtaskInvariants(tasks, 'REQ-000001')
    expect(v.map(x => x.inv)).toEqual(['INV-1'])
    expect(v[0]!.message).toContain('t-missing')
    expect(codeOf(() => assertSubtaskInvariants(tasks, 'REQ-000001'))).toBe('subtask_invariant')
    try {
      assertSubtaskInvariants(tasks, 'REQ-000001')
    } catch (err) {
      expect((err as Error).message).toContain('INV-1')
    }
  })

  it('INV-2 角色字段互斥：父卡不得有 stageKind；子卡必须有 stageKind', () => {
    expect(checkSubtaskInvariants([task({ id: 't-p', stageKind: 'dev' as any })], 'REQ-000001').map(v => v.inv)).toEqual(['INV-2'])
    const parent = task({ id: 't-p' })
    const noKind = task({ id: 't-s', parentId: 't-p' })
    expect(checkSubtaskInvariants([parent, noKind], 'REQ-000001').map(v => v.inv)).toEqual(['INV-2'])
  })

  it('2.6 幂等展开：同一父卡下 stageKind 重复 → INV-3（不产生第二套）', () => {
    const parent = task({ id: 't-p' })
    const good = [parent, sub('t-1', 't-p', 'dev'), sub('t-2', 't-p', 'integrate'), sub('t-3', 't-p', 'review'), sub('t-4', 't-p', 'test')]
    expect(checkSubtaskInvariants(good, 'REQ-000001')).toEqual([])
    const duplicated = [...good, sub('t-5', 't-p', 'dev')]
    const v = checkSubtaskInvariants(duplicated, 'REQ-000001')
    expect(v.map(x => x.inv)).toEqual(['INV-3'])
    expect(v[0]!.message).toContain('dev')
  })

  it('跨需求不误报：另一需求下的父卡不参与本需求校验（且同需求内自洽）', () => {
    const tasks = [task({ id: 't-other', requirementId: 'REQ-999999' }), sub('t-1', 't-other', 'dev', { requirementId: 'REQ-999999' })]
    expect(checkSubtaskInvariants(tasks, 'REQ-000001')).toEqual([])
    expect(checkSubtaskInvariants(tasks, 'REQ-999999')).toEqual([])
  })
})

describe('2.1 旧台账兼容（无新字段可读、行为不变）', () => {
  it('无 parentId/stageKind/attempt/revisions 的存量任务：角色为 legacy、校验零违规', () => {
    const legacy = task({ id: 't-legacy' })
    expect(legacy.parentId).toBeUndefined()
    expect(legacy.stageKind).toBeUndefined()
    expect(legacy.attempt).toBeUndefined()
    expect(legacy.revisions).toBeUndefined()
    expect(taskRoleOf(legacy)).toBe('legacy')
    expect(checkSubtaskInvariants([legacy], 'REQ-000001')).toEqual([])
  })

  it('旧台账经仓储读回不丢字段、不报错（纯加字段，不 bump schemaVersion）', async () => {
    const h = makeHarness({ requirements: [req({ id: 'REQ-000001', status: 'implementing' })], tasks: [task({ id: 't-legacy', requirementId: 'REQ-000001' })] })
    const view = await h.repo.read(v => v)
    expect(view.tasks[0]!.id).toBe('t-legacy')
    expect(view.requirements[0]!.autoRun).toBeUndefined()
  })
})
