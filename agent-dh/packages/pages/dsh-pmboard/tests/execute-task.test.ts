/**
 * ExecuteTask 用例测试（REQ-4842fe t5）——对应 design/test-cases.md §3.3/3.4/3.5/3.6。
 *
 * 口径：子卡凭证三项任一不过 → 子卡不 done；存在未 done 子卡 → 父卡不得 done；
 * 改了页面插件源码但 client 产物未更新 → 凭证不过。
 */
import { describe, it, expect } from 'vitest'
import { executeSubtask, parseSubtaskOutput, isNonEmptyValue } from '../src/application/use-cases/ExecuteTask.js'
import { executeMoveTask } from '../src/application/use-cases/MoveTask.js'
import type { WorkflowRunner, WorkflowRunOutcome } from '../src/application/ports.js'
import { makeHarness, task, req } from './application/harness.js'

const SRC = 'packages/pages/dsh-pmboard/src/domain/task/TaskStatus.ts'
const CLIENT = 'packages/pages/dsh-pmboard/lib/client.js'

class FakeRunner implements WorkflowRunner {
  calls: unknown[] = []
  constructor(private readonly outcome: WorkflowRunOutcome) {}
  async start(input: unknown): Promise<WorkflowRunOutcome> {
    this.calls.push(input)
    return this.outcome
  }
}

const okRun = (payload: unknown): WorkflowRunOutcome => ({ ok: true, value: { ok: true, output: payload } })

function seed() {
  const h = makeHarness()
  h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing' })]
  h.repo.ledger.tasks = [
    task({ id: 't-p', requirementId: 'REQ-000001', status: 'in_progress', claimedAt: h.clock.t, title: '父卡' }),
    task({ id: 't-s', requirementId: 'REQ-000001', status: 'todo', parentId: 't-p', stageKind: 'dev' as never, title: '研发', acceptance: '改动落盘并跑通测试' }),
  ]
  return h
}

const exec = { agent: { id: 'session-w-001' } }

describe('子卡闭环（3.4 凭证三项）', () => {
  it('全通过：run completed + 产出含 filesChanged + 文件 mtime≥开工 → 子卡 done', async () => {
    const h = seed()
    h.docs.put(SRC, 'x')
    h.docs.put(CLIENT, 'x')
    h.deps.workflow = new FakeRunner(okRun(JSON.stringify({ filesChanged: [SRC], completed: ['改完状态机'], evidence: ['vitest 绿'] })))
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(true)
    const t = h.repo.ledger.tasks.find(x => x.id === 't-s')!
    expect(t.status).toBe('done')
    expect(t.lastRun?.ok).toBe(true)
    expect(t.lastRun?.stopReason).toBe('completed')
    expect(t.lastReport?.filesChanged).toEqual([SRC])
    expect(t.executions[0]?.outcome).toBe('succeeded')
  })

  it('③ run 未完成（stopReason=error）→ 子卡不 done', async () => {
    const h = seed()
    h.docs.put(SRC, 'x')
    h.deps.workflow = new FakeRunner({ ok: false, reason: 'error: child failed' })
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(false)
    expect(h.repo.ledger.tasks.find(x => x.id === 't-s')!.status).not.toBe('done')
    expect(h.repo.ledger.tasks.find(x => x.id === 't-s')!.lastRun?.ok).toBe(false)
  })

  it('② 文件证据不过（mtime 早于开工）→ 子卡不 done', async () => {
    const h = seed()
    h.docs.put(SRC, 'x', h.clock.t - 10_000)
    h.docs.put(CLIENT, 'x')
    h.deps.workflow = new FakeRunner(okRun(JSON.stringify({ filesChanged: [SRC], completed: ['改完'] })))
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('REQBOARD_SUBTASK_GATE')
    expect(h.repo.ledger.tasks.find(x => x.id === 't-s')!.status).not.toBe('done')
  })

  it('① 汇报无改动文件（子代理只回文本）→ 子卡不 done（不猜文件）', async () => {
    const h = seed()
    h.deps.workflow = new FakeRunner(okRun('我做完了，功能正常'))
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('REQBOARD_SUBTASK_GATE')
    expect(h.repo.ledger.tasks.find(x => x.id === 't-s')!.status).not.toBe('done')
  })

  it('3.6 页面插件构建新鲜度：改了 src 但 client.js 陈旧 → 凭证不过', async () => {
    const h = seed()
    h.docs.put(SRC, 'x', h.clock.t)
    h.docs.put(CLIENT, 'x', h.clock.t - 10_000)
    h.deps.workflow = new FakeRunner(okRun(JSON.stringify({ filesChanged: [SRC], completed: ['改完'] })))
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('REQBOARD_SUBTASK_GATE')
  })

  it('3.3 引擎缺失 → 子卡显式失败（不静默成功）', async () => {
    const h = seed()
    h.docs.put(SRC, 'x')
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(false)
    expect(r.reason).toContain('engine_unavailable')
  })

  it('幂等：已 done 的子卡重入直接返回 ok（不重复执行）', async () => {
    const h = seed()
    h.repo.ledger.tasks.find(x => x.id === 't-s')!.status = 'done'
    const runner = new FakeRunner(okRun('{}'))
    h.deps.workflow = runner
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(true)
    expect(runner.calls).toHaveLength(0)
  })
})

describe('父卡收尾门（3.5 / INV-5）', () => {
  it('存在未 done 子卡 → 父卡 done 被拒（REQBOARD_SUBTASK_GATE）', async () => {
    const h = seed()
    h.docs.put('src/x.ts', 'x')
    h.repo.ledger.tasks.find(x => x.id === 't-p')!.lastReport = { at: h.clock.t, reportIndex: 1, filesChanged: ['src/x.ts'], completed: ['父卡完成'] }
    let code: string | undefined
    try {
      await executeMoveTask(h.deps, { task_id: 't-p', to: 'done' }, exec)
    } catch (err) { code = (err as { code?: string }).code }
    expect(code).toBe('REQBOARD_SUBTASK_GATE')
    expect(h.repo.ledger.tasks.find(x => x.id === 't-p')!.status).not.toBe('done')
  })

  it('全部子卡 done → 父卡可通过（四重校验照旧）', async () => {
    const h = seed()
    h.docs.put('src/x.ts', 'x')
    const p = h.repo.ledger.tasks.find(x => x.id === 't-p')!
    p.lastReport = { at: h.clock.t, reportIndex: 1, filesChanged: ['src/x.ts'], completed: ['父卡完成'] }
    h.repo.ledger.tasks.find(x => x.id === 't-s')!.status = 'done'
    const r = await executeMoveTask(h.deps, { task_id: 't-p', to: 'done' }, exec) as { to?: string }
    expect(r.to).toBe('done')
  })
})

describe('产出解析与空值判定（防"看起来在工作"）', () => {
  it('JSON 对象直接读；文本尝试 parse；否则整段作为一条完成项且 filesChanged 为空', () => {
    expect(parseSubtaskOutput(JSON.stringify({ filesChanged: ['a.ts'], completed: ['x'] })).filesChanged).toEqual(['a.ts'])
    expect(parseSubtaskOutput('not json').filesChanged).toEqual([])
    expect(parseSubtaskOutput('not json').completed).toHaveLength(1)
    expect(parseSubtaskOutput({ filesChanged: ['b.ts'] }).filesChanged).toEqual(['b.ts'])
  })

  it('isNonEmptyValue：null/空串/空对象/空数组都算空', () => {
    expect(isNonEmptyValue(null)).toBe(false)
    expect(isNonEmptyValue('')).toBe(false)
    expect(isNonEmptyValue({})).toBe(false)
    expect(isNonEmptyValue([])).toBe(false)
    expect(isNonEmptyValue({ ok: true })).toBe(true)
  })
})
