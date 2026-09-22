// serves: BUG-1
/**
 * REQUIREMENT_DIR_PATTERN 单测（REQ-260922133212-dd5b BUG-1）——归档目录约定兼容新旧 id 格式。
 *
 * 旧版六位 hex（REQ-f6307c）与 2026-09 起的时间戳格式（REQ-260922012924-2e29）都收；
 * 非法 id、目录层级错误、目录尾部多段一律拒。
 *
 * @module dsh-pmboard/tests/requirement-dir-pattern
 */
import { describe, it, expect } from 'vitest'
import { REQUIREMENT_DIR_PATTERN } from '../src/shared/protocol.js'

describe('REQUIREMENT_DIR_PATTERN · 新旧 id 格式兼容（BUG-1）', () => {
  it('旧版六位 hex id → 通过', () => {
    expect(REQUIREMENT_DIR_PATTERN.test('docs/requirements/REQ-f6307c')).toBe(true)
    expect(REQUIREMENT_DIR_PATTERN.test('agent-dh/docs/requirements/REQ-e3b6a0')).toBe(true)
  })

  it('新时间戳 id（YYMMDDHHmmss-xxxx = 12 位数字+4 位 hex）→ 通过（修复前必现 false）', () => {
    expect(REQUIREMENT_DIR_PATTERN.test('docs/requirements/REQ-260922012924-2e29')).toBe(true)
    expect(REQUIREMENT_DIR_PATTERN.test('docs/requirements/REQ-260922133212-dd5b')).toBe(true)
  })

  it('非法 id 形态 → 仍拒', () => {
    expect(REQUIREMENT_DIR_PATTERN.test('docs/requirements/REQ-XYZ')).toBe(false)
    expect(REQUIREMENT_DIR_PATTERN.test('docs/requirements/REQ-12345')).toBe(false)
    expect(REQUIREMENT_DIR_PATTERN.test('docs/requirements/REQ-260922012924')).toBe(false) // 缺 hex 段
    expect(REQUIREMENT_DIR_PATTERN.test('docs/requirements/REQ-260922012924-2e29ff')).toBe(false) // hex 超长
    expect(REQUIREMENT_DIR_PATTERN.test('docs/requirements/REQ-26092201292401-2e29')).toBe(false) // 时间戳超 12 位
    expect(REQUIREMENT_DIR_PATTERN.test('docs/requirements/REQ-2609220129-2e29')).toBe(false) // 时间戳不足 12 位
  })

  it('目录层级错误 / 尾部多段 → 仍拒', () => {
    expect(REQUIREMENT_DIR_PATTERN.test('docs/other/REQ-260922012924-2e29')).toBe(false)
    expect(REQUIREMENT_DIR_PATTERN.test('docs/requirements/REQ-260922012924-2e29/design')).toBe(false)
  })
})
