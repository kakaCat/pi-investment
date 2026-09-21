/**
 * 失败暂停、告警与返工测试（REQ-4842fe t8）——对应 design/test-cases.md §5。
 *
 * 口径：失败不自动重试；子卡退回 + attempt+1 + revisions(rollback)；autoRun=false；
 * 高优告警发出；弹框三选各自生效；退上游重批准后卡数不变且有 revisions(update)；
 * 自动链不产生 done→in_progress。
 */
import { describe, it, expect } from 'vitest'
import { advanceRequirement } from '../src/application/use-cases/AdvanceChain.js'
import { openFailurePopup, handleFailureChoice, FAILURE_CHOICE_LABELS } from '../src/application/use-cases/HandleFailure.js'
import { applyReworkUpdate } from '../src/application/internal/rework-update.js'
import { planTask } from './helpers/plan-task.js'
import type { WorkflowRunner, WorkflowRunOutcome, FailureAlertPort } from '../src/application/ports.js'
import { makeHarness, task, req } from './application/harness.js'

const FILE = 'src/domain/x.ts'

class FlakyRunner implements WorkflowRunner {
  calls = 0
  failOn: number
  constructor(failOn: number) { this.failOn = failOn }
  async start(_input: unknown): Promise<WorkflowRunOutcome> {
    this.calls += 1
    if (this.calls === this.failOn) return { ok: false, reason: 'error: child failed' }
    return { ok: true, value: { ok: true, output: JSON.stringify({ filesChanged: [FILE], completed: ['子卡完成'] }) } }
  }
}

function seed(runner: WorkflowRunner) {
  const h = makeHarness()
  h.docs.put(FILE, 'x')
  h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing', category: 'feature', autoRun: true, sourceSessionId: 'session-w-001' })]
  h.repo.ledger.tasks = [task({ id: 't-p', requirementId: 'REQ-000001', status: 'todo', title: '父卡' })]
  h.deps.workflow = runner
  const alerts: Array<{ requirementId: string; title: string; content: string }> = []
  const port: FailureAlertPort = { alert: (i) => { alerts.push(i) } }
  h.deps.alert = port
  return { h, alerts }
}

describe('失败暂停与回退（5.1/5.2/5.5）', () => {
  it('子卡失败 → 退回 todo + attempt+1 + revisions(rollback) + 失败评论；autoRun=false；高优告警发出', async () => {
    const runner = new FlakyRunner(2)
    const { h, alerts } = seed(runner)
    const out = await advanceRequirement(h.deps, 'REQ-000001')
    expect(out.stopped).toBe('paused')
    const rolled = h.repo.ledger.tasks.find(t => t.parentId === 't-p' && (t.attempt ?? 0) > 0)!
    expect(rolled).toBeDefined()
    expect(rolled.status).toBe('todo')
    expect(rolled.attempt).toBe(1)
    expect(rolled.revisions?.map(r => r.kind)).toEqual(['rollback'])
    expect(rolled.revisions?.[0]?.changes.join(' ')).toContain('attempt: 0→1')
    expect(rolled.comments.some(c => c.body.includes('子卡失败'))).toBe(true)
    expect(h.repo.ledger.requirements[0]!.autoRun).toBe(false)
    expect(alerts).toHaveLength(1)
    expect(alerts[0]!.title).toContain('实施链暂停')
    expect(alerts[0]!.content).toContain('重跑该卡')
  })

  it('5.2 不自动重试：失败后再次触发不产生新 run（autoRun=false）', async () => {
    const runner = new FlakyRunner(2)
    const { h } = seed(runner)
    await advanceRequirement(h.deps, 'REQ-000001')
    const callsAfterFail = runner.calls
    const again = await advanceRequirement(h.deps, 'REQ-000001')
    expect(again.stopped).toBe('not_autorun')
    expect(runner.calls).toBe(callsAfterFail)
  })

  it('5.6 自动链不产生 done→in_progress 转移', async () => {
    const { h } = seed(new FlakyRunner(-1))
    await advanceRequirement(h.deps, 'REQ-000001')
    for (const t of h.repo.ledger.tasks) {
      const hist = (t.statusHistory ?? []).map(x => x.status)
      const di = hist.indexOf('done')
      expect(di === -1 || !hist.slice(di + 1).includes('in_progress'), t.id).toBe(true)
    }
  })
})

describe('处置弹框三选（5.3）', () => {
  it('openFailurePopup 返回人工选择（重跑/退回上游/取消）', async () => {
    const { h } = seed(new FlakyRunner(2))
    expect(FAILURE_CHOICE_LABELS.rerun).toBe('重跑该卡')
    h.questions.answers = [{ selected: [FAILURE_CHOICE_LABELS.upstream] }]
    const choice = await openFailurePopup(h.deps, 'REQ-000001')
    expect(choice).toBe('upstream')
    expect(h.questions.asked[0]?.options?.map(o => o.label)).toContain(FAILURE_CHOICE_LABELS.cancel)
  })

  it('选「重跑该卡」→ autoRun 开启并继续推进', async () => {
    const runner = new FlakyRunner(2)
    const { h } = seed(runner)
    await advanceRequirement(h.deps, 'REQ-000001')
    expect(h.repo.ledger.requirements[0]!.autoRun).toBe(false)
    const r = await handleFailureChoice(h.deps, 'REQ-000001', 'rerun')
    expect(r.ok).toBe(true)
    expect(h.repo.ledger.requirements[0]!.status).toBe('accepting')
  })

  it('选「退回上游」→ 需求回 design（人工门）', async () => {
    const { h } = seed(new FlakyRunner(2))
    await advanceRequirement(h.deps, 'REQ-000001')
    const r = await handleFailureChoice(h.deps, 'REQ-000001', 'upstream')
    expect(r.ok).toBe(true)
    expect(h.repo.ledger.requirements[0]!.status).toBe('design')
  })

  it('选「取消」→ 需求 canceled', async () => {
    const { h } = seed(new FlakyRunner(2))
    await advanceRequirement(h.deps, 'REQ-000001')
    const r = await handleFailureChoice(h.deps, 'REQ-000001', 'cancel')
    expect(r.ok).toBe(true)
    expect(h.repo.ledger.requirements[0]!.status).toBe('canceled')
  })
})

describe('返工就地更新（5.4/5.5）', () => {
  it('重批准计划后：卡数不变、受影响父卡字段被更新且有 revisions(update)', async () => {
    const h = makeHarness()
    h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'design', category: 'feature' })]
    h.repo.ledger.tasks = [
      task({ id: 't-p', requirementId: 'REQ-000001', title: '父卡', acceptance: '旧验收', description: '旧描述', status: 'in_progress' }),
    ]
    const before = h.repo.ledger.tasks.length
    const updated = applyReworkUpdate(h.repo.ledger, 'REQ-000001', [
      planTask({ key: 't1', title: '父卡', acceptance: '新验收（可跑：vitest 绿）', description: '新描述', implementation: '改 y.ts', phase: 'implement', side: 'backend' }),
    ], h.clock.t)
    expect(h.repo.ledger.tasks.length).toBe(before)
    expect(updated).toHaveLength(1)
    const card = h.repo.ledger.tasks[0]!
    expect(card.acceptance).toBe('新验收（可跑：vitest 绿）')
    expect(card.revisions?.map(r => r.kind)).toEqual(['update'])
    expect(card.revisions?.[0]?.changes).toContain('acceptance')
  })
})
