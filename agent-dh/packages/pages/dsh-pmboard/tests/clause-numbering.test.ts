/**
 * 编号门禁单测（REQ-640a55 t-92e0b3 / FR-3、FR-4）
 *
 * 这两处判据长期"永不触发"，属静默失效，故本文件同时锁住两侧：
 *   - 能查出：跳号必须报出缺号；同一编号定义两次必须报次数；
 *   - 不误报：连号、多前缀各自连续、不可解析 id 一律放行。
 *
 * 修复前实测：跳号正则把 \\d+ 写成字面 d（re.exec('FR-1') === null）；
 * 判重拿的是已被 Set 去重的清单（计数恒 ≤1）。所以不仅要测判据，还要测"喂哪一份输入"。
 */
import { describe, expect, it } from 'vitest'
import {
  checkClauseSequence,
  checkClauseDuplicates,
  extractClauseDefinitions,
  extractClauseDefinitionOccurrences,
  parseDocument,
} from '../src/application/internal/content-gates.js'
import { checkRequirementDocFormatGate } from '../src/application/internal/content-gate-wiring.js'

const HEAD = ['---', 'req_id: REQ-t', '---', '# 需求', '', '## 6. 功能点', '']
const bodyOf = (...clauses: string[]) => [...HEAD, ...clauses].join('\n')
const docOf = (...clauses: string[]) => parseDocument(bodyOf(...clauses))

describe('checkClauseSequence：跳号必须查得出（FR-3）', () => {
  it('FR-1 与 FR-3 之间缺 FR-2', () => {
    expect(checkClauseSequence(['FR-1', 'FR-3'])).toEqual(['FR-2'])
  })

  it('连号 → 无缺口', () => {
    expect(checkClauseSequence(['FR-1', 'FR-2', 'FR-3'])).toEqual([])
  })

  it('多跳号逐个报：FR-1 与 FR-5 → FR-2/FR-3/FR-4', () => {
    expect(checkClauseSequence(['FR-1', 'FR-5'])).toEqual(['FR-2', 'FR-3', 'FR-4'])
  })

  it('多前缀各自独立连续 → 不误报', () => {
    expect(checkClauseSequence(['FR-1', 'NFR-1', 'NFR-2'])).toEqual([])
  })

  it('不可解析的 id 跳过 → 不误报', () => {
    expect(checkClauseSequence(['FR-1', 'foo', 'fr-2', '1-3'])).toEqual([])
  })

  it('其他前缀不与 FR 混算 → 不误报', () => {
    expect(checkClauseSequence(['FR-1', 'X-9'])).toEqual([])
  })
})

describe('判重必须吃不去重的清单（FR-4）', () => {
  it('同一编号定义两次 → 报出现 2 次', () => {
    const d = docOf('**FR-1 甲**：第一条。', '', '**FR-2 乙**：第二条。', '', '**FR-1 甲（重写了一遍）**：又是这条。')
    expect(extractClauseDefinitionOccurrences(d)).toEqual(['FR-1', 'FR-2', 'FR-1'])
    expect(checkClauseDuplicates(extractClauseDefinitionOccurrences(d))).toEqual(['FR-1（出现2次）'])
  })

  it('每个编号只定义一次 → 不报', () => {
    const d = docOf('**FR-1 甲**：第一条。', '', '**FR-2 乙**：第二条。')
    expect(checkClauseDuplicates(extractClauseDefinitionOccurrences(d))).toEqual([])
  })

  it('回归锁：喂去重后的清单永远报不出（这正是修复前的死法）', () => {
    const d = docOf('**FR-1 甲**：第一条。', '', '**FR-1 甲**：又一遍。')
    expect(extractClauseDefinitions(d)).toEqual(['FR-1'])
    expect(checkClauseDuplicates(extractClauseDefinitions(d))).toEqual([])
  })
})

describe('定义位两种写法都要认（标题式 / 加粗式）', () => {
  it('### FR-1: 标题式定义也计入出现次数', () => {
    const d = parseDocument([
      '---', 'req_id: REQ-t', '---', '# 需求', '',
      '## 6. 功能点', '', '### FR-1: 甲', '',
      '## 7. 下一节', '', '### FR-1: 甲（重复）',
    ].join('\n'))
    expect(extractClauseDefinitionOccurrences(d)).toEqual(['FR-1', 'FR-1'])
    expect(checkClauseDuplicates(extractClauseDefinitionOccurrences(d))).toEqual(['FR-1（出现2次）'])
  })

  it('标题式与加粗式混用 → 都算定义位（不因写法不同而漏计）', () => {
    const d = docOf('### FR-3: 丙', '', '**FR-1 甲**：x。')
    expect(extractClauseDefinitionOccurrences(d)).toEqual(['FR-3', 'FR-1'])
  })
})

describe('提交门禁端到端（requirement 格式门）', () => {
  const fakeDocs = (body: string) => ({ exists: () => true, read: async () => body }) as any
  const live = { id: 'REQ-t', artifacts: [{ stage: 'brainstorming', kind: 'requirement', path: 'x' }] } as any

  it('跳号文档 → 被拒且 gaps 给出缺失编号', async () => {
    const f = await checkRequirementDocFormatGate(fakeDocs(bodyOf('**FR-1 甲**：x。', '', '**FR-3 丙**：z。')), live)
    expect(f?.code).toBe('requirement_clause_sequence_gap')
    expect(f?.gaps).toEqual(['FR-2'])
  })

  it('重复编号文档 → 被拒', async () => {
    const f = await checkRequirementDocFormatGate(fakeDocs(bodyOf('**FR-1 甲**：x。', '', '**FR-1 甲（重复）**：又一遍。')), live)
    expect(f?.code).toBe('requirement_clause_duplicates')
    expect(f?.gaps).toEqual(['FR-1（出现2次）'])
  })

  it('连号且不重复 → 放行', async () => {
    const f = await checkRequirementDocFormatGate(fakeDocs(bodyOf('**FR-1 甲**：x。', '', '**FR-2 乙**：y。')), live)
    expect(f).toBeUndefined()
  })

  it('存量需求（无产物）→ 不拦', async () => {
    const legacy = { id: 'REQ-t', artifacts: [] } as any
    const f = await checkRequirementDocFormatGate(fakeDocs(bodyOf('**FR-1 甲**：x。', '', '**FR-3 丙**：z。')), legacy)
    expect(f).toBeUndefined()
  })
})
