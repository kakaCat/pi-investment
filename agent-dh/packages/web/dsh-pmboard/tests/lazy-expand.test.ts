/**
 * 懒展开测试（REQ-4842fe t6 / FR-3）——对应 design/test-cases.md §1.3/§2.6。
 *
 * 口径：父卡开工**同事务**落子卡链；顺序与映射表/显式 stages 一致；重复开工幂等；
 * 链内依赖成串，链首继承父卡外部依赖；联调卡可被 skipIntegration 跳过。
 */
import { describe, it, expect } from 'vitest'
import { executeMoveTask } from '../src/application/use-cases/MoveTask.js'
import { makeHarness, task, req } from './application/harness.js'
import type { TaskRecord } from '../src/shared/protocol.js'

const exec = { agent: { id: 'session-w-001' } }

function seed(over: { category?: 'feature' | 'bug' | 'refactor'; stages?: string[]; skipIntegration?: boolean; parentDependsOn?: string[] } = {}) {
  const h = makeHarness()
  // autoRun=true 才走自动链（懒展开）；手动/存量流程保持五段状态机（双模共存）。
  h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing', category: over.category ?? 'feature', autoRun: true })]
  // 任务落**队列**（v9）：`seedTasks` 是同步播种口（须在该需求首次被读取之前调用），
  // 因此本 helper 与 `subsOf` 的同步性得以保留，调用点无需 async 化。
  h.seedTasks('REQ-000001', [
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
  ])
  return h
}

/** 队列任务（同步读自内存队列仓储的原始文件——测试专用同步口，避免把整个文件 async 化）。 */
const tasksRaw = (h: ReturnType<typeof seed>): readonly TaskRecord[] => {
  const raw = h.queueRepo.rawOf('REQ-000001')
  return raw === undefined ? [] : (JSON.parse(raw) as { tasks: TaskRecord[] }).tasks
}

const subsOf = (h: ReturnType<typeof seed>) => tasksRaw(h).filter(t => t.parentId === 't-p')

describe('懒展开（FR-3）', () => {
  it('feature 父卡开工 → 落 dev→integrate→review→test 四张子卡，顺序与映射表一致', async () => {
    const h = seed()
    await executeMoveTask(h.deps, { task_id: 't-p', to: 'in_progress' }, exec)
    const subs = subsOf(h)
    expect(subs.map(s => s.stageKind)).toEqual(['dev', 'integrate', 'review', 'test'])
    expect(tasksRaw(h).find(t => t.id === 't-p')!.status).toBe('in_progress')
  })

  it('展开与状态变更落在队列同一批写（v9：跨存储，非同一 revision）', async () => {
    const h = seed()
    const revBefore = h.queueRevisionOf('REQ-000001')
    await executeMoveTask(h.deps, { task_id: 't-p', to: 'in_progress' }, exec)
    // v9 语义变更（REQ-260927202051-f6df）：任务进队列、需求进台账，**两个存储不可能共用一个 revision**，
    // 故原断言"台账 revision === before+1"必然失败、且已不再是本用例要保证的东西。
    // 真正要保证的是：父卡状态与 4 张子卡在**同一次队列写**里一起可见（不是两次半截写）。
    expect(h.queueRevisionOf('REQ-000001')).toBe(revBefore + 1)
    const all = tasksRaw(h)
    expect(all.find(t => t.id === 't-p')?.status).toBe('in_progress')
    expect(all.filter(t => t.parentId === 't-p')).toHaveLength(4)
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
    expect(tasksRaw(h).filter(t => t.parentId === first.id)).toHaveLength(0)
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
