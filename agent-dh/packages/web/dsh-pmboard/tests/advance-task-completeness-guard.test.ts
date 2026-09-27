/**
 * 阶段推进的任务完整性守卫（REQ-260927100007-b8ba t5 / FR-3）。
 *
 * 契约：目标态是 implementing 时，若「已批准计划里有任务、台账却 0 张未取消任务」→ 拒绝推进，
 * 且错误信息含**可执行的修复指引**；空计划 / 非 implementing / 已有任务 / 存量需求（无产物簿）一律放行。
 */
import { describe, it, expect } from 'vitest'
import { taskCompletenessGap } from '../src/application/internal/task-completeness.js'
import { executeMoveRequirement } from '../src/application/use-cases/MoveRequirement.js'
import { makeHarness, req, task } from './application/harness.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const planOf = (n: number) => ({
  path: 'docs/requirements/REQ-000001/decomposition.md',
  summary: 's',
  tasks: Array.from({ length: n }, (_, i) => ({
    key: 't' + (i + 1), title: '任务' + (i + 1), phase: 'implement', side: 'backend',
    dependsOn: [], acceptance: '跑 vitest 看到绿', implementation: '改 src/x.ts',
  })),
  submittedAt: 1,
  submittedBy: { kind: 'agent', sessionId: 'session-w-001' },
} as never)

function liveReq(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return req({
    id: 'REQ-000001',
    status: 'decomposing',
    artifacts: [{
      stage: 'decomposing', kind: 'decomposition',
      path: 'docs/requirements/REQ-000001/decomposition.md',
      registeredAt: 1, registeredBy: { kind: 'agent', sessionId: 'session-w-001' },
      confirmedAt: 2, confirmedBy: { kind: 'human', sessionId: 'session-w-001' },
    } as never],
    ...over,
  })
}

describe('taskCompletenessGap（FR-3 判定）', () => {
  it('计划有 14 张、台账 0 张 → 报缺口且含可执行修复指引', () => {
    const g = taskCompletenessGap(liveReq({ plan: planOf(14) }), [], 'implementing')
    expect(g).toBeDefined()
    expect(g).toContain('14')
    expect(g).toContain('reqboard_decompose')
    expect(g).toContain('拆分')
  })

  it('空计划 / 非 implementing 目标 / 已有未取消任务 / 存量无产物簿 → 一律放行', () => {
    expect(taskCompletenessGap(liveReq({ plan: undefined }), [], 'implementing')).toBeUndefined()
    expect(taskCompletenessGap(liveReq(), [], 'implementing')).toBeUndefined()
    expect(taskCompletenessGap(liveReq({ plan: planOf(3) }), [{ ...task({ requirementId: 'REQ-000001' }) }], 'implementing')).toBeUndefined()
    expect(taskCompletenessGap(liveReq({ plan: planOf(3) }), [], 'accepting')).toBeUndefined()
    const legacy = liveReq({ plan: planOf(3) })
    delete (legacy as { artifacts?: unknown }).artifacts
    expect(taskCompletenessGap(legacy, [], 'implementing')).toBeUndefined()
  })
})

describe('executeMoveRequirement：decomposing→implementing 被守卫拦下（FR-3）', () => {
  it('计划有卡、队列 0 卡 → REQBOARD_TASK_INCOMPLETE，且需求状态不变', async () => {
    const h = makeHarness()
    h.repo.ledger.requirements = [liveReq({ plan: planOf(2) })]
    // B-5（Lead 裁定）：不许静默删掉"此刻没有任务"这条保证 —— 换成显式前置断言（更强、且意图可见）。
    // v9 口径：任务只在队列；"0 卡" = 该需求没有队列文件（不 seed 即无队列）。
    expect(h.queueExists('REQ-000001')).toBe(false)
    expect(await h.tasksOf('REQ-000001')).toHaveLength(0)
    let code: string | undefined
    try {
      await executeMoveRequirement(h.deps, { to: 'implementing' }, { agent: { id: 'session-w-001' } })
    } catch (err) {
      code = (err as { code?: string }).code
    }
    expect(code).toBe('REQBOARD_TASK_INCOMPLETE')
    expect(h.repo.ledger.requirements[0]!.status).toBe('decomposing')
  })
})
