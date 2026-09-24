/**
 * artifact-labels 唯一事实源单测（REQ-260922182638-0777 / FR-1, FR-3, FR-4, FR-5）
 *
 * 验收口径（design/test-cases.md T-1）：
 *   TC-001 KIND_LABELS 覆盖全部 ArtifactKind（含 notes/task_output）+ 3 种扩展种类（ui/proposal/retro），逐条断言中文名（防漂移）；
 *   TC-002 未知 kind → 「产物（mystery_kind）」；空串 → 不 throw；
 *   TC-003 DOC_FILE_LABELS 全表逐条命中（含 design/ 前缀段边界后缀匹配）；
 *         未知文件名 → 「设计文档（foo.md）」；
 *   TC-004 taskCardLabel：有 title →「任务卡 · 名称」；无 title →「任务卡（t-xxx）」；
 *   TC-005 防漂移护栏：effectiveDesignDocs(各类型) 产出的全部规范文件名 ∈ DOC_FILE_LABELS 键集
 *         ——新增规范文件名未配中文名即红。
 */
import { describe, expect, it } from 'vitest'
import {
  KIND_LABELS,
  KIND_ICONS,
  DOC_FILE_LABELS,
  artifactKindLabel,
  docFileLabel,
  taskCardLabel,
} from '../src/shared/artifact-labels.js'
import { ALL_ARTIFACT_KINDS } from '../src/shared/protocol.js'
import { CATEGORY_DELTAS, effectiveDesignDocs } from '../src/application/internal/category-doc-sets.js'

describe('TC-001 · KIND_LABELS 全表逐条断言（ArtifactKind 全量 + 3 种扩展）', () => {
  it('ArtifactKind 中文名与设计终稿（I-3）逐字一致（notes/task_output 为枚举内扩展）', () => {
    expect(KIND_LABELS['requirement']).toBe('需求文档')
    expect(KIND_LABELS['design']).toBe('设计文档')
    expect(KIND_LABELS['plan']).toBe('拆分计划（旧版）')
    expect(KIND_LABELS['decomposition']).toBe('拆分计划')
    expect(KIND_LABELS['task_detail']).toBe('任务卡')
    expect(KIND_LABELS['verification']).toBe('验收材料')
    expect(KIND_LABELS['archive']).toBe('归档材料')
    expect(KIND_LABELS['notes']).toBe('其他')
    expect(KIND_LABELS['task_output']).toBe('任务产物')
  })
  it('3 种文档区扩展种类中文名与设计终稿逐字一致', () => {
    expect(KIND_LABELS['ui']).toBe('UI 文档')
    expect(KIND_LABELS['proposal']).toBe('设计文档')
    expect(KIND_LABELS['retro']).toBe('复盘')
  })
  it('防漂移：全部 ArtifactKind 枚举值都已配中文名（新增 kind 未配即红）', () => {
    for (const kind of ALL_ARTIFACT_KINDS) {
      expect(KIND_LABELS[kind], `ArtifactKind "${kind}" 未在 KIND_LABELS 配中文名`).toBeDefined()
    }
  })
  it('KIND_ICONS 与 KIND_LABELS 键集一致（图标归属集中一处）', () => {
    for (const kind of Object.keys(KIND_LABELS)) {
      expect(KIND_ICONS[kind], `KIND_ICONS 缺 "${kind}" 的图标`).toBeDefined()
    }
  })
})

describe('TC-002 · artifactKindLabel 未知值兜底', () => {
  it('未知 kind → 「产物（mystery_kind）」（中文引导 + 原文附注，不裸显英文）', () => {
    expect(artifactKindLabel('mystery_kind')).toBe('产物（mystery_kind）')
  })
  it('空串 → 不 throw，返回「产物」', () => {
    expect(() => artifactKindLabel('')).not.toThrow()
    expect(artifactKindLabel('')).toBe('产物')
  })
  it('命中 kind → 中文名（调用方不再需要 ?? kind 兜底）', () => {
    expect(artifactKindLabel('requirement')).toBe('需求文档')
    expect(artifactKindLabel('task_detail')).toBe('任务卡')
  })
})

describe('TC-003 · DOC_FILE_LABELS 全表命中 + 未知文件名兜底', () => {
  it('10 个规范文件名逐条命中（含 design/ 前缀）', () => {
    expect(docFileLabel('requirement.md')).toBe('需求文档')
    expect(docFileLabel('decomposition.md')).toBe('拆分计划')
    expect(docFileLabel('design/architecture.md')).toBe('架构文档')
    expect(docFileLabel('design/data-model.md')).toBe('数据模型')
    expect(docFileLabel('design/interfaces.md')).toBe('接口文档')
    expect(docFileLabel('design/test-cases.md')).toBe('测试用例')
    expect(docFileLabel('design/migration.md')).toBe('迁移方案')
    expect(docFileLabel('design/frontend.md')).toBe('前端设计')
    expect(docFileLabel('design/backend.md')).toBe('后端设计')
    expect(docFileLabel('design/use-cases.md')).toBe('用例文档')
  })
  it('段边界后缀匹配：完整需求目录路径同样命中', () => {
    expect(docFileLabel('docs/requirements/REQ-xxx/design/architecture.md')).toBe('架构文档')
    expect(docFileLabel('./docs/requirements/REQ-xxx/requirement.md')).toBe('需求文档')
  })
  it('非段边界不误命中（my-architecture.md ≠ architecture.md）', () => {
    expect(docFileLabel('docs/requirements/REQ-xxx/design/my-architecture.md', 'design')).toBe('设计文档（my-architecture.md）')
  })
  it('未知文件名 → 「设计文档（foo.md）」（kind 中文 + 原文附注）', () => {
    expect(docFileLabel('docs/requirements/REQ-xxx/design/foo.md', 'design')).toBe('设计文档（foo.md）')
  })
  it('未知文件名且未传 kind → 「文档（foo.md）」；空路径 → 不 throw', () => {
    expect(docFileLabel('foo.md')).toBe('文档（foo.md）')
    expect(() => docFileLabel('')).not.toThrow()
    expect(() => docFileLabel('', undefined)).not.toThrow()
  })
})

describe('TC-004 · taskCardLabel 两分支', () => {
  it('有 title → 「任务卡 · <任务名称>」', () => {
    expect(taskCardLabel('docs/requirements/REQ-xxx/tasks/t-85eedd.md', '新增 artifact-labels 映射模块'))
      .toBe('任务卡 · 新增 artifact-labels 映射模块')
  })
  it('无 title → 「任务卡（t-xxx）」（basename 去 .md）', () => {
    expect(taskCardLabel('docs/requirements/REQ-xxx/tasks/t-85eedd.md')).toBe('任务卡（t-85eedd）')
    expect(taskCardLabel('docs/requirements/REQ-xxx/tasks/t-85eedd.md', '')).toBe('任务卡（t-85eedd）')
    expect(taskCardLabel('docs/requirements/REQ-xxx/tasks/t-85eedd.md', '   ')).toBe('任务卡（t-85eedd）')
  })
  it('空路径 → 不 throw，返回「任务卡」', () => {
    expect(() => taskCardLabel('')).not.toThrow()
    expect(taskCardLabel('')).toBe('任务卡')
  })
})

describe('TC-005 · 防漂移护栏：规范文件名必须全部配中文名', () => {
  it('effectiveDesignDocs(各类型) 产出的全部规范文件名 ∈ DOC_FILE_LABELS 键集', () => {
    // 全端侧声明取并集，确保条件必交（frontend.md/backend.md）也被覆盖
    const ALL_SIDES = ['frontend', 'backend', 'fullstack', 'doc']
    for (const delta of CATEGORY_DELTAS) {
      for (const { name } of effectiveDesignDocs(delta.category, ALL_SIDES)) {
        const key = `design/${name}`
        expect(
          DOC_FILE_LABELS[key],
          `${delta.category} 的规范设计文档 ${key} 未在 DOC_FILE_LABELS 配中文名（防漂移护栏）`,
        ).toBeDefined()
      }
    }
  })
  it('DOC_FILE_LABELS 表行数与设计终稿一致（10 行，新增须同步评审）', () => {
    expect(Object.keys(DOC_FILE_LABELS)).toHaveLength(10)
  })
})
