/**
 * 覆盖门禁单测（REQ-d3e61a T-3 / serve TC-009）
 *
 * 验收口径：构造"需求有、卡上没有"的拆分 → 被拒且 gaps 列出缺失编号；
 * 同例把该条款标「本轮不做」→ 通过（证明拦的是"无记录"，不是"少做"）。
 */
import { describe, expect, it } from 'vitest'
import { parseDocument, extractSkippedClauses, extractClauseDefinitions } from '../src/application/internal/content-gates.js'
import { assertClauseCoverageGate, requirementRefsOf } from '../src/application/internal/content-gate-wiring.js'

const doc = (...lines: string[]) => lines.join('\n')

const REQ_BODY = doc(
  '---',
  'req_id: REQ-t',
  '---',
  '# 需求',
  '',
  '## 6. 功能点',
  '',
  '**FR-1 覆盖门禁**：拆分时逐条核对。',
  '',
  '**FR-4 三段可追溯**：需求↔任务↔证据。',
  '',
  '**FR-7 指标条件类型**：新增指标/板块/事件条件。',
)

const REQ_BODY_SKIPPED = doc(
  '---', 'req_id: REQ-t', '---', '# 需求', '',
  '## 6. 功能点', '',
  '**FR-1 覆盖门禁**：拆分时逐条核对。', '',
  '**FR-4 三段可追溯**：需求↔任务↔证据。', '',
  '**FR-7 指标条件类型**：本轮不做（原因：依赖的行情源未就绪）。',
)

const fakeDocs = (files: Record<string, string>) => ({
  exists: (p: string) => Object.prototype.hasOwnProperty.call(files, p),
  read: async (p: string) => files[p] ?? '',
})

const reqWith = (artifacts: unknown[] | undefined) => ({ id: 'REQ-t', artifacts } as any)
const PATH = 'docs/requirements/REQ-t/requirement.md'
const live = reqWith([{ stage: 'brainstorming', kind: 'requirement', path: 'x' }])

describe('requirementRefsOf（两种写法都认，避免静默漏判）', () => {
  it('snake / camel / 缺失 / 非法值', () => {
    expect(requirementRefsOf({ requirement_refs: ['FR-1', 'FR-4'] })).toEqual(['FR-1', 'FR-4'])
    expect(requirementRefsOf({ requirementRefs: ['FR-2'] })).toEqual(['FR-2'])
    expect(requirementRefsOf({ key: 'T-1' })).toEqual([])
    expect(requirementRefsOf({ requirement_refs: ['FR-1', 3, null] })).toEqual(['FR-1'])
    expect(requirementRefsOf(null)).toEqual([])
  })
})

describe('extractSkippedClauses（显式裁剪）', () => {
  it('标了「本轮不做」的条款被识别；没标的不会', () => {
    const d = parseDocument(REQ_BODY_SKIPPED)
    expect(extractClauseDefinitions(d)).toEqual(['FR-1', 'FR-4', 'FR-7'])
    expect(extractSkippedClauses(d)).toEqual(['FR-7'])
  })
  it('无裁剪标记 → 空（不误判）', () => {
    expect(extractSkippedClauses(parseDocument(REQ_BODY))).toEqual([])
  })
})

describe('assertClauseCoverageGate（TC-009）', () => {
  it('TC-009 需求有 FR-7、卡上没有 → 被拒且 gaps 含 FR-7', async () => {
    const r = await assertClauseCoverageGate(
      fakeDocs({ [PATH]: REQ_BODY }),
      live,
      [{ key: 'T-1', requirement_refs: ['FR-1', 'FR-4'] }],
    )
    expect(r).toBeDefined()
    expect(r?.code).toBe('requirement_uncovered')
    expect(r?.gaps).toEqual(['FR-7'])
    expect(r?.message).toContain('FR-7')
  })

  it('同例把 FR-7 标「本轮不做」→ 通过（拦的是无记录，不是少做）', async () => {
    const r = await assertClauseCoverageGate(
      fakeDocs({ [PATH]: REQ_BODY_SKIPPED }),
      live,
      [{ key: 'T-1', requirement_refs: ['FR-1', 'FR-4'] }],
    )
    expect(r).toBeUndefined()
  })

  it('全部条款都被卡接收 → 通过', async () => {
    const r = await assertClauseCoverageGate(
      fakeDocs({ [PATH]: REQ_BODY }),
      live,
      [{ requirement_refs: ['FR-1', 'FR-4', 'FR-7'] }],
    )
    expect(r).toBeUndefined()
  })

  it('存量需求（artifacts 为空）→ 豁免，不拦', async () => {
    const r = await assertClauseCoverageGate(fakeDocs({ [PATH]: REQ_BODY }), reqWith(undefined), [])
    expect(r).toBeUndefined()
  })

  it('需求文档不存在 / 文档里没有编号条款 → 不拦（避免误拦）', async () => {
    expect(await assertClauseCoverageGate(fakeDocs({}), live, [])).toBeUndefined()
    expect(await assertClauseCoverageGate(fakeDocs({ [PATH]: doc('# 需求', '没有编号条款') }), live, [])).toBeUndefined()
  })

  it('camelCase 的 requirementRefs 同样被认（防写法不一致导致静默漏判）', async () => {
    const r = await assertClauseCoverageGate(
      fakeDocs({ [PATH]: REQ_BODY }),
      live,
      [{ requirementRefs: ['FR-1', 'FR-4', 'FR-7'] }],
    )
    expect(r).toBeUndefined()
  })

  it('覆盖可来自多张卡 / 多来源的并集（不是只看第一张）', async () => {
    const r = await assertClauseCoverageGate(
      fakeDocs({ [PATH]: REQ_BODY }),
      live,
      [{ requirement_refs: ['FR-1'] }, { requirementRefs: ['FR-4'] }, { requirement_refs: ['FR-7'] }],
    )
    expect(r).toBeUndefined()
  })

  it('gaps 是结构化编号清单（不是一句人话），便于 agent 精确修复', async () => {
    const r = await assertClauseCoverageGate(fakeDocs({ [PATH]: REQ_BODY }), live, [])
    expect(r?.gaps).toEqual(['FR-1', 'FR-4', 'FR-7'])
  })
})
