/**
 * DAG 画布面板样式分片断言（REQ-260929010300-dbf9 FR-6）· serves: FR-6
 *
 * 皮肤统一到会话面板的 np 苹果风：面板骨架取值全部走 --dsh-pm-np-* 令牌，
 * 不再引用 dsw 主题变量（那份是另一种观感，本轮订正要消除的正是两处不同源）。
 * 类名与选择器作用域照旧（-panel/-head/-btn/-flowstat/-canvas-wrap/-legend）。
 */
import { describe, it, expect } from 'vitest'
import { DAG_CSS } from '../src/client/styles/dag.js'

/** 去掉 CSS 注释（避免注释文字被误当选择器命中）。 */
function stripComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, '')
}

/** 从 CSS 文本抽出每条规则的「选择器部分」。 */
function selectorsOf(css: string): string[] {
  const clean = stripComments(css)
  const out: string[] = []
  const re = /([^{}@]+)\{/g
  let m: RegExpExecArray | null
  while ((m = re.exec(clean)) !== null) {
    const sel = m[1].trim()
    if (sel.length > 0) out.push(sel)
  }
  return out
}

/** 取某条规则（精确选择器 + 单空格 + 花括号）的声明块正文；找不到返回空串。 */
function ruleOf(css: string, selector: string): string {
  const clean = stripComments(css)
  const start = clean.indexOf(selector + ' {')
  if (start < 0) return ''
  const open = clean.indexOf('{', start)
  const close = clean.indexOf('}', open)
  return clean.slice(open + 1, close)
}

describe('FR-6 DAG 面板皮肤 = 会话面板 np 苹果风', () => {
  it('面板不再有标题行 / 统计条（2026-09-29 用户裁定 B：两处从简）', () => {
    expect(DAG_CSS).not.toContain('.dsh-pm-dag-title')
    expect(DAG_CSS).not.toContain('.dsh-pm-dag-flowstat')
  })
  it('不再引用 dsw 主题变量（--dsw-*）', () => {
    expect(DAG_CSS).not.toMatch(/--dsw-/)
  })
  it('取值来源为 --dsh-pm-np-* 苹果风令牌', () => {
    expect(DAG_CSS).toContain('--dsh-pm-np-')
    expect(DAG_CSS).toContain('--dsh-pm-np-bg')
    expect(DAG_CSS).toContain('--dsh-pm-np-blue')
  })
  it('作用域：每条规则选择器含 .dsh-pm-dag-（与看板其它页面零冲突）', () => {
    const sels = selectorsOf(DAG_CSS)
    expect(sels.length).toBeGreaterThan(8)
    for (const sel of sels) expect(sel.includes('.dsh-pm-dag-'), '裸选择器: ' + sel).toBe(true)
  })
  it('面板骨架的关键类仍在（构建与挂载靠它们定位）', () => {
    for (const c of ['.dsh-pm-dag-panel', '.dsh-pm-dag-head', '.dsh-pm-dag-canvas-wrap', '.dsh-pm-dag-legend']) {
      expect(DAG_CSS).toContain(c)
    }
  })
  it('胶囊与圆角口径：980px 胶囊 + 12px 面板圆角', () => {
    expect(DAG_CSS).toContain('border-radius: 980px')
    expect(DAG_CSS).toContain('border-radius: 12px')
  })
  it('面板底色 = 泳道图底色（--dsh-pm-np-bg，2026-09-29 用户：应按照泳道图的底色）', () => {
    const panel = /\.dsh-pm-dag-panel\s*\{[^}]*\}/.exec(DAG_CSS)?.[0] ?? ''
    expect(panel).toContain('background: var(--dsh-pm-np-bg)')
    expect(panel).not.toContain('background: #fff')
  })
  it('骨架逐条口径（2026-09-29 裁定：面板非白底，用泳道底色）', () => {
    // 面板：泳道底色 + line-soft 描边 + 12px 圆角（用户 2026-09-29 裁定，不得为白底）
    const panel = ruleOf(DAG_CSS, '.dsh-pm-dag-panel')
    expect(panel).toContain('background: var(--dsh-pm-np-bg)')
    expect(panel).not.toContain('#fff')
    expect(panel).toContain('border: 1px solid var(--dsh-pm-np-line-soft)')
    expect(panel).toContain('border-radius: 12px')
    // 表头：#f5f5f7 底 + 下描边
    const head = ruleOf(DAG_CSS, '.dsh-pm-dag-head')
    expect(head).toContain('background: var(--dsh-pm-np-bg)')
    expect(head).toContain('border-bottom: 1px solid var(--dsh-pm-np-line-soft)')
    // 说明 / 图例：三级 / 二级文本色
    expect(ruleOf(DAG_CSS, '.dsh-pm-dag-sub')).toContain('color: var(--dsh-pm-np-text3)')
    expect(ruleOf(DAG_CSS, '.dsh-pm-dag-legend')).toContain('color: var(--dsh-pm-np-text2)')
    // 工具按钮：980px 胶囊
    expect(ruleOf(DAG_CSS, '.dsh-pm-dag-btn')).toContain('border-radius: 980px')
    // 选中态：blue 实底
    expect(ruleOf(DAG_CSS, '.dsh-pm-dag-btn.is-on')).toContain('background: var(--dsh-pm-np-blue)')
    // 滚动条 8px + 圆角
    expect(ruleOf(DAG_CSS, '.dsh-pm-dag-canvas-wrap::-webkit-scrollbar')).toContain('width: 8px')
    expect(ruleOf(DAG_CSS, '.dsh-pm-dag-canvas-wrap::-webkit-scrollbar-thumb')).toContain('border-radius: 4px')
  })
})
