// serves: FR-2
/**
 * requirementDocPath 单测（REQ-260922012924-2e29 FR-2 / TC-2）——docBasePath 消费契约。
 *
 * 契约（design/interfaces.md）：docLinks.requirement 优先 → docBasePath 拼接（<REQ> 替换、
 * 无占位符追加 id 子目录、尾斜杠归一）→ 缺省 docs/requirements/<REQ>/；缺省分支与改造前
 * 逐字节一致（兼容老记录）。
 *
 * @module dsh-pmboard/tests/requirement-doc-path
 */
import { describe, it, expect } from 'vitest'
import { requirementDocPath } from '../src/application/internal/node-input-package.js'
import { req } from './application/harness.js'

describe('requirementDocPath · docBasePath 消费（FR-2）', () => {
  it('无需求记录 → 空串', () => {
    expect(requirementDocPath(undefined)).toBe('')
  })

  it('缺省（无 docBasePath/docLinks）→ docs/requirements/<id>/requirement.md（与改造前逐字节一致）', () => {
    const r = req({ id: 'REQ-TEST01', title: 't', category: 'feature', status: 'design' })
    expect(requirementDocPath(r)).toBe('docs/requirements/REQ-TEST01/requirement.md')
  })

  it('docBasePath 含 <REQ> 占位符 → 全部替换为需求 id（含自定义形状）', () => {
    const r = req({ id: 'REQ-TEST01', title: 't', category: 'feature', status: 'design', docBasePath: 'docs/guides/<REQ>-guide/' })
    expect(requirementDocPath(r)).toBe('docs/guides/REQ-TEST01-guide/requirement.md')
  })

  it('docBasePath 无占位符 → 追加 id 子目录防碰撞（尾斜杠有无都归一）', () => {
    const withSlash = req({ id: 'REQ-TEST01', title: 't', category: 'feature', status: 'design', docBasePath: 'docs/rfcs/' })
    expect(requirementDocPath(withSlash)).toBe('docs/rfcs/REQ-TEST01/requirement.md')
    const noSlash = req({ id: 'REQ-TEST01', title: 't', category: 'feature', status: 'design', docBasePath: 'docs/rfcs' })
    expect(requirementDocPath(noSlash)).toBe('docs/rfcs/REQ-TEST01/requirement.md')
  })

  it('默认 docs/requirements/<REQ>/ 显式传入 → 与缺省输出一致', () => {
    const r = req({ id: 'REQ-TEST01', title: 't', category: 'feature', status: 'design', docBasePath: 'docs/requirements/<REQ>/' })
    expect(requirementDocPath(r)).toBe('docs/requirements/REQ-TEST01/requirement.md')
  })

  it('docLinks.requirement 优先级最高（docBasePath 在场也不生效）', () => {
    const r = req({
      id: 'REQ-TEST01', title: 't', category: 'feature', status: 'design',
      docBasePath: 'docs/rfcs/',
      docLinks: { requirement: 'docs/custom/explicit.md' },
    })
    expect(requirementDocPath(r)).toBe('docs/custom/explicit.md')
  })
})
