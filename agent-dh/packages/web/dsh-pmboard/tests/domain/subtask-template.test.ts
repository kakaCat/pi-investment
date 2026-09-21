/**
 * 子卡模板映射表测试（REQ-4842fe t1）——对应 design/test-cases.md §1。
 *
 * 口径：映射表是数据化契约（加一行即扩类型）；逃生舱口必须受控枚举、非空、去重。
 */
import { describe, it, expect } from 'vitest'
import {
  STAGE_KINDS,
  SUBTASK_TEMPLATES,
  DEFAULT_FALLBACK_STAGES,
  stagesForCardType,
  validateExplicitStages,
  buildSubtaskSpecs,
  stageLabel,
} from '../../src/domain/task/SubtaskTemplate.js'

describe('子卡映射表（FR-1）', () => {
  it('1.1 各类型映射正确（顺序即链序）', () => {
    expect(stagesForCardType('feature')).toEqual(['dev', 'integrate', 'review', 'test'])
    expect(stagesForCardType('refactor')).toEqual(['dev', 'integrate', 'review', 'test'])
    expect(stagesForCardType('bug')).toEqual(['repro', 'fix', 'review', 'regress'])
    expect(stagesForCardType('doc')).toEqual(['dev', 'review'])
    expect(stagesForCardType('chore')).toEqual(['dev', 'review'])
    expect(stagesForCardType('spike')).toEqual(['probe', 'review'])
    expect(stagesForCardType('research')).toEqual(['collect', 'analyze', 'review'])
    expect(stagesForCardType('data')).toEqual(['prepare', 'run', 'verify', 'review'])
    expect(stagesForCardType('ops')).toEqual(['change', 'dryrun', 'apply', 'verify', 'review'])
    expect(stagesForCardType('review-only')).toEqual(['review'])
  })

  it('1.1b review 必在测试段之前；无测试段的以 review 收尾', () => {
    for (const stages of Object.values(SUBTASK_TEMPLATES)) {
      const ri = stages.indexOf('review')
      expect(ri).toBeGreaterThanOrEqual(0)
      const ti = stages.findIndex(s => s === 'test' || s === 'regress')
      if (ti >= 0) expect(ri).toBeLessThan(ti) // 先复核、后测试（2026-09-20 用户裁定）
      else expect(stages[stages.length - 1]).toBe('review')
    }
  })

  it('1.2 未映射/未知类型回退 dev→review', () => {
    expect(stagesForCardType('unknown-type')).toEqual(['dev', 'review'])
    expect(stagesForCardType(undefined)).toEqual(DEFAULT_FALLBACK_STAGES)
    expect(stagesForCardType('')).toEqual(['dev', 'review'])
  })

  it('映射表只含受控 stageKind 且无重复', () => {
    const allowed = new Set<string>(STAGE_KINDS)
    for (const stages of Object.values(SUBTASK_TEMPLATES)) {
      for (const s of stages) expect(allowed.has(s)).toBe(true)
      expect(new Set(stages).size).toBe(stages.length)
    }
  })
})

describe('显式 stages 逃生舱口（FR-1b）', () => {
  it('1.3 合法声明：保留顺序、原样返回', () => {
    const r = validateExplicitStages(['collect', 'analyze', 'review'])
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.value).toEqual(['collect', 'analyze', 'review'])
  })

  it('1.4a 自由文本被拒', () => {
    const r = validateExplicitStages(['collect', '写代码'])
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toContain('写代码')
  })

  it('1.4b 空数组被拒', () => {
    const r = validateExplicitStages([])
    expect(r.ok).toBe(false)
  })

  it('1.4c 重复项被拒', () => {
    const r = validateExplicitStages(['dev', 'dev', 'review'])
    expect(r.ok).toBe(false)
  })

  it('1.4d 非法输入类型被拒（非数组）', () => {
    const r = validateExplicitStages('dev' as unknown as string[])
    expect(r.ok).toBe(false)
  })
})

describe('子卡规格生成（FR-1/FR-3 契约）', () => {
  it('链依赖：首卡无链内前置，其后每卡依赖前一张', () => {
    const specs = buildSubtaskSpecs(['dev', 'integrate', 'review', 'test'])
    expect(specs.map(s => s.chainIndex)).toEqual([0, 1, 2, 3])
    expect(specs.map(s => s.dependsOnIndex)).toEqual([null, 0, 1, 2])
    expect(specs.map(s => s.stageKind)).toEqual(['dev', 'integrate', 'review', 'test'])
  })

  it('每张子卡都有非空标题与可证伪验收模板', () => {
    for (const kind of STAGE_KINDS) {
      const [spec] = buildSubtaskSpecs([kind])
      expect(spec.title.length).toBeGreaterThan(0)
      expect(/命令|跑通|输出|结论|证据|校验|通过|全绿|落库|标注/.test(spec.acceptance)).toBe(true)
      expect(stageLabel(kind).length).toBeGreaterThan(0)
    }
  })

  it('空集合不产出子卡', () => {
    expect(buildSubtaskSpecs([])).toEqual([])
  })
})
