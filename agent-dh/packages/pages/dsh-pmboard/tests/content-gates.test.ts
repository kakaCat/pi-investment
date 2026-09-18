/**
 * 内容校验闸门单测（REQ-d3e61a T-2 / serve TC-001..TC-006）
 *
 * 覆盖：解析器（front-matter / 标题 / 表格）、条款覆盖、编号串联、验收四件套、E2E。
 * 重点回归：**代码围栏内的井号与竖线不得被当成结构**（否则门禁会乱拦）。
 */
import { describe, expect, it } from 'vitest'
import {
  parseDocument,
  markCodeFences,
  isRootId,
  extractClauseDefinitions,
  extractServes,
  extractServesFrom,
  collectIds,
  checkClauseCoverage,
  checkNumberChain,
  checkAcceptanceKit,
  checkE2ECoverage,
} from '../src/application/internal/content-gates.js'

const doc = (...lines: string[]) => lines.join('\n')

const REQ_MD = doc(
  '---',
  'req_id: REQ-test',
  'category: feature',
  '---',
  '',
  '# 需求',
  '',
  '## 6. 功能点',
  '',
  '**FR-1 覆盖门禁**：拆分时逐条核对，漏条款即拦。',
  '- AC1：构造"需求有、卡上没有" → 被拒。',
  '',
  '**FR-7 指标条件类型**：新增指标/板块/事件条件。',
  '',
  '## 10. 测试策略',
  '',
  '| 层级 | 用例数 | 覆盖 |',
  '|------|--------|------|',
  '| 单元 | 8 | 纯函数边界 |',
  '| E2E | 2 | 完整链路 |',
)

describe('parseDocument', () => {
  it('解析 front-matter / 标题 / 表格', () => {
    const d = parseDocument(REQ_MD)
    expect(d.frontmatter.req_id).toBe('REQ-test')
    expect(d.frontmatter.category).toBe('feature')
    expect(d.headings.map(h => h.text)).toContain('6. 功能点')
    expect(d.tables).toHaveLength(1)
    expect(d.tables[0].header).toEqual(['层级', '用例数', '覆盖'])
    expect(d.tables[0].rows).toHaveLength(2)
  })

  it('**代码围栏内的井号与竖线不是结构**（陷阱回归）', () => {
    const md = doc(
      '# 真标题',
      '',
      '```',
      '# 假标题（在代码块里）',
      '| 假 | 表 |',
      '|----|----|',
      '| a  | b  |',
      '```',
      '',
      '## 真二级标题',
    )
    const d = parseDocument(md)
    expect(d.headings.map(h => h.text)).toEqual(['真标题', '真二级标题'])
    expect(d.tables).toHaveLength(0)

    const fenced = markCodeFences(md.split('\n'))
    expect(fenced[2]).toBe(true)
    expect(fenced[7]).toBe(true)
    expect(fenced[0]).toBe(false)
  })

  it('无 front-matter 时不吞正文', () => {
    const d = parseDocument(doc('# 标题', '正文 FR-1'))
    expect(Object.keys(d.frontmatter)).toHaveLength(0)
    expect(d.bodyLines).toContain('正文 FR-1')
  })
})

describe('isRootId', () => {
  it('按立项类型前缀判定，且不与下游前缀混', () => {
    expect(isRootId('FR-1')).toBe(true)
    expect(isRootId('BUG-3')).toBe(true)
    expect(isRootId('CH-4')).toBe(true)
    expect(isRootId('T-1')).toBe(false)
    expect(isRootId('D-ARCH-1')).toBe(false)
    expect(isRootId('FE-2')).toBe(false)
    expect(isRootId('TC-007')).toBe(false)
  })
})

describe('collectIds', () => {
  it('收集根编号与下游编号，忽略非编号文本', () => {
    expect(collectIds('`serves: FR-12, D-ARCH-2, TC-007`'))
      .toEqual(['FR-12', 'D-ARCH-2', 'TC-007'])
    expect(collectIds('没有任何编号')).toEqual([])
    expect(collectIds('FE-2 是前端编号，FE 不是根前缀')).toEqual(['FE-2'])
  })
})

describe('extractClauseDefinitions', () => {
  it('只取定义位（**FR-n**），不误抓泛指引用', () => {
    const md = doc(
      '**FR-1 覆盖门禁**：拆分时核对。',
      '**FR-7 指标条件类型**：新增条件。',
      '见 FR-10「对应哪条」的落点。',   // 泛指引用，不应计入
    )
    expect(extractClauseDefinitions(parseDocument(md))).toEqual(['FR-1', 'FR-7'])
  })
})

describe('extractServes', () => {
  it('提取并按前缀+数字自然排序', () => {
    expect(extractServes('## D-ARCH-1 三级门禁架构 `serves: FR-12, FR-13`'))
      .toEqual(['FR-12', 'FR-13'])
    expect(extractServes('没有标注的章节')).toEqual([])
  })

  it('extractServesFrom 汇总三个来源：标题 serves + 表格 serves 列 + front-matter', () => {
    const md = doc(
      '---',
      'requirement_refs: [FR-9]',
      '---',
      '## D-ARCH-1 三级门禁 `serves: FR-12`',
      '',
      '| 本项编号 | serves | 名称 | 状态 |',
      '|---------|--------|------|------|',
      '| T-1 | FR-1, FR-4 | 覆盖门禁 | done |',
      '| T-2 | FR-12 | 文档校验 | done |',
    )
    expect(extractServesFrom(parseDocument(md))).toEqual(['FR-1', 'FR-4', 'FR-9', 'FR-12'])
  })

  it('无任何 serves 来源 → 空数组（不假装有）', () => {
    expect(extractServesFrom(parseDocument(doc('# 标题', '正文')))).toEqual([])
  })
})

describe('checkClauseCoverage (TC-001 / TC-002)', () => {
  it('TC-001 有条款无引用 → gaps 列出缺失编号', () => {
    const roots = extractClauseDefinitions(parseDocument(REQ_MD))
    expect(roots).toEqual(['FR-1', 'FR-7'])
    expect(checkClauseCoverage(roots, ['FR-1']).gaps).toEqual(['FR-7'])
  })

  it('TC-002 显式标"本轮不做" → 不算缺口（拦的是无记录，不是少做）', () => {
    const roots = ['FR-1', 'FR-7']
    expect(checkClauseCoverage(roots, ['FR-1'], { skipped: ['FR-7'] }).gaps).toEqual([])
  })

  it('全覆盖 → 无缺口；根编号去重排序', () => {
    expect(checkClauseCoverage(['FR-10', 'FR-2'], ['FR-2', 'FR-10']).gaps).toEqual([])
    expect(checkClauseCoverage(['FR-10', 'FR-2'], []).gaps).toEqual(['FR-2', 'FR-10'])
  })
})

describe('checkNumberChain (TC-003 / TC-004)', () => {
  it('TC-003 serves 指向不存在 → 悬空', () => {
    const r = checkNumberChain([
      { id: 'FR-1', serves: [] },
      { id: 'T-1', serves: ['FR-1'] },
      { id: 'T-2', serves: ['FR-99'] },
    ])
    expect(r.dangling).toEqual(['T-2→FR-99'])
  })

  it('TC-004 根编号无人指向 → 孤儿', () => {
    const r = checkNumberChain([
      { id: 'FR-1', serves: [] },
      { id: 'FR-7', serves: [] },
      { id: 'T-1', serves: ['FR-1'] },
    ])
    expect(r.orphans).toEqual(['FR-7'])
    expect(r.dangling).toEqual([])
  })

  it('链路完整 → 既不悬空也无孤儿', () => {
    const r = checkNumberChain([
      { id: 'FR-4', serves: [] },
      { id: 'T-1', serves: ['FR-4'] },
      { id: 'D-DATA-1', serves: ['FR-4', 'T-1'] },
      { id: 'TC-007', serves: ['FR-4'] },
    ])
    expect(r).toEqual({ dangling: [], orphans: [] })
  })
})

describe('checkAcceptanceKit (TC-005)', () => {
  it('TC-005 缺"怎么验" → 计入 missing 并指出行键', () => {
    const md = doc(
      '| 验什么 | 对应编号 | 怎么验 | 预期 |',
      '|--------|---------|--------|------|',
      '| 拆分漏条款被拦 | FR-1 | `pytest x` | 3 passed |',
      '| 设计缺映射被拒 | FR-5 |  | 409 |',
    )
    const r = checkAcceptanceKit(parseDocument(md))
    expect(r.missing).toContain('FR-5：缺「怎么验」')
    expect(r.missing).not.toContain('FR-1：缺「怎么验」')
  })

  it('表头缺列 → 报缺列', () => {
    const md = doc(
      '| 验什么 | 怎么验 |',
      '|--------|--------|',
      '| A | `pytest` |',
    )
    const r = checkAcceptanceKit(parseDocument(md))
    expect(r.missing).toContain('表头缺列：对应编号')
    expect(r.missing).toContain('表头缺列：预期')
  })

  it('找不到验收表 → 整表缺失', () => {
    const r = checkAcceptanceKit(parseDocument(doc('# 验收', '没有表')))
    expect(r.missing).toHaveLength(1)
    expect(r.missing[0]).toContain('找不到验收四件套表')
  })

  it('四件套齐全 → 无缺失', () => {
    const md = doc(
      '| 验什么 | 对应编号 | 怎么验 | 预期 |',
      '|--------|---------|--------|------|',
      '| 拆分漏条款被拦 | FR-1 | `pytest x` | 3 passed |',
    )
    expect(checkAcceptanceKit(parseDocument(md)).missing).toEqual([])
  })
})

describe('checkE2ECoverage (TC-006)', () => {
  it('TC-006 有 E2E 行 → true', () => {
    expect(checkE2ECoverage(parseDocument(REQ_MD))).toEqual({ hasE2E: true })
  })

  it('只有单元/集成 → false', () => {
    const md = doc(
      '| 层级 | 用例数 |',
      '|------|--------|',
      '| 单元 | 8 |',
      '| 集成 | 4 |',
    )
    expect(checkE2ECoverage(parseDocument(md))).toEqual({ hasE2E: false })
  })

  it('无测试策略表 → false（不假装有）', () => {
    expect(checkE2ECoverage(parseDocument(doc('# 需求')))).toEqual({ hasE2E: false })
  })
})
