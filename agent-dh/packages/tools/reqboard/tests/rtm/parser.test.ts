/**
 * t3 · 文档标注解析测试（FR-3 / FR-4）。
 */
import { describe, expect, it } from 'vitest'
import {
  extractFRTokens,
  extractTaskTokens,
  parseDecompositionServes,
  parseDesignSections,
  parseRequirementFRs,
  parseTestCovers,
} from '../../src/rtm/parser.js'

describe('parser / parseRequirementFRs', () => {
  it('从 **FR-N: 标题 提取（含行号）', () => {
    const frs = parseRequirementFRs('**FR-1: 文件结构\n**FR-2: 生成逻辑')
    expect(frs).toHaveLength(2)
    expect(frs[0]?.id).toBe('FR-1')
    expect(frs[0]?.title).toBe('文件结构')
    expect(frs[0]?.line).toBe(1)
    expect(frs[1]?.line).toBe(2)
  })

  it('从 ### FR-N: 标题 提取（本需求 requirement.md 的实际写法）', () => {
    const frs = parseRequirementFRs('### FR-1: RTM 文件结构设计\n正文\n### FR-2: RTM 生成逻辑')
    expect(frs.map(f => f.id)).toEqual(['FR-1', 'FR-2'])
    expect(frs[0]?.title).toBe('RTM 文件结构设计')
  })

  it('忽略代码围栏内的示例与正文中的引用', () => {
    const md = '参考 FR-1 与 FR-2 的说明\n\n\u0060\u0060\u0060\n**FR-9: 示例\n\u0060\u0060\u0060\n\n**FR-3: 真需求'
    const frs = parseRequirementFRs(md)
    expect(frs.map(f => f.id)).toEqual(['FR-3'])
  })

  it('重复 FR 只取首个，空文档返回空数组', () => {
    expect(parseRequirementFRs('')).toEqual([])
    expect(parseRequirementFRs('**FR-1: a\n**FR-1: b')).toHaveLength(1)
  })
})

describe('parser / parseDesignSections', () => {
  it('提取编号章节 + 标题同行的 serves 标注', () => {
    const sections = parseDesignSections([{ path: 'design/architecture.md', content: '# 标题\n\n## 1.1 文件结构 serves: FR-1, FR-2\n正文' }])
    expect(sections).toHaveLength(1)
    expect(sections[0]?.ref).toBe('design/architecture.md#1.1')
    expect(sections[0]?.serves).toEqual(['FR-1', 'FR-2'])
    expect(sections[0]?.title).toBe('文件结构')
  })

  it('支持紧随其后的独立 serves: 行', () => {
    const sections = parseDesignSections([{ path: 'design/data.md', content: '## 2.1 数据模型\nserves: FR-1\n\n## 2.2 存储\nserves: FR-2' }])
    expect(sections.map(s => s.serves)).toEqual([['FR-1'], ['FR-2']])
  })

  it('无编号标题用 slug 作 section，且忽略围栏内示例', () => {
    const md = '## 架构说明\nserves: FR-1\n\u0060\u0060\u0060\nserves: FR-9\n\u0060\u0060\u0060\n'
    const sections = parseDesignSections([{ path: 'design/arch.md', content: md }])
    expect(sections).toHaveLength(1)
    expect(sections[0]?.serves).toEqual(['FR-1'])
    expect(sections[0]?.ref).toBe('design/arch.md#架构说明')
  })

  it('空文件返回空数组', () => {
    expect(parseDesignSections([])).toEqual([])
    expect(parseDesignSections([{ path: 'design/x.md', content: '' }])).toEqual([])
  })
})

describe('parser / parseTestCovers', () => {
  it('提取 covers / validates，用例 id 取标题 TC-N', () => {
    const cases = parseTestCovers([{ path: 'design/test-cases.md', content: '## TC-1 文件结构测试\ncovers: t-0001\nvalidates: FR-1' }])
    expect(cases).toHaveLength(1)
    expect(cases[0]?.id).toBe('TC-1')
    expect(cases[0]?.covers).toEqual(['t-0001'])
    expect(cases[0]?.validates).toEqual(['FR-1'])
  })

  it('无 TC id 时按顺序编号；无 covers 的段不产生用例', () => {
    const cases = parseTestCovers([{
      path: 'verification.md',
      content: '## 端到端\ncovers: t-0001, t-0002\nvalidates: FR-1, FR-2\n\n## 说明\n纯文字',
    }])
    expect(cases).toHaveLength(1)
    expect(cases[0]?.id).toBe('TC-1')
    expect(cases[0]?.covers).toEqual(['t-0001', 't-0002'])
  })

  it('token 提取工具', () => {
    expect(extractFRTokens('serves FR-1, FR-2 与 FR-1')).toEqual(['FR-1', 'FR-2'])
    expect(extractTaskTokens('covers: t-abcdef, t-123456')).toEqual(['t-abcdef', 't-123456'])
  })
})

describe('parser / parseDecompositionServes', () => {
  it('解析 §1 根编号 ↔ 任务卡 对照表', () => {
    const md = '| 根编号 | 任务编号 | 任务标题 |\n| --- | --- | --- |\n| FR-1 | t-8c8edc | 类型定义 |\n| FR-1 | t-e57e00 | 文件 IO |\n| FR-2 | t-8c8edc | 类型定义 |'
    const map = parseDecompositionServes(md)
    expect(map['t-8c8edc']).toEqual(['FR-1', 'FR-2'])
    expect(map['t-e57e00']).toEqual(['FR-1'])
  })
})
