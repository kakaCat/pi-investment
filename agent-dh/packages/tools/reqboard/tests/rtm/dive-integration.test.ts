/**
 * FR-8 · 节点输入包装配 + 压缩模式 + Dive 决策（design/interfaces.md §3.1/§3.2）。
 */
import { describe, expect, it } from 'vitest'
import { RTMGenerator } from '../../src/rtm/generator.js'
import {
  assembleNodeInput,
  estimateTokens,
  generateNextAction,
  nextStageOf,
  previousStageOf,
} from '../../src/dive/node-input.js'
import { makeDiveDecision } from '../../src/dive/decision.js'
import { DESIGN_MD, fiveTasks, makeFixture, REQUIREMENT_MD, TEST_CASES_MD } from './fixture.js'

/** 全量生成 7 个 RTM（docs/requirements/<REQ>/rtm-*.yml）。 */
function full() {
  const f = makeFixture()
  f.writeDoc('requirement.md', REQUIREMENT_MD)
  f.writeDoc('design/architecture.md', DESIGN_MD)
  f.writeDoc('design/test-cases.md', TEST_CASES_MD)
  f.setTasks(fiveTasks())
  const gen = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger })
  gen.generateLifecycle(f.reqId)
  gen.generateBrainstorming(f.reqId)
  gen.generateDesign(f.reqId)
  gen.generateDecomposing(f.reqId)
  gen.generateImplementing(f.reqId)
  gen.generateAccepting(f.reqId)
  return { f, gen }
}

describe('assembleNodeInput (FR-8 节点输入包)', () => {
  it('full 模式注入完整 RTM 块与 next_action', () => {
    const { f } = full()
    const input = assembleNodeInput(f.root, 'design', f.reqId, 'full')
    expect(input.stage).toBe('design')
    expect(input.requirement_id).toBe(f.reqId)
    expect(input.mode).toBe('full')
    expect(input.previous_stage).toBe('brainstorming')
    expect((input.coverage as any).design.rate).toBe(67)
    expect(input.outputs).toBeDefined()
    expect(input.traceability).toBeDefined()
    expect(input.next_action).toContain('1 个 FR 缺少设计')
  })

  it('compressed 模式只留 rate/uncovered，且显著更省 token', () => {
    const { f } = full()
    const fullInput = assembleNodeInput(f.root, 'design', f.reqId, 'full')
    const comp = assembleNodeInput(f.root, 'design', f.reqId, 'compressed')
    expect(comp.mode).toBe('compressed')
    expect((comp.coverage as any).design).toEqual({ rate: 67, uncovered: ['FR-3'] })
    expect(comp.traceability).toBeUndefined()
    expect(estimateTokens(comp)).toBeLessThan(estimateTokens(fullInput))
  })

  it('implementing compressed 给出进度与进行中任务', () => {
    const f = makeFixture()
    f.writeDoc('requirement.md', REQUIREMENT_MD)
    const tasks = fiveTasks()
    tasks[0] = { ...tasks[0]!, status: 'in_progress' }
    f.setTasks(tasks)
    const gen = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger })
    gen.generateImplementing(f.reqId)
    const comp = assembleNodeInput(f.root, 'implementing', f.reqId, 'compressed')
    expect((comp.status as any).progress).toBe('0/5 done, 1 in_progress')
    expect((comp.status as any).current_tasks).toHaveLength(1)
    expect(String((comp.status as any).current_tasks[0])).toContain('t-0001')
  })

  it('RTM 缺失不抛异常，next_action 如实说明', () => {
    const f = makeFixture()
    const input = assembleNodeInput(f.root, 'design', f.reqId, 'full')
    expect(input.coverage).toBeUndefined()
    expect(input.next_action).toContain('RTM 数据缺失')
  })

  it('helper：阶段前后继', () => {
    expect(previousStageOf('design')).toBe('brainstorming')
    expect(previousStageOf('draft')).toBeUndefined()
    expect(nextStageOf('design')).toBe('decomposing')
    expect(nextStageOf('done')).toBeUndefined()
    expect(generateNextAction('design', undefined)).toContain('缺失')
  })
})

describe('makeDiveDecision (FR-8 Dive 决策)', () => {
  it('design 覆盖度不足 → 不推进并点名缺哪条 FR', () => {
    const { f } = full()
    const d = makeDiveDecision(f.root, 'design', f.reqId)
    expect(d.can_proceed).toBe(false)
    expect(d.coverage?.rate).toBe(67)
    expect(d.blockers).toEqual(['FR-3'])
    expect(d.reason).toContain('FR')
  })

  it('design 覆盖度 100% → 可推进到 decomposing', () => {
    const { f, gen } = full()
    f.writeDoc('design/extra.md', '## 3 数据同步 serves: FR-3\n描述。\n')
    gen.generateDesign(f.reqId)
    const d = makeDiveDecision(f.root, 'design', f.reqId)
    expect(d.can_proceed).toBe(true)
    expect(d.next_stage).toBe('decomposing')
  })

  it('implementing 全完成 → 可推进到 accepting', () => {
    const f = makeFixture()
    f.writeDoc('requirement.md', REQUIREMENT_MD)
    f.setTasks(fiveTasks().map(t => ({ ...t, status: 'done' })))
    const gen = new RTMGenerator({ workspaceRoot: f.root, ledger: f.ledger })
    gen.generateImplementing(f.reqId)
    const d = makeDiveDecision(f.root, 'implementing', f.reqId)
    expect(d.can_proceed).toBe(true)
    expect(d.next_stage).toBe('accepting')
  })

  it('implementing 未完成 → 不推进且列出未完成任务', () => {
    const { f } = full()
    const d = makeDiveDecision(f.root, 'implementing', f.reqId)
    expect(d.can_proceed).toBe(false)
    expect(d.blockers?.length).toBe(5)
  })

  it('accepting 测试覆盖度 40% → 不推进（门禁 80%）', () => {
    const { f } = full()
    const d = makeDiveDecision(f.root, 'accepting', f.reqId)
    expect(d.can_proceed).toBe(false)
    expect(d.coverage?.rate).toBe(40)
  })

  it('RTM 缺失 → 不猜，can_proceed=false', () => {
    const f = makeFixture()
    const d = makeDiveDecision(f.root, 'design', f.reqId)
    expect(d.can_proceed).toBe(false)
    expect(d.reason).toContain('RTM 数据缺失')
  })
})

describe('测试文档发现（FR-4 Level 3 / FR-5）', () => {
  it('tests/*.md 里的 covers: 标注计入测试覆盖度', () => {
    const { f, gen } = full()
    // 覆盖度初始 40%（2/5）
    f.writeDoc('tests/evidence.md', '# 测试证据\n\n## 用例\ncovers: t-0003, t-0004, t-0005\nvalidates: FR-3\n')
    const rtm = gen.generateAccepting(f.reqId)
    expect(rtm.coverage.testing.total_tasks).toBe(5)
    expect(rtm.coverage.testing.tested_tasks).toBe(5)
    expect(rtm.coverage.testing.rate).toBe(100)
  })
})
