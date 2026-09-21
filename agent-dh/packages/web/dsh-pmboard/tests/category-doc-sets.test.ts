/**
 * 分类文档集单测（REQ-d3e61a T-13 / serve FR-15）
 *
 * 验收口径：六类样例——少交必填文档 → 被拒并指出缺失文档名；**bug 缺"复现步骤" → 拒绝**。
 * 底线：类型只减少文档**数量**，不取消**追溯**。
 * （BASE + DELTA 的两层性质由 tests/base-delta.test.ts 覆盖——那是 T-14。）
 */
import { describe, expect, it } from 'vitest'
import { CATEGORY_DELTAS, deltaFor, missingCategoryDocs, requiredRootSectionsFor } from '../src/application/internal/category-doc-sets.js'

// REQ-2d1c74 FR-1：feature 必交扩为五份（补 use-cases.md）；条件必交 frontend/backend 由 design-doc-policy.test.ts 覆盖
const FEATURE_DESIGN = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']
const BASE_TEXT = '## 边界\n'

describe('deltaFor / requiredRootSectionsFor（六类齐全，未知类型不拦）', () => {
  it('六类都有 DELTA', () => {
    expect(CATEGORY_DELTAS.map(s => s.category).sort()).toEqual(['bug', 'chore', 'doc', 'feature', 'refactor', 'spike'])
  })
  it('未知类型 / undefined → 不拦', () => {
    expect(deltaFor(undefined)).toBeUndefined()
    expect(deltaFor('nonsense')).toBeUndefined()
    expect(requiredRootSectionsFor('nonsense')).toEqual([])
  })
  it('**底线**：每个类型都要求至少一条必填节（类型只减数量，不取消追溯）', () => {
    for (const d of CATEGORY_DELTAS) expect(requiredRootSectionsFor(d.category).length).toBeGreaterThan(0)
  })
})

describe('missingCategoryDocs', () => {
  it('根文档不存在 → 空（还没到可判阶段，不制造噪声）', () => {
    expect(missingCategoryDocs({ category: 'feature', rootExists: false, rootText: '', designNames: [] })).toEqual([])
  })

  it('feature 齐活 → 无缺失', () => {
    const root = '# 需求\n\n' + BASE_TEXT + '\n## 产品定义\n\n## 用户与角色\n\n## 功能点\n'
    expect(missingCategoryDocs({ category: 'feature', rootExists: true, rootText: root, designNames: FEATURE_DESIGN })).toEqual([])
  })

  it('feature 缺节 → 点出节名；少交设计文档 → 点出文件名', () => {
    const root = '# 需求\n\n' + BASE_TEXT + '\n## 产品定义\n'
    const missing = missingCategoryDocs({ category: 'feature', rootExists: true, rootText: root, designNames: ['architecture.md'] })
    expect(missing.join(' ')).toContain('用户与角色')
    expect(missing.join(' ')).toContain('design/data-model.md')
    expect(missing.join(' ')).toContain('design/test-cases.md')
  })

  it('**bug 缺「复现步骤」→ 拒绝**（验收要点）', () => {
    const root = '# 缺陷\n\n' + BASE_TEXT + '\n## 现象\n\n## 根因\n\n## 回归\n'
    expect(missingCategoryDocs({ category: 'bug', rootExists: true, rootText: root, designNames: [] }).join(' ')).toContain('复现步骤')
  })

  it('bug 齐活 → 无缺失（裁的是**数量**：不要 PRD 那套用户角色，仍要追溯）', () => {
    const root = '# 缺陷\n\n' + BASE_TEXT + '\n## 复现步骤\n\n## 根因\n\n## 回归\n'
    expect(missingCategoryDocs({ category: 'bug', rootExists: true, rootText: root, designNames: [] })).toEqual([])
    expect(requiredRootSectionsFor('bug')).not.toContain('用户')
  })

  it('refactor 要求"行为不变式"', () => {
    const root = '# 重构\n\n' + BASE_TEXT + '\n## 现状\n\n## 目标结构\n'
    expect(missingCategoryDocs({ category: 'refactor', rootExists: true, rootText: root, designNames: ['architecture.md', 'migration.md'] }).join(' ')).toContain('行为不变式')
  })

  it('chore 最简：BASE + 完成判据', () => {
    expect(requiredRootSectionsFor('chore').filter(s => s === '完成判据')).toEqual(['完成判据'])
    const missing = missingCategoryDocs({ category: 'chore', rootExists: true, rootText: '# 杂务\n\n## 边界\n', designNames: [] })
    expect(missing).toContain('requirement.md 缺必填节「完成判据」')
  })
})
