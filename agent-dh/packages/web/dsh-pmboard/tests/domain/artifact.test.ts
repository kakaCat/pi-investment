/**
 * L1 领域单测 · 产物规约（REQ-47939a t2 / INV-7）。
 * serves: FR-3（REQ-81aabd design 种类与展示边界）。
 *
 * 覆盖：kindForRelPath 分类、节点必备产物表、人工确认门（4 道）、归档文档规则。
 * 锚点为表驱动断言——规则表改动时测试跟着走，不靠手写用例覆盖。
 */
import { describe, it, expect } from 'vitest'
import {
  ALL_ARTIFACT_KINDS,
  STAGE_ARTIFACT_REQUIREMENTS,
  ARTIFACT_CONFIRM_GATES,
  ARCHIVE_DOC_RULES,
  kindForRelPath,
} from '../../src/domain/artifact/ArtifactSpec.js'
import * as protocol from '../../src/shared/protocol.js'

describe('kindForRelPath：从需求目录相对路径推断产物种类', () => {
  it('必备产物按文件名归类', () => {
    expect(kindForRelPath('requirement.md')).toBe('requirement')
    expect(kindForRelPath('plan.md')).toBe('plan')
    expect(kindForRelPath('decomposition.md')).toBe('decomposition')
    expect(kindForRelPath('verification.md')).toBe('verification')
    expect(kindForRelPath('archive.md')).toBe('archive')
    expect(kindForRelPath('tasks/t-abc123.md')).toBe('task_detail')
  })

  it('design/*.md 归「设计文档」（REQ-81aabd FR-1），非 .md 仍是 notes', () => {
    expect(kindForRelPath('design/architecture.md')).toBe('design')
    expect(kindForRelPath('design/test-cases.md')).toBe('design')
    expect(kindForRelPath('design/token-ui.html')).toBe('notes')
    expect(kindForRelPath('design/sub/x.md')).toBe('design')
  })

  it('未命中 → notes（原型 html / 笔记等过程产物）', () => {
    expect(kindForRelPath('prototype.html')).toBe('notes')
    expect(kindForRelPath('lanes-prototype.html')).toBe('notes')
    expect(kindForRelPath('notes/x.txt')).toBe('notes')
  })

  it('tasks/ 下非 t-xxx.md 不误判为 task_detail', () => {
    expect(kindForRelPath('tasks/readme.md')).toBe('notes')
  })
})

describe('产物规则表', () => {
  it('每节点必备产物与六道节点一致', () => {
    expect(STAGE_ARTIFACT_REQUIREMENTS).toEqual({
      brainstorming: ['requirement'],
      // 2026-09-21 用户裁定：设计阶段必备产物 = 设计文档（拆分计划归拆分阶段）
      design: ['design'],
      decomposing: ['decomposition'],
      implementing: ['task_detail'],
      accepting: ['verification'],
      archived: ['archive'],
    })
  })

  it('design 是设计阶段必备产物与 G2 闸门产物（2026-09-21 用户裁定：设计只写设计文档）', () => {
    expect(ALL_ARTIFACT_KINDS).toContain('design')
    expect(STAGE_ARTIFACT_REQUIREMENTS.design).toContain('design')
    expect(Object.values(ARTIFACT_CONFIRM_GATES)).toContain('design')
    // 旧的 plan 门（design>decomposing 锚定 plan）已退役：plan 不再是任何闸门的锚
    expect(Object.values(ARTIFACT_CONFIRM_GATES)).not.toContain('plan')
  })

  it('恰好 4 道人工确认门，且 kind 是合法产物种类', () => {
    expect(Object.keys(ARTIFACT_CONFIRM_GATES)).toHaveLength(4)
    for (const kind of Object.values(ARTIFACT_CONFIRM_GATES)) {
      expect(ALL_ARTIFACT_KINDS).toContain(kind)
    }
  })

  it('ARCHIVE_DOC_RULES 每个分类都给出必填文档与合并去向', () => {
    for (const [category, rule] of Object.entries(ARCHIVE_DOC_RULES)) {
      expect(rule.requiredDocs.length, category).toBeGreaterThan(0)
      expect(rule.mergeTargets.length, category).toBeGreaterThan(0)
    }
    expect(ARCHIVE_DOC_RULES.bug.requiredDocs).toContain('retro')
    expect(ARCHIVE_DOC_RULES.bug.mergeTargets).toContain('agent-dh/docs/guides/')
    expect(ARCHIVE_DOC_RULES.spike.requiredDocs).toEqual(['requirement', 'retro'])
    expect(ARCHIVE_DOC_RULES.feature.requireManual).toBe(true)
    expect(ARCHIVE_DOC_RULES.bug.requireManual).toBe(false)
  })
})

describe('t2 再导出：shared/protocol 与 domain 同源', () => {
  it('产物规则经 protocol 再导出后引用同一实现', () => {
    expect(protocol.STAGE_ARTIFACT_REQUIREMENTS).toEqual(STAGE_ARTIFACT_REQUIREMENTS)
    expect(protocol.ARTIFACT_CONFIRM_GATES).toEqual(ARTIFACT_CONFIRM_GATES)
    expect(protocol.ARCHIVE_DOC_RULES).toBe(ARCHIVE_DOC_RULES)
  })
})
