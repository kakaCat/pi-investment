/**
 * L1 领域单测 · 验收单规约（REQ-47939a t4 / INV-6）。
 *
 * 覆盖：buildSheet 生成（每任务+需求级）、返工续版、applyVerdicts 的 invalid_input 拒绝与
 * 返工规格生成、isAllPassed；source 判别联合。
 *
 * 说明（2026-09-17 D-7 已对齐卡面）：卡面 acceptance 要求"续版只含 pending+failed"。t4 落地时
 * 既有实现与既有测试都是"只含 failed（pending 也被丢弃）"，按零行为变更先落成 failed-only 并
 * 上浮为待裁决项；用户随后裁定"本轮顺带修"，故此处断言已改为 **failed + pending 都带过**，
 * 并新增"上一版无 failed（仅 pending）不进续版"的守卫用例（保住未被要求改动的另一条语义）。
 */
import { describe, it, expect } from 'vitest'
import {
  buildSheet,
  applyVerdicts,
  isAllPassed,
  isFullyDecided,
  REQUIREMENT_LEVEL_CRITERION,
  type SheetLike,
} from '../../src/domain/workflow/AcceptanceSheetSpec.js'
import { hasErrorCode, REQBOARD_ERROR_CODES } from '../../src/domain/errors.js'

const actor = { kind: 'human', sessionId: 'w-abcdef12' } as const

describe('buildSheet：验收单生成', () => {
  it('v1：每任务一条 + 需求级一条，全部 pending，source 为判别联合', () => {
    const { sheet, reworkOnly } = buildSheet({
      sheetHistoryLength: 0,
      tasks: [
        { id: 't-aaaaaa', title: '任务一', acceptance: '单测绿' },
        { id: 't-bbbbbb', title: '任务二', acceptance: '' },
      ],
      evidence: ['npx vitest run 全绿'],
      generatedAt: 100,
      generatedBy: actor,
    })
    expect(reworkOnly).toBe(false)
    expect(sheet.version).toBe(1)
    expect(sheet.items.map(i => i.id)).toEqual(['v1-1', 'v1-2', 'v1-3'])
    expect(sheet.items.map(i => i.source)).toEqual([
      { kind: 'task', taskId: 't-aaaaaa' },
      { kind: 'task', taskId: 't-bbbbbb' },
      { kind: 'requirement' },
    ])
    // 迁移（REQ-d3e61a T-11）：验收项改为「业务标题 + 怎么验」——本断言验的是
    // "逐任务一条 + 需求级一条、顺序与来源正确"，语义不变，只是文案按新格式升级。
    expect(sheet.items.map(i => i.criterion)).toEqual(['【任务一】验收：单测绿', '【任务二】验收：交付完成', REQUIREMENT_LEVEL_CRITERION])
    expect(sheet.items.every(i => i.status === 'pending')).toBe(true)
    expect(sheet.items.every(i => i.evidence.length === 1 && i.evidence[0] === 'npx vitest run 全绿')).toBe(true)
  })

  it('续版：上一版有 failed → 带过「未过项 + 未裁决项」（passed 不再出现），版本递增且 reworkOnly=true', () => {
    const prev: SheetLike = {
      version: 1,
      items: [
        { id: 'v1-1', source: { kind: 'task', taskId: 't-aaaaaa' }, criterion: '单测绿', evidence: ['e'], status: 'passed' },
        { id: 'v1-2', source: { kind: 'task', taskId: 't-bbbbbb' }, criterion: '截图可见', evidence: ['e'], status: 'failed', opinion: '不清晰' },
        { id: 'v1-3', source: { kind: 'requirement' }, criterion: REQUIREMENT_LEVEL_CRITERION, evidence: ['e'], status: 'pending' },
      ],
      generatedAt: 1,
      generatedBy: actor,
    }
    const { sheet, reworkOnly } = buildSheet({
      sheetHistoryLength: 0, prevSheet: prev, tasks: [], evidence: ['e2'], generatedAt: 200, generatedBy: actor,
    })
    expect(reworkOnly).toBe(true)
    expect(sheet.version).toBe(2)
    // 2026-09-17 用户裁定（REQ-47939a D-7）：未裁决项必须带过 —— 旧实现只带 failed，
    // pending 项会从在册验收单里消失，导致"从未被裁决却可归档"。
    expect(sheet.items).toHaveLength(2)
    expect(sheet.items.map(i => i.source)).toEqual([
      { kind: 'task', taskId: 't-bbbbbb' }, // 未过项：必须复核
      { kind: 'requirement' },              // 未裁决项：不能被丢弃
    ])
    expect(sheet.items.every(i => i.status === 'pending')).toBe(true)
    expect(sheet.items.every(i => i.opinion === undefined)).toBe(true)
    expect(sheet.items.map(i => i.id)).toEqual(['v2-1', 'v2-2'])
    expect(sheet.reworkOnly).toBe(true)
  })

  it('续版守卫：上一版**没有** failed 项（仅 pending）→ 重新生成全新验收单，不进入续版', () => {
    // 这条守住 D-7 修复没有顺带改掉另一条既有语义：未产生过"未过项"时不叫返工轮次。
    const prev: SheetLike = {
      version: 1,
      items: [
        { id: 'v1-1', source: { kind: 'task', taskId: 't-aaaaaa' }, criterion: '单测绿', evidence: ['e'], status: 'pending' },
      ],
      generatedAt: 1,
      generatedBy: actor,
    }
    const { sheet, reworkOnly } = buildSheet({
      sheetHistoryLength: 0,
      prevSheet: prev,
      tasks: [{ id: 't-aaaaaa', title: '任务一', acceptance: '单测绿' }],
      evidence: ['e2'],
      generatedAt: 300,
      generatedBy: actor,
    })
    expect(reworkOnly).toBe(false)
    expect(sheet.items).toHaveLength(2) // 重新生成：每任务一条 + 需求级一条
    expect(sheet.items[1].source).toEqual({ kind: 'requirement' })
  })

  it('无上一版 & 有历史 → version = history + 1', () => {
    const { sheet } = buildSheet({ sheetHistoryLength: 2, tasks: [], evidence: ['e'], generatedAt: 1, generatedBy: actor })
    expect(sheet.version).toBe(3)
  })
})

describe('applyVerdicts：逐项裁决 + 返工规格', () => {
  const mkSheet = (): SheetLike => ({
    version: 1,
    items: [
      { id: 'v1-1', source: { kind: 'task', taskId: 't-aaaaaa' }, criterion: '单测绿', evidence: [], status: 'pending' },
      { id: 'v1-2', source: { kind: 'task', taskId: 't-bbbbbb' }, criterion: '截图可见', evidence: [], status: 'pending' },
      { id: 'v1-3', source: { kind: 'requirement' }, criterion: REQUIREMENT_LEVEL_CRITERION, evidence: [], status: 'pending' },
    ],
    generatedAt: 1,
    generatedBy: actor,
  })
  const tasks = [
    { id: 't-aaaaaa', title: '任务一', phase: 'implement', side: 'backend', scope: { apis: [], tables: [], files: ['a.ts'] } },
    { id: 't-bbbbbb', title: '任务二', phase: 'test', side: 'frontend', scope: { apis: [], tables: [], files: ['b.ts'] } },
  ]

  it('failed 无 opinion → 抛 invalid_input', () => {
    try {
      applyVerdicts(mkSheet(), [{ itemId: 'v1-1', status: 'failed' }], actor, 100, tasks)
      throw new Error('应当抛错')
    } catch (err) {
      expect(hasErrorCode(err, REQBOARD_ERROR_CODES.invalidInput)).toBe(true)
      expect((err as Error).message).toContain('必须写意见')
    }
  })

  it('验收项不存在 → 抛 invalid_input', () => {
    try {
      applyVerdicts(mkSheet(), [{ itemId: 'v9-9', status: 'passed' }], actor, 100, tasks)
      throw new Error('应当抛错')
    } catch (err) {
      expect(hasErrorCode(err, REQBOARD_ERROR_CODES.invalidInput)).toBe(true)
    }
  })

  it('有 failed → 生成返工规格（承接原任务 phase/side/scope + 意见）并计数', () => {
    const r = applyVerdicts(
      mkSheet(),
      [
        { itemId: 'v1-1', status: 'passed' },
        { itemId: 'v1-2', status: 'failed', opinion: '截图不清晰，请补高清图' },
      ],
      actor, 100, tasks,
    )
    expect(r.reworkTasks).toHaveLength(1)
    const spec = r.reworkTasks[0]
    expect(spec.title).toBe('返工：任务二')
    expect(spec.description).toContain('v1 项 v1-2')
    expect(spec.phase).toBe('test')
    expect(spec.side).toBe('frontend')
    expect(spec.scope).toEqual({ apis: [], tables: [], files: ['b.ts'] })
    expect(spec.implementation).toContain('截图不清晰，请补高清图')
    expect(spec.context).toContain('t-bbbbbb')
    expect(spec.opinion).toBe('截图不清晰，请补高清图')
    expect(r.pending).toBe(1)
    expect(r.passed).toBe(1)
    expect(r.failed).toBe(1)
  })

  it('需求级 failed → context 标注需求级', () => {
    const r = applyVerdicts(mkSheet(), [{ itemId: 'v1-3', status: 'failed', opinion: '范围蔓延' }], actor, 100, tasks)
    expect(r.reworkTasks[0].title).toBe('返工：' + REQUIREMENT_LEVEL_CRITERION.slice(0, 60))
    expect(r.reworkTasks[0].context).toContain('需求级验收项')
  })

  it('isAllPassed：有 pending/failed → false；全过 → true', () => {
    const s = mkSheet()
    expect(isAllPassed(s)).toBe(false)
    applyVerdicts(s, s.items.map(i => ({ itemId: i.id, status: 'passed' as const })), actor, 100, tasks)
    expect(isAllPassed(s)).toBe(true)
  })
})

describe('T-U1~T-U4：不可验收项与「全部已裁决」放行判据（REQ-308b9a FR-9）', () => {
  const actor2 = { kind: 'human', sessionId: 'w-abcdef12' } as const
  const tasks2 = [{ id: 't-aaaaaa', title: '任务一', phase: 'implement', side: 'backend' }]

  function mkSheet2(): SheetLike {
    return {
      version: 1,
      items: [
        { id: 'v1-1', source: { kind: 'task', taskId: 't-aaaaaa' }, criterion: '单测绿', evidence: ['e'], status: 'pending' },
        { id: 'v1-2', source: { kind: 'task', taskId: 't-aaaaaa' }, criterion: '截图可见', evidence: ['e'], status: 'pending' },
      ],
      generatedAt: 1,
      generatedBy: actor2,
    }
  }

  it('T-U1: applyVerdicts 对 not_verifiable 缺原因抛 invalid_input（AC-9.2）', () => {
    const s = mkSheet2()
    try {
      applyVerdicts(s, [{ itemId: 'v1-1', status: 'not_verifiable' }], actor2, 100, tasks2)
      throw new Error('应当抛错')
    } catch (err) {
      expect(hasErrorCode(err, REQBOARD_ERROR_CODES.invalidInput)).toBe(true)
    }
  })

  it('T-U2: applyVerdicts 对 failed 缺意见抛 invalid_input', () => {
    const s = mkSheet2()
    try {
      applyVerdicts(s, [{ itemId: 'v1-1', status: 'failed' }], actor2, 100, tasks2)
      throw new Error('应当抛错')
    } catch (err) {
      expect(hasErrorCode(err, REQBOARD_ERROR_CODES.invalidInput)).toBe(true)
    }
  })

  it('T-U3: passed + not_verifiable（无 pending）→ isFullyDecided=true，且不生成返工（AC-9.3/AC-8.5）', () => {
    const s = mkSheet2()
    const r = applyVerdicts(s, [
      { itemId: 'v1-1', status: 'passed' },
      { itemId: 'v1-2', status: 'not_verifiable', opinion: '本机无该运行环境' },
    ], actor2, 100, tasks2)
    expect(r.notVerifiable).toBe(1)
    expect(r.pending).toBe(0)
    expect(isFullyDecided(s)).toBe(true)
    expect(r.reworkTasks.length).toBe(0)
  })

  it('T-U4: 仍有 pending → isFullyDecided=false（AC-9.5）', () => {
    const s = mkSheet2()
    applyVerdicts(s, [{ itemId: 'v1-1', status: 'passed' }], actor2, 100, tasks2)
    expect(isFullyDecided(s)).toBe(false)
  })
})
