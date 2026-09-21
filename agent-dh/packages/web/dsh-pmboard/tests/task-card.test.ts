/**
 * 任务卡三要素校验单测（REQ-d3e61a T-10 / serve TC-007）
 * 判据来源：需求附录 A（旧写法被拦 / 新写法通过 / 人工可读性判据）。
 */
import { describe, expect, it } from 'vitest'
import { parseDocument, checkTaskCardTriad, triadFields, looksTechnical, TRIAD } from '../src/application/internal/content-gates.js'
import { resolveStagePrompt } from '../src/domain/prompt/index.js'

const doc = (...lines: string[]) => lines.join('\n')

/** 需求附录 A.2 的新写法（应通过）。 */
const GOOD_CARD = doc(
  '---',
  'task_id: t-abc123',
  'title: 盯盘噪音治理：让反复触发的规则收敛成一条修规则待办',
  'requirement_refs: [FR-6]',
  '---',
  '',
  '# 盯盘噪音治理',
  '',
  '## 1. 业务三要素',
  '',
  '**在做什么**',
  '盯盘噪音治理：让"反复触发"的规则自动收敛成一条「修规则」待办。',
  '',
  '**解决什么问题**',
  '同一批规则连续 4-5 天、日均 5-7 次触发，同类重复占多数，真实的买卖信号被淹没。',
  '',
  '**得到什么结果**',
  '该规则自动进入抑噪：不再逐条推送，一天最多打扰一次；同时生成一条说明该怎么改的待办。',
  '',
  '## 2. 验收标准',
  '```',
  'pytest tests/application/test_self_heal.py',
  '```',
)

/** 附录 A.1 的旧写法（应被拦）。 */
const BAD_CARD = doc(
  '---',
  'task_id: t-bad001',
  'title: 判据 metric 化',
  '---',
  '',
  '# 判据 metric 化',
  '',
  '## 1. 业务三要素',
  '',
  '**在做什么**',
  '把判据改成 metric 化。',
  '',
  '## 2. 实施方案',
  '改 conditions.py。',
)

describe('分片真的注入了吗（端到端，不只是单元）', () => {
  const dump = (stage: string, difficulty: string, category: string) =>
    JSON.stringify(resolveStagePrompt({ stage, difficulty, category } as any))

  it('implementing/light/feature 真注入任务卡契约', () => {
    const s = dump('implementing', 'light', 'feature')
    expect(s).toContain('任务卡必须说人话')
    expect(s).toContain('解决什么问题')
    expect(s).toContain('得到什么结果')
  })

  it('implementing/heavy 也注入（覆盖 7）', () => {
    const s = dump('implementing', 'heavy', 'feature')
    expect(s).toContain('覆盖 7')
  })

  it('不越界：brainstorming 档不含实施档契约', () => {
    expect(dump('brainstorming', 'light', 'feature')).not.toContain('任务卡必须说人话')
  })
})

describe('looksTechnical（建议级判据）', () => {
  it('命中已知坏卡标题', () => {
    expect(looksTechnical('判据 metric 化')).toBe(true)
    expect(looksTechnical('新增四张表与两表加列')).toBe(true)
  })
  it('纯英文标题视为工程语', () => {
    expect(looksTechnical('refactor noise policy pipeline')).toBe(true)
  })
  it('业务标题不算工程名词堆叠', () => {
    expect(looksTechnical('盯盘噪音治理：让反复触发的规则收敛成一条待办')).toBe(false)
    expect(looksTechnical('拆分门禁：条款没落卡就拦下')).toBe(false)
  })
})

describe('triadFields', () => {
  it('区分「字段缺失」与「字段在但为空」', () => {
    const f = triadFields(parseDocument(BAD_CARD))
    expect(f['在做什么']).toContain('metric')
    expect(f['解决什么问题']).toBeUndefined()
    expect(f['得到什么结果']).toBeUndefined()
  })
  it('新写法三要素都能取到正文', () => {
    const f = triadFields(parseDocument(GOOD_CARD))
    for (const name of TRIAD) expect((f[name] ?? '').length).toBeGreaterThan(0)
  })
})

describe('checkTaskCardTriad（TC-007）', () => {
  it('TC-007 旧卡（title=判据 metric 化，缺两要素）→ 被拦 + 给出标题建议', () => {
    const r = checkTaskCardTriad(parseDocument(BAD_CARD))
    expect(r.missing).toContain('缺字段：解决什么问题')
    expect(r.missing).toContain('缺字段：得到什么结果')
    expect(r.warnings.some(w => w.includes('工程名词堆叠'))).toBe(true)
  })

  it('新卡（业务三要素齐全）→ 无 missing、无 warnings', () => {
    const r = checkTaskCardTriad(parseDocument(GOOD_CARD))
    expect(r.missing).toEqual([])
    expect(r.warnings).toEqual([])
  })

  it('字段在但为空 → 报"字段为空"而非"缺字段"', () => {
    const md = doc(
      '**在做什么**',
      '**解决什么问题**',
      '',
      '**得到什么结果**',
      '规则不再反复打扰。',
    )
    const r = checkTaskCardTriad(parseDocument(md))
    expect(r.missing).toContain('字段为空：在做什么')
    expect(r.missing).not.toContain('缺字段：在做什么')
  })

  it('代码块里的三要素字样不算（围栏陷阱在任务卡场景的回归）', () => {
    const md = doc(
      '## 示例（下面这段是代码块里的反例）',
      '```',
      '**在做什么**',
      '**解决什么问题**',
      '**得到什么结果**',
      '```',
    )
    const r = checkTaskCardTriad(parseDocument(md))
    expect(r.missing).toContain('缺字段：在做什么')
  })
})
