/**
 * 批准拆分计划 → **同步落库**任务卡（REQ-260927100007-b8ba t4 / FR-1、FR-2）。
 *
 * 实测事故：批准计划只推进状态（createdCount=0），落库被委托给 Dive 续跑，而本需求 dive=null、
 * 全仓无人 armed → 台账 0 任务、看板拆分节点 DAG 空白、零告警静默数日（用户实测报「拆分确认
 * 没有 DAG 层级展示」）。本文件锁两件事：
 *   ① 成功路径：批准的同一次调用返回时，台账任务数 = 计划卡数，且已进入 implementing；
 *   ② 失败路径：落库被覆盖门禁拦住时**不推进**，且 pausedReason / 系统评论 / 告警三件齐备。
 */
import { describe, it, expect } from 'vitest'
import { askConfirm } from '../src/application/use-cases/AskConfirm.js'
import { DEFAULT_CONFIRM_OPTIONS } from '../src/domain/text/labels.js'
import { makeHarness, req } from './application/harness.js'

const exec = { agent: { id: 'session-w-001' } }

function planSeed() {
  const h = makeHarness()
  h.repo.ledger.requirements = [req({
    id: 'REQ-000001',
    status: 'decomposing',
    category: 'feature',
    sourceSessionId: 'session-w-001',
    artifacts: [{
      stage: 'decomposing', kind: 'decomposition',
      path: 'docs/requirements/REQ-000001/decomposition.md',
      registeredAt: 1, registeredBy: { kind: 'agent', sessionId: 'session-w-001' },
    } as never],
    plan: {
      path: 'docs/requirements/REQ-000001/decomposition.md',
      summary: '把长任务拆短',
      tasks: [
        { key: 't1', title: '实现子卡层', phase: 'implement', side: 'backend', dependsOn: [], acceptance: '跑 pnpm vitest 看到全绿', implementation: '改 src/domain/x.ts' },
        { key: 't2', title: '接线', phase: 'implement', side: 'backend', dependsOn: ['t1'], acceptance: '跑 vitest 看到全绿', implementation: '改 src/index.ts' },
      ],
      submittedAt: h.clock.t,
      submittedBy: { kind: 'agent', sessionId: 'session-w-001' },
    },
  })]
  // 任务不在此 seed（v9 口径，B-4/B-5）："无任务" = **没有队列文件**，由各用例显式断言，
  // 不静默省略——失败路径尤其要断言 `queueExists === false`（比"读到 0 条"更强，见 t-e96a0c 验收）。
  h.questions.answers = [{ selected: [DEFAULT_CONFIRM_OPTIONS[0] as string] }]
  return h
}

describe('批准计划 → 同步落库任务卡（FR-1/FR-2）', () => {
  it('成功路径：同一调用返回时队列任务数 = 计划卡数，且进入 implementing', async () => {
    const h = planSeed()
    expect(h.queueExists('REQ-000001')).toBe(false) // 前置锚：从"无队列"开始（否则下面的 2 张卡可能是旧的）
    const out = await askConfirm(h.deps, { requirement_id: 'REQ-000001', target: 'plan', question: '批准？' }, exec) as { confirmed?: boolean }
    expect(out.confirmed).toBe(true)
    const r = h.repo.ledger.requirements[0]!
    expect(r.status).toBe('implementing')
    expect(r.autoRun).toBe(true)
    const tasks = await h.tasksOf('REQ-000001')
    expect(tasks).toHaveLength(2)
    const t1 = tasks.find(t => t.title === '实现子卡层')!
    const t2 = tasks.find(t => t.title === '接线')!
    expect(t2.dependsOn).toEqual([t1.id])
    // DAG 数据源：任务卡文档落盘（看板拆分节点读的就是它 + dependsOn）
    expect(h.docs.exists('docs/requirements/REQ-000001/tasks/' + t1.id + '.md')).toBe(true)
  })

  it('失败路径：落库被覆盖门禁拦住 → 不推进，且 pausedReason/评论/告警齐备', async () => {
    const h = planSeed()
    h.docs.put('docs/requirements/REQ-000001/requirement.md', '**FR-1 覆盖门禁**：拆分时逐条核对。')
    const alerts: unknown[] = []
    h.deps.alert = { alert: (a: unknown) => { alerts.push(a) } } as never
    const out = await askConfirm(h.deps, { requirement_id: 'REQ-000001', target: 'plan', question: '批准？' }, exec) as { confirmed?: boolean }
    expect(out.confirmed).toBe(true)
    const r = h.repo.ledger.requirements[0]!
    expect(r.status).toBe('decomposing')
    expect(r.autoRun).toBeUndefined()
    // B-4：失败路径断言**更强的那个** —— 队列文件根本不存在（"校验失败不落盘"）。
    // 只断言"读到 0 条"会把"文件存在但校验不过"混进来（QueueRepository.load 两种情况都返回 undefined）。
    expect(h.queueExists('REQ-000001')).toBe(false)
    expect(await h.tasksOf('REQ-000001')).toHaveLength(0)
    expect(String(r.advance?.pausedReason ?? '')).toContain('auto_decompose_failed')
    expect(r.comments.some(c => c.body.includes('自动开跑失败'))).toBe(true)
    expect(alerts).toHaveLength(1)
  })
})
