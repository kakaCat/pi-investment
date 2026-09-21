/**
 * renderMarkdown 链接协议白名单回归（REQ-f0579a FR-5）。
 * 缺陷：链接替换不过滤 javascript:/data: 协议 —— markdown 里的 [x](javascript:…) 会被
 * 渲染成可点 <a href="javascript:…">（低危 XSS 面）。修复 = 只放行 http/https/mailto/相对路径。
 */
import { describe, it, expect } from 'vitest'
import { renderMarkdown } from '../src/client/render/dom-utils.js'

describe('renderMarkdown 链接协议白名单', () => {
  it('javascript: 协议链接不渲染为可点链接', () => {
    const out = renderMarkdown('[点我](javascript:alert(1))')
    expect(out).not.toContain('<a href')
    expect(out).toContain('点我')
  })

  it('data: 协议链接不渲染为可点链接', () => {
    const out = renderMarkdown('[点我](data:text/html;base64,PHNjcmlwdD4=)')
    expect(out).not.toContain('<a href')
  })

  it('http/https/mailto/相对路径/锚点正常渲染', () => {
    for (const url of ['https://a.b/c', 'http://a.b', 'mailto:x@y.z', 'docs/requirements/REQ-1/plan.md', '#anchor']) {
      const out = renderMarkdown('[链接](' + url + ')')
      expect(out, url).toContain('<a href="' + url + '"')
    }
  })
})
