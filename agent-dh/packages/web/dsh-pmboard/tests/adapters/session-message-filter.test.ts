/**
 * 会话消息过滤单测（REQ-47939a t9）——覆盖从 host/classifier.ts 与 host/session-sync.ts 迁入
 * adapters/SessionMessageFilter.ts 的三个**仍在运行时被调用**的函数。
 *
 * 为什么补这组：t9 删「M2 自动分类」死代码时，同步删除了 tests/reqboard.test.ts 的 4 个 describe
 * （11 例，断言的是自 2026-09 起不再装配的机制——见该文件顶部的删除记录）。其中断言的是
 * **活行为**的部分（消息清洗 / 忽略会话判定 / 用户消息抽取）必须逐条重建、断言不得削弱：
 * 本文件即该重建（另补边界与错误输入路径）。
 */
import { describe, it, expect } from 'vitest'
import {
  cleanUserMessageText,
  extractUserMessageText,
  isIgnoredSession,
} from '../../src/adapters/SessionMessageFilter.js'

describe('cleanUserMessageText：剥掉系统注入块，保留真实对话', () => {
  it('非字符串输入 → 空串（不抛）', () => {
    expect(cleanUserMessageText(undefined)).toBe('')
    expect(cleanUserMessageText(null)).toBe('')
    expect(cleanUserMessageText(123)).toBe('')
    expect(cleanUserMessageText({ content: 'x' })).toBe('')
  })

  it('剥掉 <system-reminder> 块，保留正文', () => {
    expect(cleanUserMessageText('<system-reminder>噪声\n\n更多噪声</system-reminder>\n\n帮我加个导出按钮'))
      .toBe('帮我加个导出按钮')
  })

  it('整段都是系统注入块 → 空串（调用方据此跳过立项）', () => {
    expect(cleanUserMessageText('<system-reminder>only noise</system-reminder>')).toBe('')
    expect(cleanUserMessageText('Current runtime context. This snapshot supersedes earlier ones.')).toBe('')
    expect(cleanUserMessageText('This is an automatically generated checkpoint cond')).toBe('')
    expect(cleanUserMessageText('\n\n   \n')).toBe('')
  })

  it('正文中后部跟了 runtime context 注入句 → 截到正文为止（仅位置 >20 才截）', () => {
    const text = '一二三四五六七八九十一二三四五六七八九十一二三 Current runtime context. blah blah'
    const out = cleanUserMessageText(text)
    expect(out).toContain('一二三')
    expect(out).not.toContain('Current runtime context')
    // 短正文里开头就是注入句（位置 <=20）→ 交由段落过滤整段丢弃
    expect(cleanUserMessageText('Current runtime context')).toBe('')
  })

  it('多段正文按空行拼接（逐段过滤后保留非噪声段）', () => {
    expect(cleanUserMessageText('第一段\n\n第二段')).toBe('第一段\n\n第二段')
  })
})

describe('extractUserMessageText：从会话事件 data 抽取正文', () => {
  it('content 为字符串 → 原样返回', () => {
    expect(extractUserMessageText({ content: '发现一个 bug，登录页面崩溃' })).toBe('发现一个 bug，登录页面崩溃')
  })

  it('content 为分片数组 → 只取 text 分片并按换行拼接', () => {
    expect(extractUserMessageText({ content: ['a', { text: 'b' }, { other: 1 }, 'c'] })).toBe('a\nb\nc')
  })

  it('非对象 / content 缺失 / content 非文本 → 空串', () => {
    expect(extractUserMessageText(undefined)).toBe('')
    expect(extractUserMessageText('raw string')).toBe('')
    expect(extractUserMessageText({})).toBe('')
    expect(extractUserMessageText({ content: 123 })).toBe('')
  })
})

describe('isIgnoredSession：subagent / child / reqboard 内部会话不参与捕获', () => {
  it('会话 id 前缀命中 → 忽略', () => {
    expect(isIgnoredSession('session-reqboard-1')).toBe(true)
    expect(isIgnoredSession('subagent-xyz')).toBe(true)
    expect(isIgnoredSession('child-abc')).toBe(true)
  })

  it('header/meta.origin=subagent → 忽略', () => {
    expect(isIgnoredSession('session-abc', { header: { origin: 'subagent' } })).toBe(true)
    expect(isIgnoredSession('session-abc', { meta: { origin: 'subagent' } })).toBe(true)
  })

  it('header/meta.parentSession 存在（派生子会话）→ 忽略', () => {
    expect(isIgnoredSession('session-abc', { header: { parentSession: 'parent-1' } })).toBe(true)
    expect(isIgnoredSession('session-abc', { meta: { parentSession: 'parent-1' } })).toBe(true)
  })

  it('delegationDepth > 0 → 忽略；=0 不算', () => {
    expect(isIgnoredSession('session-abc', { header: { delegationDepth: 1 } })).toBe(true)
    expect(isIgnoredSession('session-abc', { meta: { delegationDepth: 2 } })).toBe(true)
    expect(isIgnoredSession('session-abc', { header: { delegationDepth: 0 } })).toBe(false)
  })

  it('普通会话（无 meta 或 meta 无相关字段）→ 不忽略', () => {
    expect(isIgnoredSession('session-abc')).toBe(false)
    expect(isIgnoredSession('session-abc', { header: { cwd: '/x' } })).toBe(false)
    expect(isIgnoredSession('session-abc', null)).toBe(false)
  })
})
