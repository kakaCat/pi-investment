/**
 * AdvanceChain 事件链测试（REQ-4842fe t7）——对应 design/test-cases.md §4。
 *
 * 口径：全自动跑到 accepting；重复触发 noop 且 revision 不变；单飞锁挡并发；
 * 连续 noop 达阈值熔断；崩溃后恢复扫描续跑；autoRun=false 无新事件、置回 true 续跑。
 */
import { describe, it, expect } from 'vitest'
import { advanceRequirement, scanAndResume } from '../src/application/use-cases/AdvanceChain.js'
import { LIMITS } from '../src/domain/limits.js'
import type { WorkflowRunner, WorkflowRunOutcome } from '../src/application/ports.js'
import { makeHarness, task, req } from './application/harness.js'

const FILE = 'src/domain/x.ts'

class FakeRunner implements WorkflowRunner {
  calls = 0
  constructor(private readonly failOn = -1) {}
  async start(_input: unknown): Promise<WorkflowRunOutcome> {
    this.calls += 1
    if (this.failOn === this.calls) return { ok: false, reason: 'error: child failed' }
    return { ok: true, value: { ok: true, output: JSON.stringify({ filesChanged: [FILE], completed: ['子卡完成'], evidence: ['vitest 绿'] }) } }
  }
}

function seed(opts: { autoRun?: boolean; runner?: WorkflowRunner; parentStatus?: 'todo' | 'in_progress'; withSubtaskDone?: boolean; dependsOnCanceled?: boolean } = {}) {
  const h = makeHarness()
  h.docs.put(FILE, 'x')
  h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing', category: 'feature', autoRun: opts.autoRun ?? true })]
  const tasks = [
    task({ id: 't-p', requirementId: 'REQ-000001', status: opts.parentStatus ?? 'todo', title: '父卡', dependsOn: opts.dependsOnCanceled === true ? ['t-dead'] : [] }),
  ]
  if (opts.dependsOnCanceled === true) tasks.push(task({ id: 't-dead', requirementId: 'REQ-000001', status: 'canceled' }))
  if (opts.parentStatus === 'in_progress') {
    tasks[0]!.claimedAt = h.clock.t
    if (opts.withSubtaskDone === true) {
      tasks.push(task({ id: 't-s1', requirementId: 'REQ-000001', status: 'done', parentId: 't-p', stageKind: 'dev' as never, lastReport: { at: h.clock.t, reportIndex: 1, filesChanged: [FILE], completed: ['done'] } }))
      tasks.push(task({ id: 't-s2', requirementId: 'REQ-000001', status: 'todo', parentId: 't-p', stageKind: 'review' as never }))
    }
  }
  h.repo.ledger.tasks = tasks
  h.deps.workflow = opts.runner ?? new FakeRunner()
  return h
}

describe('事件链自动驱动（4.1 主用例）', () => {
  it('批准后的需求：自动开父卡 → 跑完子卡链 → 收尾 → rollup 进 accepting', async () => {
    const h = seed()
    const out = await advanceRequirement(h.deps, 'REQ-000001')
    expect(out.stopped).toBe('rollup')
    const events = out.steps.map(s => s.event)
    expect(events[0]).toBe('OPEN_PARENT')
    expect(events.filter(e => e === 'RUN_SUBTASK')).toHaveLength(4)
    expect(events).toContain('FINALIZE_PARENT')
    expect(events[events.length - 1]).toBe('ROLLUP')
    const reqAfter = h.repo.ledger.requirements.find(r => r.id === 'REQ-000001')!
    expect(reqAfter.status).toBe('accepting')
    expect(h.repo.ledger.tasks.find(t => t.id === 't-p')!.status).toBe('done')
    expect(h.repo.ledger.tasks.filter(t => t.parentId === 't-p').every(t => t.status === 'done')).toBe(true)
  })

  it('4.3 幂等重放：链已完成（accepting）后再触发 → noop 且 revision 不变', async () => {
    const h = seed()
    await advanceRequirement(h.deps, 'REQ-000001')
    const rev = h.repo.ledger.revision
    const again = await advanceRequirement(h.deps, 'REQ-000001')
    expect(again.stopped).toBe('terminal')
    expect(again.steps).toEqual([])
    expect(h.repo.ledger.revision).toBe(rev)
  })

  it('4.4 单飞锁：台账 lockAt 新鲜时被挡下（不重复执行）', async () => {
    const h = seed()
    const r = h.repo.ledger.requirements[0]!
    r.advance = { lockAt: h.clock.t }
    const out = await advanceRequirement(h.deps, 'REQ-000001')
    expect(out.stopped).toBe('locked')
    expect(out.steps).toEqual([])
    expect(h.repo.ledger.tasks.find(t => t.id === 't-p')!.status).toBe('todo')
  })

  it('4.5 停滞熔断：连续 noop 达阈值 → autoRun=false + pausedReason=stagnation', async () => {
    const h = seed({ dependsOnCanceled: true })
    let last: Awaited<ReturnType<typeof advanceRequirement>> | undefined
    for (let i = 0; i < LIMITS.advanceNoopBreaker; i += 1) {
      last = await advanceRequirement(h.deps, 'REQ-000001')
      if (last.stopped === 'paused') break
    }
    expect(last?.stopped).toBe('paused')
    const r = h.repo.ledger.requirements[0]!
    expect(r.autoRun).toBe(false)
    expect(r.advance?.pausedReason).toBe('stagnation')
  })

  it('4.7 autoRun=false 无新事件；置回 true 并触发一次即续跑', async () => {
    const h = seed({ autoRun: false })
    expect((await advanceRequirement(h.deps, 'REQ-000001')).stopped).toBe('not_autorun')
    expect(h.repo.ledger.tasks.find(t => t.id === 't-p')!.status).toBe('todo')
    h.repo.ledger.requirements[0]!.autoRun = true
    const out = await advanceRequirement(h.deps, 'REQ-000001')
    expect(out.stopped).toBe('rollup')
  })

  it('4.6 崩溃恢复：中途状态（父卡 in_progress + 一张子卡 done）→ 扫描续跑至完成', async () => {
    const h = seed({ parentStatus: 'in_progress', withSubtaskDone: true })
    const outcomes = await scanAndResume(h.deps)
    expect(outcomes).toHaveLength(1)
    expect(h.repo.ledger.requirements[0]!.status).toBe('accepting')
    expect(h.repo.ledger.tasks.find(t => t.id === 't-s2')!.status).toBe('done')
  })

  it('5.2 失败即暂停：子卡 run 失败 → autoRun=false，不执行后续卡', async () => {
    const h = seed({ runner: new FakeRunner(2) })
    const out = await advanceRequirement(h.deps, 'REQ-000001')
    expect(out.stopped).toBe('paused')
    expect(h.repo.ledger.requirements[0]!.autoRun).toBe(false)
    expect(h.repo.ledger.requirements[0]!.advance?.pausedReason).toBe('fail')
    expect(out.steps.some(s => s.outcome === 'failed')).toBe(true)
    const subs = h.repo.ledger.tasks.filter(t => t.parentId === 't-p')
    expect(subs.filter(s => s.status === 'done').length).toBeLessThan(4)
  })
})
