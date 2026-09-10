/**
 * 需求状态自动推进（rollup）单测 —— 派生规则的正确性与闸门不可越性。
 * 覆盖：R1 接手推进（draft→reviewing）、R2 实施完成（implementing→accepting）、
 * 非触发态不动、canceled 任务不计入完成度、人工闸门永不被自动越过。
 */
import { describe, it, expect } from 'vitest'
import { applyPickupAdvance, applyPickupReconcile, applyTaskRollup } from '../src/host/rollup.js'
import { emptyLedger, type ReqboardLedger, type RequirementRecord, type TaskRecord } from '../src/shared/protocol.js'

let seq = 0
const rid = (p: string) => `${p}-${String(++seq).padStart(6, '0')}`

function req(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: rid('REQ'), title: '需求', description: '', status: 'draft', blocked: false,
    comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    ...over,
  } as RequirementRecord
}

function task(reqId: string, over: Partial<TaskRecord> = {}): TaskRecord {
  return {
    id: rid('t'), requirementId: reqId, title: '任务', description: '',
    phase: 'implement', side: 'fullstack', dependsOn: [],
    scope: { apis: [], tables: [], files: [] },
    acceptance: '', context: '', status: 'todo', blocked: false,
    executions: [], comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    ...over,
  } as TaskRecord
}

function ledger(over: Partial<ReqboardLedger> = {}): ReqboardLedger {
  return { ...emptyLedger(), ...over }
}

const ctx = { now: 2_000, commentId: () => rid('c') }

// -- R1 接手推进 -----------------------------------------------------------

describe('applyPickupAdvance（R1 接手推进）', () => {
  it('draft 需求被窗口接手 → reviewing，并留痕', () => {
    const r = req({ status: 'draft', sourceSessionId: 'session-abc' })
    const l = ledger({ requirements: [r] })
    const advanced = applyPickupAdvance(l, r.id, ctx)
    expect(advanced).toBeDefined()
    expect(l.requirements[0].status).toBe('reviewing')
    expect(l.requirements[0].version).toBe(2)
    expect(l.requirements[0].updatedBy.kind).toBe('system')
    expect(l.requirements[0].comments.at(-1)?.body).toContain('[自动推进] draft → reviewing')
  })

  it('非 draft 需求不动（幂等：已在评审/实施的需求不被回拉）', () => {
    for (const status of ['reviewing', 'decomposing', 'implementing', 'accepting', 'done'] as const) {
      const r = req({ status })
      const l = ledger({ requirements: [r] })
      expect(applyPickupAdvance(l, r.id, ctx)).toBeUndefined()
      expect(l.requirements[0].status).toBe(status)
    }
  })

  it('需求不存在 → 不动', () => {
    const l = ledger({ requirements: [req()] })
    expect(applyPickupAdvance(l, 'REQ-ffffff', ctx)).toBeUndefined()
  })
})

// -- R2 实施完成 rollup ----------------------------------------------------

describe('applyTaskRollup（R2 实施完成 → 验收）', () => {
  it('implementing 且全部任务 done → accepting', () => {
    const r = req({ status: 'implementing' })
    const l = ledger({ requirements: [r], tasks: [task(r.id, { status: 'done' }), task(r.id, { status: 'done' })] })
    const advanced = applyTaskRollup(l, ctx)
    expect(advanced).toHaveLength(1)
    expect(l.requirements[0].status).toBe('accepting')
    expect(l.requirements[0].comments.at(-1)?.body).toContain('全部 2 个实施任务已完成')
  })

  it('仍有未完成任务 → 不动', () => {
    const r = req({ status: 'implementing' })
    const l = ledger({ requirements: [r], tasks: [task(r.id, { status: 'done' }), task(r.id, { status: 'testing' })] })
    expect(applyTaskRollup(l, ctx)).toHaveLength(0)
    expect(l.requirements[0].status).toBe('implementing')
  })

  it('canceled 任务不计入完成度（全部 done + 1 canceled → 仍推进）', () => {
    const r = req({ status: 'implementing' })
    const l = ledger({
      requirements: [r],
      tasks: [task(r.id, { status: 'done' }), task(r.id, { status: 'canceled' })],
    })
    expect(applyTaskRollup(l, ctx)).toHaveLength(1)
    expect(l.requirements[0].comments.at(-1)?.body).toContain('全部 1 个实施任务已完成')
  })

  it('无任务 → 不动（0 任务不算完成）', () => {
    const r = req({ status: 'implementing' })
    const l = ledger({ requirements: [r] })
    expect(applyTaskRollup(l, ctx)).toHaveLength(0)
  })

  it('非 implementing 状态不动（人工闸门不可绕过：reviewing 全部任务 done 也不自动进实施）', () => {
    const r = req({ status: 'reviewing' })
    const l = ledger({ requirements: [r], tasks: [task(r.id, { status: 'done' })] })
    expect(applyTaskRollup(l, ctx)).toHaveLength(0)
    expect(l.requirements[0].status).toBe('reviewing')
  })

  it('onlyReqId 过滤：只重算指定需求', () => {
    const a = req({ status: 'implementing' })
    const b = req({ status: 'implementing' })
    const l = ledger({
      requirements: [a, b],
      tasks: [task(a.id, { status: 'done' }), task(b.id, { status: 'done' })],
    })
    const advanced = applyTaskRollup(l, ctx, b.id)
    expect(advanced).toHaveLength(1)
    expect(advanced[0].id).toBe(b.id)
    expect(l.requirements.find(r => r.id === a.id)!.status).toBe('implementing')
  })
})
// -- R0 启动对账 -----------------------------------------------------------

describe('applyPickupReconcile（R0 启动对账）', () => {
  it('已挂窗口的 draft 需求 → reviewing（带对账留痕）', () => {
    const bound = req({ status: 'draft', sourceSessionId: 'session-abc' })
    const human = req({ status: 'draft' }) // 人工建卡：无 sourceSessionId
    const l = ledger({ requirements: [bound, human] })
    const advanced = applyPickupReconcile(l, ctx)
    expect(advanced.map(r => r.id)).toEqual([bound.id])
    expect(l.requirements[0].status).toBe('reviewing')
    expect(l.requirements[0].comments.at(-1)?.body).toContain('启动对账')
    expect(l.requirements[1].status).toBe('draft')
  })

  it('triage 锚点绑定的 draft 需求也纳入对账', () => {
    const r0 = req({ status: 'draft' })
    const l = ledger({
      requirements: [r0],
      triages: [{ id: 'tri-1', sessionId: 'session-x', status: 'confirmed', resultRequirementId: r0.id } as never],
    })
    expect(applyPickupReconcile(l, ctx)).toHaveLength(1)
    expect(l.requirements[0].status).toBe('reviewing')
  })

  it('幂等：第二次跑无变化（已在评审的不再动）', () => {
    const r0 = req({ status: 'draft', sourceSessionId: 'session-abc' })
    const l = ledger({ requirements: [r0] })
    expect(applyPickupReconcile(l, ctx)).toHaveLength(1)
    expect(applyPickupReconcile(l, ctx)).toHaveLength(0)
  })

  it('非 draft 状态一律不动，且永不越过人工闸门（reviewing 不被自动推成 decomposing）', () => {
    const r0 = req({ status: 'reviewing', sourceSessionId: 'session-abc' })
    const l = ledger({ requirements: [r0] })
    expect(applyPickupReconcile(l, ctx)).toHaveLength(0)
    expect(l.requirements[0].status).toBe('reviewing')
  })
})
