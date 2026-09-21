/**
 * 懒展开测试（REQ-4842fe t6 / FR-3）——对应 design/test-cases.md §1.3/§2.6。
 *
 * 口径：父卡开工**同事务**落子卡链；顺序与映射表/显式 stages 一致；重复开工幂等；
 * 链内依赖成串，链首继承父卡外部依赖；联调卡可被 skipIntegration 跳过。
 */
import { describe, it, expect } from 'vitest'
import { executeMoveTask } from '../src/application/use-cases/MoveTask.js'
import { makeHarness, task, req } from './application/harness.js'

const exec = { agent: { id: 'session-w-001' } }

function seed(over: { category?: 'feature' | 'bug' | 'refactor'; stages?: string[]; skipIntegration?: boolean; parentDependsOn?: string[] } = {}) {
  const h = makeHarness()
  // autoRun=true 才走自动链（懒展开）；手动/存量流程保持五段状态机（双模共存）。
  h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing', category: over.category ?? 'feature', autoRun: true })]
  h.repo.ledger.tasks = [
    ...(over.parentDependsOn ?? []).map(id => task({ id, requirementId: 'REQ-000001', status: 'done' })),
    task({
      id: 't-p',
      requirementId: 'REQ-000001',
      status: 'todo',
      title: '父卡',
      dependsOn: over.parentDependsOn ?? [],
      ...(over.stages !== undefined ? { stages: over.stages as never } : {}),
      ...(over.skipIntegration !== undefined ? { skipIntegration: over.skipIntegration } : {}),
    }),
  ]
  return h
}

const subsOf = (h: ReturnType<typeof seed>) => h.repo.ledger.tasks.filter(t => t.parentId === 't-p')

describe('懒展开（FR-3）', () => {
  it('feature 父卡开工 → 落 dev→integrate→review→test 四张子卡，顺序与映射表一致', async () => {
    const h = seed()
    await executeMoveTask(h.deps, { task_id: 't-p', to: 'in_progress' }, exec)
    const subs = subsOf(h)
    expect(subs.map(s => s.stageKind)).toEqual(['dev', 'integrate', 'review', 'test'])
    expect(h.repo.ledger.tasks.find(t => t.id === 't-p')!.status).toBe('in_progress')
  })

  it('展开与状态变更落在同一 revision（同事务）', async () => {
    const h = seed()
    const before = h.repo.ledger.revision
    await executeMoveTask(h.deps, { task_id: 't-p', to: 'in_progress' }, exec)
    expect(h.repo.ledger.revision).toBe(before + 1)
    expect(subsOf(h)).toHaveLength(4)
  })

  it('链内依赖成串；链首继承父卡外部依赖', async () => {
    const h = seed({ parentDependsOn: ['t-dep'] })
    await executeMoveTask(h.deps, { task_id: 't-p', to: 'in_progress' }, exec)
    const subs = subsOf(h)
    const byId = new Map(subs.map(s => [s.id, s]))
    expect(subs[0]!.dependsOn).toEqual(['t-dep'])
    for (let i = 1; i < subs.length; i += 1) {
      expect(subs[i]!.dependsOn).toEqual([subs[i - 1]!.id])
      expect(byId.has(subs[i]!.dependsOn[0]!)).toBe(true)
    }
  })

  it('2.6 幂等：重复开工不产生第二套子卡', async () => {
    const h = seed()
    await executeMoveTask(h.deps, { task_id: 't-p', to: 'in_progress' }, exec)
    expect(subsOf(h)).toHaveLength(4)
    // 重复触发（父卡已在 in_progress，再次 move 到 in_progress 应无新增）
    await executeMoveTask(h.deps, { task_id: 't-p', to: 'in_progress' }, exec).catch(() => undefined)
    expect(subsOf(h)).toHaveLength(4)
  })

  it('bug 分类 → repro→fix→review→regress；联调卡不在该模板', async () => {
    const h = seed({ category: 'bug' })
    await executeMoveTask(h.deps, { task_id: 't-p', to: 'in_progress' }, exec)
    expect(subsOf(h).map(s => s.stageKind)).toEqual(['repro', 'fix', 'review', 'regress'])
  })

  it('1.3 显式 stages 覆盖映射表（逃生舱口）', async () => {
    const h = seed({ stages: ['collect', 'analyze', 'review'] })
    await executeMoveTask(h.deps, { task_id: 't-p', to: 'in_progress' }, exec)
    expect(subsOf(h).map(s => s.stageKind)).toEqual(['collect', 'analyze', 'review'])
  })

  it('skipIntegration=true → 不落联调卡（其余卡照旧）', async () => {
    const h = seed({ skipIntegration: true })
    await executeMoveTask(h.deps, { task_id: 't-p', to: 'in_progress' }, exec)
    expect(subsOf(h).map(s => s.stageKind)).toEqual(['dev', 'review', 'test'])
  })

  it('子卡不展开子卡（递归语义被禁止）', async () => {
    const h = seed()
    await executeMoveTask(h.deps, { task_id: 't-p', to: 'in_progress' }, exec)
    const first = subsOf(h)[0]!
    await executeMoveTask(h.deps, { task_id: first.id, to: 'in_progress' }, exec)
    expect(h.repo.ledger.tasks.filter(t => t.parentId === first.id)).toHaveLength(0)
  })

  it('子卡转移收紧：子卡 in_progress → integrating 被拒', async () => {
    const h = seed()
    await executeMoveTask(h.deps, { task_id: 't-p', to: 'in_progress' }, exec)
    const first = subsOf(h)[0]!
    await executeMoveTask(h.deps, { task_id: first.id, to: 'in_progress' }, exec)
    let code: string | undefined
    try { await executeMoveTask(h.deps, { task_id: first.id, to: 'integrating' }, exec) } catch (err) { code = (err as { code?: string }).code }
    expect(code).toBe('invalid_transition')
  })
})
