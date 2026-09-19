/**
 * L1 领域单测 · rollup 决策规约（REQ-47939a t3 / INV-5）。
 *
 * 锚点：① 决策正确（R1/R2/R3，规则与理由文案）；② **纯函数无副作用**——Object.freeze 入参后
 * 调用不抛、且入参对象内容不变（卡里的可证伪验收：freeze 入参不抛）；
 * ③ 人工闸门不可越（决策只会产出 system 白名单内的转移）。
 */
import { describe, it, expect } from 'vitest'
import {
  planRollup,
  planPickupAdvance,
  planPickupReconcile,
  type RollupView,
} from '../../src/domain/workflow/RollupSpec.js'
import { SYSTEM_REQ_TRANSITIONS } from '../../src/domain/requirement/RequirementStatus.js'

function view(over: Partial<RollupView> = {}): RollupView {
  return deepFreeze({ requirements: [], tasks: [], triages: [], ...over })
}
function deepFreeze<T>(v: T): T {
  if (v !== null && typeof v === 'object') {
    Object.freeze(v)
    for (const k of Object.keys(v as Record<string, unknown>)) deepFreeze((v as Record<string, unknown>)[k])
  }
  return v
}

describe('planRollup（R2/R3）', () => {
  it('implementing + 全部未取消任务 done → R2 accepting', () => {
    const v = view({
      requirements: [{ id: 'REQ-000001', status: 'implementing' }],
      tasks: [{ requirementId: 'REQ-000001', status: 'done' }, { requirementId: 'REQ-000001', status: 'done' }],
    })
    expect(planRollup(v)).toEqual([{
      reqId: 'REQ-000001', from: 'implementing', to: 'accepting', rule: 'R2',
      reason: '全部 2 个实施任务已完成，自动进入验收',
    }])
  })

  it('canceled 不计入完成度；无任务不推进；非触发态不推进', () => {
    expect(planRollup(view({
      requirements: [{ id: 'R', status: 'implementing' }],
      tasks: [{ requirementId: 'R', status: 'done' }, { requirementId: 'R', status: 'canceled' }],
    })).map(m => m.rule)).toEqual(['R2'])
    expect(planRollup(view({ requirements: [{ id: 'R', status: 'implementing' }] }))).toEqual([])
    expect(planRollup(view({
      requirements: [{ id: 'R', status: 'brainstorming' }],
      tasks: [{ requirementId: 'R', status: 'done' }],
    }))).toEqual([])
  })

  it('design + 已有任务 → R3 decomposing（不再自动越过人工门）', () => {
    const moves = planRollup(view({
      requirements: [{ id: 'R', status: 'design' }],
      tasks: [{ requirementId: 'R', status: 'todo' }],
    }))
    expect(moves).toHaveLength(1)
    expect(moves[0]).toMatchObject({ from: 'design', to: 'decomposing', rule: 'R3' })
    expect(moves[0].reason).toContain('已按批准的计划落库 1 个任务')
  })

  it('decomposing 停在原地（decomposing>implementing 是人工门）', () => {
    expect(planRollup(view({
      requirements: [{ id: 'R', status: 'decomposing' }],
      tasks: [{ requirementId: 'R', status: 'done' }],
    }))).toEqual([])
  })

  it('onlyReqId 过滤', () => {
    const v = view({
      requirements: [{ id: 'A', status: 'implementing' }, { id: 'B', status: 'implementing' }],
      tasks: [{ requirementId: 'A', status: 'done' }, { requirementId: 'B', status: 'done' }],
    })
    expect(planRollup(v, 'B').map(m => m.reqId)).toEqual(['B'])
  })

  it('决策只产出 system 白名单内的转移（人工闸门不可越）', () => {
    for (const rule of planRollup(view({
      requirements: [
        { id: 'A', status: 'design' }, { id: 'B', status: 'implementing' },
      ],
      tasks: [{ requirementId: 'A', status: 'todo' }, { requirementId: 'B', status: 'done' }],
    }))) {
      expect(SYSTEM_REQ_TRANSITIONS.has(rule.from + '>' + rule.to)).toBe(true)
    }
  })
})

describe('planPickupAdvance / planPickupReconcile（R1/R0）', () => {
  it('draft → brainstorming；非 draft 不动；不存在不动', () => {
    const v = view({ requirements: [{ id: 'R', status: 'draft' }] })
    expect(planPickupAdvance(v, 'R')).toMatchObject({ from: 'draft', to: 'brainstorming', rule: 'R1' })
    expect(planPickupAdvance(v, 'X')).toBeUndefined()
    expect(planPickupAdvance(view({ requirements: [{ id: 'R', status: 'implementing' }] }), 'R')).toBeUndefined()
  })

  it('对账只动「draft + 已挂窗口（sourceSessionId / triage 锚点）」', () => {
    const v = view({
      requirements: [
        { id: 'BOUND', status: 'draft', sourceSessionId: 'session-abc' },
        { id: 'HUMAN', status: 'draft' },
        { id: 'TRI', status: 'draft' },
        { id: 'LATER', status: 'brainstorming', sourceSessionId: 'session-abc' },
      ],
      triages: [{ resultRequirementId: 'TRI' }],
    })
    expect(planPickupReconcile(v).map(m => m.reqId)).toEqual(['BOUND', 'TRI'])
  })
})

describe('纯函数无副作用（卡的可证伪验收：Object.freeze 入参不抛）', () => {
  it('冻结视图后调用全部决策函数不抛，且视图内容不变', () => {
    const requirements = [{ id: 'R', status: 'implementing' as const }]
    const tasks = [{ requirementId: 'R', status: 'done' as const }]
    const v = view({ requirements, tasks })
    const snapshot = JSON.stringify(v)
    expect(() => planRollup(v)).not.toThrow()
    expect(() => planPickupReconcile(v)).not.toThrow()
    expect(() => planPickupAdvance(v, 'R')).not.toThrow()
    expect(JSON.stringify(v)).toBe(snapshot)
  })
})
