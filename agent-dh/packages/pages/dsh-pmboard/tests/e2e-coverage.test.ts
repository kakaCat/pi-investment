/**
 * E2E 缺口可见单测（REQ-d3e61a T-16 / serve FR-11）
 *
 * 验收口径：只交单元/集成时，验收单**必须有一项**显示「E2E 覆盖：无（缺口）」；
 * 补一条链路 e2e 后该项变「有」。核心是**可见**——靠人记得不是机制。
 */
import { describe, expect, it } from 'vitest'
import { e2eCoverageOf } from '../src/application/internal/content-gate-wiring.js'
import { buildSheet } from '../src/domain/workflow/AcceptanceSheetSpec.js'

const doc = (...lines: string[]) => lines.join('\n')

const fakeDocs = (files: Record<string, string>) => ({
  exists: (p: string) => Object.prototype.hasOwnProperty.call(files, p),
  read: async (p: string) => files[p] ?? '',
})

const live = { id: 'REQ-t', artifacts: [{ stage: 'brainstorming', kind: 'requirement', path: 'x' }] } as any
const PATH = 'docs/requirements/REQ-t/requirement.md'

const REQ_ONLY_UNIT = doc(
  '# 需求', '',
  '## 10. 测试策略', '',
  '| 层级 | 数量 | 说明 |',
  '|------|------|------|',
  '| 单元 | 8 | 纯函数边界 |',
  '| 集成 | 4 | 门禁接线 |',
)
const REQ_WITH_E2E = doc(
  '# 需求', '',
  '## 10. 测试策略', '',
  '| 层级 | 数量 | 说明 |',
  '|------|------|------|',
  '| 单元 | 8 | 纯函数边界 |',
  '| **E2E** | **2** | 两条完整业务链路 |',
)

describe('e2eCoverageOf（读需求文档的测试策略表）', () => {
  it('只有单元/集成 → false（缺口）', async () => {
    expect(await e2eCoverageOf(fakeDocs({ [PATH]: REQ_ONLY_UNIT }), live)).toBe(false)
  })
  it('含 E2E 行 → true', async () => {
    expect(await e2eCoverageOf(fakeDocs({ [PATH]: REQ_WITH_E2E }), live)).toBe(true)
  })
  it('需求文档不存在 → undefined（读数未知，不制造噪声）', async () => {
    expect(await e2eCoverageOf(fakeDocs({}), live)).toBeUndefined()
    expect(await e2eCoverageOf(fakeDocs({ [PATH]: '   ' }), live)).toBeUndefined()
  })
})

describe('验收单可见性：E2E 缺口必须成为一项', () => {
  const base = {
    sheetHistoryLength: 0,
    tasks: [{ id: 't-1', title: 'A', acceptance: 'npx vitest run x 通过' }],
    evidence: ['ev'],
    generatedAt: 1,
    generatedBy: { kind: 'agent', sessionId: 'w' },
  } as any

  it('e2eCoverage=false → 出现「无（缺口）」项，且是 pending', () => {
    const r = buildSheet({ ...base, e2eCoverage: false })
    const item = r.sheet.items.find(i => i.criterion.includes('E2E 覆盖'))
    expect(item).toBeDefined()
    expect(item?.criterion).toContain('无（缺口）')
    expect(item?.status).toBe('pending')
  })

  it('e2eCoverage=true → 出现「有」项（补了 e2e 后状态随之改变）', () => {
    const r = buildSheet({ ...base, e2eCoverage: true })
    const item = r.sheet.items.find(i => i.criterion.includes('E2E 覆盖'))
    expect(item?.criterion).toContain('**有**')
  })

  it('读数未知（未传）→ 不追加（不对没有测试策略的需求制造噪声）', () => {
    const r = buildSheet(base)
    expect(r.sheet.items.some(i => i.criterion.includes('E2E 覆盖'))).toBe(false)
  })

  it('端到端串联：只交单测的需求走完 e2eCoverageOf → 验收单带缺口项', async () => {
    const cov = await e2eCoverageOf(fakeDocs({ [PATH]: REQ_ONLY_UNIT }), live)
    const r = buildSheet({ ...base, ...(cov !== undefined ? { e2eCoverage: cov } : {}) })
    expect(r.sheet.items.map(i => i.criterion).join(' ')).toContain('E2E 覆盖')
    expect(r.sheet.items.map(i => i.criterion).join(' ')).toContain('无（缺口）')
  })
})
