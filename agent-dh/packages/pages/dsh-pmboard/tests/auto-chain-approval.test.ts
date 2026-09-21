/**
 * 批准计划后的零点击主链测试（REQ-4842fe t10 / design/test-cases.md §4.1/4.2/7.1）。
 *
 * 口径：批准计划（唯一人工动作）之后**不再调用任何人工工具**，需求应一路自动推进到
 * accepting；全程不出现「确认拆分清单」弹框；批准弹框文案含自动开跑说明。
 */
import { describe, it, expect } from 'vitest'
import { askConfirm } from '../src/application/use-cases/AskConfirm.js'
import { DEFAULT_CONFIRM_OPTIONS } from '../src/domain/text/labels.js'
import type { WorkflowRunner, WorkflowRunOutcome } from '../src/application/ports.js'
import { makeHarness, req } from './application/harness.js'

const FILE = 'src/domain/x.ts'
const exec = { agent: { id: 'session-w-001' } }

class OkRunner implements WorkflowRunner {
  async start(_i: unknown): Promise<WorkflowRunOutcome> {
    return { ok: true, value: { ok: true, output: JSON.stringify({ filesChanged: [FILE], completed: ['子卡完成'] }) } }
  }
}

function seed() {
  const h = makeHarness()
  h.docs.put(FILE, 'x')
  h.repo.ledger.requirements = [req({
    id: 'REQ-000001',
    // 2026-09-21 阶段门裁定（w-2105d331 代录）：拆分计划归 decomposing，批准门在 decomposing→implementing
    status: 'decomposing',
    category: 'feature',
    sourceSessionId: 'session-w-001',
    // 拆分计划产物（真实流程中由 reqboard_submit(kind=plan) 登记，批准门落章它）
    artifacts: [{
      stage: 'decomposing', kind: 'decomposition',
      path: 'docs/requirements/REQ-000001/decomposition.md',
      registeredAt: 1, registeredBy: { kind: 'agent', sessionId: 'session-w-001' },
    } as never],
    plan: {
      path: 'docs/requirements/REQ-000001/decomposition.md',
      summary: '把长任务拆短',
      tasks: [{
        key: 't1', title: '实现子卡层', phase: 'implement', side: 'backend', dependsOn: [],
        acceptance: '跑 pnpm vitest 看到全绿', implementation: '改 src/domain/x.ts 与 packages/x/src/y.ts',
      }],
      submittedAt: h.clock.t,
      submittedBy: { kind: 'agent', sessionId: 'session-w-001' },
    },
  })]
  h.repo.ledger.tasks = []
  h.deps.workflow = new OkRunner()
  h.questions.answers = [{ selected: [DEFAULT_CONFIRM_OPTIONS[0] as string] }]
  return h
}

describe('批准计划 → 零点击跑到 accepting（4.1 / 4.2 / 7.1）', () => {
  it('批准后自动拆分 + 自动进入实施 + 自动跑完子卡链 → 需求 accepting', async () => {
    const h = seed()
    const out = await askConfirm(h.deps, {
      requirement_id: 'REQ-000001', target: 'plan', question: '批准拆分计划进入拆分？',
    }, exec) as { confirmed?: boolean; note?: string }

    expect(out.confirmed).toBe(true)
    const requirement = h.repo.ledger.requirements[0]!
    expect(requirement.status).toBe('accepting')
    expect(requirement.autoRun).toBe(true)

    // 拆分落库：父卡 + 子卡（feature = dev→integrate→review→test）
    const parents = h.repo.ledger.tasks.filter(t => t.parentId === undefined)
    expect(parents).toHaveLength(1)
    const subs = h.repo.ledger.tasks.filter(t => t.parentId === parents[0]!.id)
    expect(subs.map(s => s.stageKind)).toEqual(['dev', 'integrate', 'review', 'test'])
    expect(subs.every(s => s.status === 'done')).toBe(true)
    expect(parents[0]!.status).toBe('done')
  })

  it('批准弹框文案含「自动拆分并立即开跑」说明（7.1）', async () => {
    const h = seed()
    await askConfirm(h.deps, { requirement_id: 'REQ-000001', target: 'plan', question: '批准拆分计划进入拆分？' }, exec)
    const asked = h.questions.asked[0]!
    expect(asked.question).toContain('自动拆分')
    expect(asked.question).toContain('立即开跑')
  })

  it('4.2 全程不出现「确认拆分清单」弹框（只有一次批准弹框）', async () => {
    const h = seed()
    await askConfirm(h.deps, { requirement_id: 'REQ-000001', target: 'plan', question: '批准拆分计划进入拆分？' }, exec)
    expect(h.questions.asked).toHaveLength(1)
    expect(h.questions.asked[0]!.header).toBe('确认')
  })

  it('decomposition 产物由批准门自动落章（门合并留痕）', async () => {
    const h = seed()
    await askConfirm(h.deps, { requirement_id: 'REQ-000001', target: 'plan', question: '批准？' }, exec)
    const art = (h.repo.ledger.requirements[0]!.artifacts ?? []).find(a => a.kind === 'decomposition')
    expect(art?.confirmedAt).toBeDefined()
    expect(h.repo.ledger.requirements[0]!.comments.some(c => c.body.includes('门合并'))).toBe(true)
  })
})


describe('REQ-84bea5：断链修复回归测试', () => {
  it('①修复验证：RTM 覆盖（FR-1）+ plan.tasks 无 refs → 批准成功（双源合并生效）', async () => {
    const h = makeHarness()
    h.clock.t = 1000
    
    // 设置 requirement.md（含 FR-1）
    h.docs.put('docs/requirements/REQ-000002/requirement.md', `## 功能需求\n\n- **FR-1** 需求条款\n`)
    
    // 设置 decomposition.md（RTM 表覆盖 FR-1）
    h.docs.put('docs/requirements/REQ-000002/decomposition.md', `
## 拆分计划

| 任务编号 | 任务标题 | 根编号 |
|---------|---------|-------|
| t1      | 实现    | FR-1  |
`)
    
    h.repo.ledger.requirements = [req({
      id: 'REQ-000002',
      status: 'decomposing',
      artifacts: [
        {
          stage: 'decomposing', kind: 'requirement',
          path: 'docs/requirements/REQ-000002/requirement.md',
          registeredAt: 1, registeredBy: { kind: 'agent', sessionId: 'session-w-001' },
          confirmedAt: 1, confirmedBy: { kind: 'human', sessionId: 'session-w-001' },
        } as never,
        {
          stage: 'decomposing', kind: 'decomposition',
          path: 'docs/requirements/REQ-000002/decomposition.md',
          registeredAt: 1, registeredBy: { kind: 'agent', sessionId: 'session-w-001' },
        } as never
      ],
      plan: {
        path: 'docs/requirements/REQ-000002/decomposition.md',
        summary: '测试双源合并',
        tasks: [{
          key: 't1', title: '实现', phase: 'implement', side: 'backend', dependsOn: [],
          acceptance: '编译通过', implementation: '改代码',
          // 关键：plan.tasks 不含 requirement_refs，只有 RTM 覆盖
        }],
        submittedAt: h.clock.t,
        submittedBy: { kind: 'agent', sessionId: 'session-w-001' },
      },
    })]
    h.repo.ledger.tasks = []
    h.deps.workflow = new OkRunner()
    h.questions.answers = [{ selected: [DEFAULT_CONFIRM_OPTIONS[0] as string] }]
    
    const out = await askConfirm(h.deps, {
      requirement_id: 'REQ-000002', target: 'plan', question: '批准？',
    }, exec) as { confirmed?: boolean; gate_failure?: unknown }
    
    // 断言：批准成功（覆盖门禁通过，证明双源合并生效）
    // 核心验证：plan.tasks 无 refs，但 RTM 有覆盖 → 门禁通过
    expect(out.confirmed).toBe(true)
    expect(out.gate_failure).toBeUndefined()
    
    // 注：完整的自动推进链（implementing + autoRun）需要更复杂的 workflow 设置
    // 本测试只验证覆盖门禁双源合并的核心修复
  })
  
  it('③验收文档门禁：无 plan.md、有 decomposition.md → passed=true', async () => {
    const { checkDocCompleteness } = await import('../src/domain/workflow/DocCompleteness.js')
    
    const result = checkDocCompleteness({
      files: new Set([
        'requirement.md',
        'decomposition.md',
        'design/architecture.md',
        'design/data-model.md',
        'design/interfaces.md',
        'design/test-cases.md',
        'reviews/review-1.md',
        'tests/test-1.test.ts',
        'tasks/t-001.md',
      ]),
      taskIds: ['t-001'],
    })
    
    // 断言：验收通过（plan.md 已从必填清单删除）
    expect(result.passed).toBe(true)
    expect(result.missing).toEqual([])
  })
})

