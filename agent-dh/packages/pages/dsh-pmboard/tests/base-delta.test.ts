/**
 * BASE + DELTA 两层结构单测（REQ-d3e61a T-14 / serve FR-15）
 *
 * 验收口径：**删掉 BASE 某个公共节 → 六类全部返回拒绝**。
 * 这条性质证明"共同骨架只定义一次"——六份副本做不到这一点（改一处不会同时影响六类）。
 * 另覆盖标记载体规则：逐条状态只存表格行，front-matter 只放文档级索引。
 */
import { describe, expect, it } from 'vitest'
import {
  COMMON_ROOT_SECTIONS, CATEGORY_DELTAS, CATEGORY_DELTAS as DELTAS,
  requiredRootSectionsFor, missingCategoryDocs, frontmatterStateViolations,
} from '../src/application/internal/category-doc-sets.js'

/** 造一份"BASE 齐 + 该类型 DELTA 齐"的根文档。 */
const completeRootFor = (category: string): string => {
  const heads = [...COMMON_ROOT_SECTIONS, ...(DELTAS.find(d => d.category === category)?.rootSectionsDelta ?? [])]
  return '# 文档\n\n' + heads.map(h => '## ' + h + '\n\n内容').join('\n\n') + '\n'
}
const designFor = (category: string): string[] => [...(DELTAS.find(d => d.category === category)?.requiredDesignDocs ?? [])]

describe('BASE 只定义一次（删一条 → 六类同时拒绝）', () => {
  it('先确认：BASE 齐 + DELTA 齐时，六类全部通过', () => {
    for (const d of CATEGORY_DELTAS) {
      expect(missingCategoryDocs({ category: d.category, rootExists: true, rootText: completeRootFor(d.category), designNames: designFor(d.category) })).toEqual([])
    }
  })

  it('**删掉 BASE 里任一条公共节 → 六类全部返回拒绝**（这正是"只定义一次"的可测性质）', () => {
    for (const dropped of COMMON_ROOT_SECTIONS) {
      for (const d of CATEGORY_DELTAS) {
        // 把该公共节从文档里删掉（其余都齐）
        const text = completeRootFor(d.category).split('## ' + dropped).join('## 被删节')
        const missing = missingCategoryDocs({ category: d.category, rootExists: true, rootText: text, designNames: designFor(d.category) })
        // 精确断言条目，而不是子串包含——"待答问题"含"问题"，子串判断会被误满足
        expect(missing).toContain('requirement.md 缺必填节「' + dropped + '」')
      }
    }
  })

  it('把 BASE 整体删空（base=[]）→ 谁也不因 BASE 被拒（反证：拒绝确实来自 BASE）', () => {
    for (const d of CATEGORY_DELTAS) {
      const text = completeRootFor(d.category).split('## ' + COMMON_ROOT_SECTIONS[0]).join('## 被删节')
      const missing = missingCategoryDocs({ category: d.category, rootExists: true, rootText: text, designNames: designFor(d.category), base: [] })
      expect(missing).not.toContain('requirement.md 缺必填节「' + COMMON_ROOT_SECTIONS[0] + '」')
    }
  })

  it('BASE 非空且不重复（骨架必须是共同的，不能塞类型专属节）', () => {
    expect(COMMON_ROOT_SECTIONS.length).toBeGreaterThan(0)
    expect(new Set(COMMON_ROOT_SECTIONS).size).toBe(COMMON_ROOT_SECTIONS.length)
    for (const d of CATEGORY_DELTAS) {
      for (const sec of COMMON_ROOT_SECTIONS) expect(d.rootSectionsDelta).not.toContain(sec)
    }
  })

  it('requiredRootSectionsFor = BASE + DELTA（顺序稳定、无重复）', () => {
    for (const d of CATEGORY_DELTAS) {
      const all = requiredRootSectionsFor(d.category)
      expect(all.slice(0, COMMON_ROOT_SECTIONS.length)).toEqual([...COMMON_ROOT_SECTIONS])
      expect(new Set(all).size).toBe(all.length)
    }
  })
})

describe('标记载体：逐条状态只存表格行，front-matter 只放文档级索引', () => {
  it('文档级键 → 不违规（req_id / title / status / owner / category / requirement_refs）', () => {
    expect(frontmatterStateViolations({
      req_id: 'REQ-1', title: 't', status: 'implementing', owner: 'w', category: 'feature',
      created: '2026-09-18', requirement_refs: '[FR-1]', coverage_status: 'complete',
    })).toEqual([])
  })

  it('**把逐条状态塞进 front-matter → 探测出来**（键里带编号）', () => {
    expect(frontmatterStateViolations({ req_id: 'REQ-1', FR1_status: 'done' })).toEqual(['FR1_status'])
    expect(frontmatterStateViolations({ 't-aaa111_evidence': 'x', 'BUG-3_state': 'fixed' })).toEqual(['t-aaa111_evidence', 'BUG-3_state'])
  })
})
