/**
 * t4/t5 · 追溯映射构建 + 三层覆盖度统计 + 门禁校验（FR-4 / FR-5 / FR-9）。
 */
import { describe, expect, it } from 'vitest'
import {
  buildDesignToTasks,
  buildFRToDesign,
  buildFRToTasks,
  buildFRToTests,
  buildTaskToTests,
  buildTraceability,
  buildTraceabilityChain,
} from '../../src/rtm/traceability-builder.js'
import {
  calculateDesignCoverage,
  calculateImplementationCoverage,
  calculateTestingCoverage,
  rateOf,
} from '../../src/rtm/coverage-calculator.js'
import { RTMValidator, rtmValidator, thresholdFor } from '../../src/rtm/validator.js'
import type { DesignSection, FR, RTMTaskLike, TestCase } from '../../src/rtm/types.js'

const frs: FR[] = [
  { id: 'FR-1', title: 'a', source: 'requirement.md', line: 1 },
  { id: 'FR-2', title: 'b', source: 'requirement.md', line: 2 },
  { id: 'FR-3', title: 'c', source: 'requirement.md', line: 3 },
]
const sections: DesignSection[] = [
  { ref: 'design/arch.md#1.1', title: 's1', serves: ['FR-1'], file: 'design/arch.md', section: '1.1' },
  { ref: 'design/arch.md#1.2', title: 's2', serves: ['FR-2'], file: 'design/arch.md', section: '1.2' },
  { ref: 'design/data.md#2.1', title: 's3', serves: ['FR-1', 'FR-2'], file: 'design/data.md', section: '2.1' },
  { ref: 'design/data.md#2.2', title: 's4', serves: ['FR-3'], file: 'design/data.md', section: '2.2' },
]
const tasks: RTMTaskLike[] = [
  { id: 't-0001', serves: ['FR-1'], implements: 'design/arch.md#1.1' },
  { id: 't-0002', serves: ['FR-2'] },
  { id: 't-0003', serves: ['FR-3'] },
  { id: 't-0004', serves: [] },
  { id: 't-0005', serves: ['FR-1'] },
]
const testCases: TestCase[] = [
  { id: 'TC-1', title: 'x', covers: ['t-0001'], validates: ['FR-1'] },
  { id: 'TC-2', title: 'y', covers: ['t-0002', 't-0001'], validates: ['FR-2'] },
]

describe('traceability-builder', () => {
  it('FR → 设计', () => {
    const m = buildFRToDesign(frs, sections)
    expect(m['FR-1']).toEqual(['design/arch.md#1.1', 'design/data.md#2.1'])
    expect(m['FR-3']).toEqual(['design/data.md#2.2'])
  })

  it('设计 → 任务（serves 交集或显式 implements）', () => {
    const m = buildDesignToTasks(sections, tasks)
    expect(m['design/arch.md#1.1']).toEqual(['t-0001', 't-0005'])
    expect(m['design/data.md#2.1']).toEqual(['t-0001', 't-0002', 't-0005'])
    expect(m['design/data.md#2.2']).toEqual(['t-0003'])
  })

  it('任务 → 测试', () => {
    const m = buildTaskToTests(tasks, testCases)
    expect(m['t-0001']).toEqual(['TC-1', 'TC-2'])
    expect(m['t-0003']).toEqual([])
  })

  it('间接映射 FR → 任务 / FR → 测试，完整链路可查', () => {
    const trace = buildTraceability({ frs, sections, tasks, testCases })
    expect(trace.fr_to_tasks['FR-1']).toEqual(['t-0001', 't-0005', 't-0002'])
    expect(trace.fr_to_tests['FR-1']).toEqual(['TC-1', 'TC-2'])
    const chain = buildTraceabilityChain('FR-1', trace)
    expect(chain).toEqual({ fr: 'FR-1', designs: ['design/arch.md#1.1', 'design/data.md#2.1'], tasks: ['t-0001', 't-0005', 't-0002'], tests: ['TC-1', 'TC-2'] })
    expect(buildFRToTasks(trace.fr_to_design, trace.design_to_tasks, ['FR-1'])['FR-1']).toBeDefined()
    expect(buildFRToTests(trace.fr_to_tasks, trace.task_to_tests, ['FR-9'])['FR-9']).toEqual([])
  })
})

describe('coverage-calculator', () => {
  it('rateOf：分母 0 按 100 计', () => {
    expect(rateOf(0, 0)).toBe(100)
    expect(rateOf(2, 3)).toBe(67)
  })

  it('设计覆盖度：3 FR 覆盖 2 → 67%，uncovered=[FR-3]', () => {
    const cov = calculateDesignCoverage(frs, { 'FR-1': ['a'], 'FR-2': ['b'], 'FR-3': [] })
    expect(cov.rate).toBe(67)
    expect(cov.total_frs).toBe(3)
    expect(cov.covered_frs).toBe(2)
    expect(cov.uncovered).toEqual(['FR-3'])
  })

  it('实施覆盖度：4 章节覆盖 3 → 75%', () => {
    const m = buildDesignToTasks(sections, tasks)
    const cov = calculateImplementationCoverage(sections, m)
    expect(cov.rate).toBe(100)
    expect(cov.total_designs).toBe(4)
    const partial = calculateImplementationCoverage(sections, { 'design/arch.md#1.1': ['t-1'] })
    expect(partial.rate).toBe(25)
    expect(partial.uncovered).toEqual(['design/arch.md#1.2', 'design/data.md#2.1', 'design/data.md#2.2'])
  })

  it('测试覆盖度：5 任务覆盖 2 → 40%', () => {
    const cov = calculateTestingCoverage(tasks, buildTaskToTests(tasks, testCases))
    expect(cov.rate).toBe(40)
    expect(cov.total_tasks).toBe(5)
    expect(cov.tested_tasks).toBe(2)
    expect(cov.untested).toEqual(['t-0003', 't-0004', 't-0005'])
    expect(cov.uncovered).toEqual(['t-0003', 't-0004', 't-0005'])
  })

  it('全空集合视为 100% 且无缺口', () => {
    expect(calculateDesignCoverage([], {}).rate).toBe(100)
    expect(calculateImplementationCoverage([], {}).uncovered).toEqual([])
    expect(calculateTestingCoverage([], {}).rate).toBe(100)
  })
})

describe('validator', () => {
  it('设计覆盖度门禁 100%，不足时点名缺哪条', () => {
    const ok = rtmValidator.checkDesign({ total: 2, covered: 2, uncovered: [], rate: 100 })
    expect(ok.passed).toBe(true)
    expect(ok.threshold).toBe(100)
    const bad = rtmValidator.checkDesign({ total: 3, covered: 2, uncovered: ['FR-3'], rate: 67 })
    expect(bad.passed).toBe(false)
    expect(bad.message).toContain('FR-3')
  })

  it('验收门禁阈值 80%', () => {
    expect(rtmValidator.checkAcceptance({ total: 5, covered: 4, uncovered: [], rate: 80 }).passed).toBe(true)
    expect(rtmValidator.checkAcceptance({ total: 5, covered: 3, uncovered: ['t-4', 't-5'], rate: 60 }).passed).toBe(false)
    expect(thresholdFor('accepting')).toBe(80)
    expect(thresholdFor('design')).toBe(100)
    expect(thresholdFor('unknown')).toBe(100)
  })

  it('自定义阈值', () => {
    const v = new RTMValidator()
    expect(v.checkGate('x', { total: 1, covered: 1, uncovered: [], rate: 50 }, 50).passed).toBe(true)
  })
})
