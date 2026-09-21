/**
 * 设计文档策略单测（REQ-2d1c74 T-1 · serves FR-1）
 *
 * 验收口径：feature 缺 use-cases.md 报缺；sides=frontend 只要求 frontend.md；
 * 有效豁免使缺失消失；空理由/未知键豁免不生效（数据模型设计 §2）。
 * 策略解析 designDocPolicyFrom 与有效清单 effectiveDesignDocs 同测。
 */
import { describe, expect, it } from 'vitest'
import {
  CATEGORY_DELTAS,
  designDocPolicyFrom,
  effectiveDesignDocs,
  missingCategoryDocs,
} from '../src/application/internal/category-doc-sets.js'

const FEATURE_ROOT = '# 需求\n\n## 边界\n\n## 产品定义\n\n## 用户与角色\n\n## 功能点\n'
const FEATURE_REQUIRED = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']
const BUG_ROOT = '# 缺陷\n\n## 边界\n\n## 复现步骤\n\n## 根因\n\n## 回归\n'

describe('feature 文档集扩展（FR-1：五份必交 + 端侧条件必交）', () => {
  it('feature DELTA 含 use-cases.md 必交与 frontend/backend 条件必交', () => {
    const feature = CATEGORY_DELTAS.find(d => d.category === 'feature')
    expect(feature?.requiredDesignDocs).toEqual(FEATURE_REQUIRED)
    expect(feature?.conditionalDesignDocs).toEqual([
      { name: 'frontend.md', side: 'frontend' },
      { name: 'backend.md', side: 'backend' },
    ])
  })

  it('缺 use-cases.md → 缺失清单点名', () => {
    const missing = missingCategoryDocs({
      category: 'feature', rootExists: true, rootText: FEATURE_ROOT,
      designNames: ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md'],
    })
    expect(missing.join(' ')).toContain('design/use-cases.md 未交')
  })

  it('五份齐交（无 sides 声明）→ 无缺失，条件必交不冒出来', () => {
    expect(missingCategoryDocs({
      category: 'feature', rootExists: true, rootText: FEATURE_ROOT, designNames: FEATURE_REQUIRED,
    })).toEqual([])
  })
})

describe('端侧条件必交（sides 命中才要求）', () => {
  it('sides=frontend → 只要求 frontend.md，不要求 backend.md', () => {
    const missing = missingCategoryDocs({
      category: 'feature', rootExists: true, rootText: FEATURE_ROOT,
      designNames: FEATURE_REQUIRED, sides: ['frontend'],
    })
    expect(missing.join(' ')).toContain('design/frontend.md 未交')
    expect(missing.join(' ')).not.toContain('backend.md')
  })

  it('sides=frontend,backend → 两份都要求；交齐后无缺失', () => {
    const base = { category: 'feature', rootExists: true, rootText: FEATURE_ROOT, sides: ['frontend', 'backend'] } as const
    const missing = missingCategoryDocs({ ...base, designNames: FEATURE_REQUIRED })
    expect(missing.join(' ')).toContain('design/frontend.md 未交')
    expect(missing.join(' ')).toContain('design/backend.md 未交')
    expect(missingCategoryDocs({ ...base, designNames: [...FEATURE_REQUIRED, 'frontend.md', 'backend.md'] })).toEqual([])
  })

  it('effectiveDesignDocs 标记条件来源；无 sides 时条件必交不出现', () => {
    expect(effectiveDesignDocs('feature').map(d => d.name)).toEqual(FEATURE_REQUIRED)
    expect(effectiveDesignDocs('feature', ['frontend'])).toContainEqual({ name: 'frontend.md', conditional: 'frontend' })
    expect(effectiveDesignDocs('feature', ['backend'])).toContainEqual({ name: 'backend.md', conditional: 'backend' })
  })
})

describe('designDocPolicyFrom（front-matter 解析）', () => {
  it('解析 sides 与 design_exempt；忽略非法 side 与畸形条目', () => {
    const policy = designDocPolicyFrom({
      sides: 'frontend, backend , nonsense',
      design_exempt: 'use-cases.md=纯内部工具无用户场景; frontend.md=不改前端; 畸形条目; =空键',
    })
    expect(policy.sides).toEqual(['frontend', 'backend'])
    expect(policy.exempt).toEqual({
      'use-cases.md': '纯内部工具无用户场景',
      'frontend.md': '不改前端',
    })
  })

  it('空 front-matter → 空策略', () => {
    expect(designDocPolicyFrom({})).toEqual({ sides: [], exempt: {} })
  })
})

describe('豁免有效性（未知键/空理由 = 豁免无效）', () => {
  it('有效豁免 → 缺失消失', () => {
    expect(missingCategoryDocs({
      category: 'feature', rootExists: true, rootText: FEATURE_ROOT,
      designNames: ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md'],
      exempt: { 'use-cases.md': '纯内部工具无用户场景' },
    })).toEqual([])
  })

  it('条件必交也可豁免（sides=frontend + 豁免 frontend.md）', () => {
    expect(missingCategoryDocs({
      category: 'feature', rootExists: true, rootText: FEATURE_ROOT,
      designNames: FEATURE_REQUIRED, sides: ['frontend'],
      exempt: { 'frontend.md': '纯后端改动' },
    })).toEqual([])
  })

  it('空理由豁免不生效 → 仍报缺并注明豁免无效', () => {
    const missing = missingCategoryDocs({
      category: 'feature', rootExists: true, rootText: FEATURE_ROOT,
      designNames: ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md'],
      exempt: { 'use-cases.md': '' },
    })
    expect(missing.join(' ')).toContain('design/use-cases.md 未交（豁免无效：理由为空）')
  })

  it('未知键豁免不生效 → 缺失清单注明未知键', () => {
    const missing = missingCategoryDocs({
      category: 'feature', rootExists: true, rootText: FEATURE_ROOT,
      designNames: FEATURE_REQUIRED,
      exempt: { 'use-case.md': '拼错的键' },
    })
    expect(missing.join(' ')).toContain('design_exempt 含未知键「use-case.md」')
  })

  it('对未触发的条件必交键豁免 = 无害空操作（不注明、不拦截）', () => {
    expect(missingCategoryDocs({
      category: 'feature', rootExists: true, rootText: FEATURE_ROOT,
      designNames: FEATURE_REQUIRED,
      exempt: { 'backend.md': '不改后端' },
    })).toEqual([])
  })

  it('其他类型不受影响：bug 无设计文档要求，豁免键全部未知', () => {
    const missing = missingCategoryDocs({
      category: 'bug', rootExists: true, rootText: BUG_ROOT,
      designNames: [], exempt: { 'use-cases.md': 'x' },
    })
    expect(missing.join(' ')).toContain('未知键')
  })
})
