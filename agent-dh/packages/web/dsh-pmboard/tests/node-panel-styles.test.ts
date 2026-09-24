/**
 * TC-11（REQ-260923134706-e72f / t5，FR-7 FR-8）：node-panel 样式分片作用域断言。
 *
 * 看板其他页面零影响：除 :root 变量定义外，每条规则的选择器都含 .dsh-pm-np
 * （面板内容根）或是 .dsh-pm-cprog-detail-panel（本面板唯一外壳）。任何裸全局选择器
 * （如 .modal-overlay / body / .stage-btn）都会让本测试红。
 */
import { describe, it, expect } from 'vitest'
import { NODE_PANEL_CSS } from '../src/client/styles/node-panel.js'

/** 去掉 CSS 注释（避免注释文字被误当选择器/命中裸全局断言）。 */
function stripComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, '')
}

/** 从 CSS 文本抽出每条规则的「选择器部分」（去掉声明块与注释）。 */
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

describe('TC-11 node-panel 样式作用域', () => {
  it('每条规则选择器含 .dsh-pm-np / .dsh-pm-cprog-detail-panel，或为 :root 变量', () => {
    const sels = selectorsOf(NODE_PANEL_CSS)
    expect(sels.length).toBeGreaterThan(20)
    for (const sel of sels) {
      const ok = sel.includes('.dsh-pm-np') || sel.includes('.dsh-pm-cprog-detail-panel') || sel.startsWith(':root')
      expect(ok, '裸全局选择器: ' + sel).toBe(true)
    }
  })
  it('不含常见裸全局选择器（body/.modal/.stage-btn 等）', () => {
    const clean = stripComments(NODE_PANEL_CSS)
    // 词边界：bad 名前面不能是标识符字符（排除 .dsh-pm-np-fold-body 这类合法类名），后面接 {/,/:/空白/行尾
    for (const bad of ['body', '.modal-overlay', '.modal-container', '.stage-btn', '.stage-header', '.stage-body']) {
      const re = new RegExp('(^|[^a-zA-Z0-9_-])' + bad.replace(/\./g, '\\.') + '([\\s{,:]|$)')
      expect(re.test(clean), '出现裸全局选择器 ' + bad).toBe(false)
    }
  })
  it('设计令牌：720px 宽度上限 + 68vh 高度上限 + 10px 圆角', () => {
    expect(NODE_PANEL_CSS).toContain('min(720px, calc(100vw - 130px))')
    expect(NODE_PANEL_CSS).toContain('max-height: 68vh')
    expect(NODE_PANEL_CSS).toContain('border-radius: 10px')
  })
  it('泳道 6 列看板（设计稿 task-columns）：列体纵向滚动不裁切', () => {
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-cols\s*\{[^}]*grid-template-columns:\s*repeat\(6,/)
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-col-body\s*\{[^}]*overflow-y:\s*auto/)
  })
  it('泳道列保底宽 + 灰底全高（2026-09-24 用户裁定修订：放弃无横向滚动）', () => {
    // 列保底 220px（minmax；2026-09-24 用户裁定：150→220，卡片标题尽量一行放下），面板容不下时泳道区横向滚动，不再压扁列
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-cols\s*\{[^}]*grid-template-columns:\s*repeat\(6,\s*minmax\(220px,\s*1fr\)/)
    // 灰底全高：不得用 align-items:start 让短列灰底半截（默认 stretch 拉高）
    expect(NODE_PANEL_CSS).not.toMatch(/\.dsh-pm-np-cols\s*\{[^}]*align-items:\s*start/)
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-cols\s*\{[^}]*min-height:\s*200px/)
  })
  it('泳道横向滚动条可抓不抢戏（2026-09-24 用户裁定：8px + 轨道 + hover 反馈）', () => {
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-pane\[data-pane="list"\]::-webkit-scrollbar\s*\{\s*height:\s*8px/)
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-pane\[data-pane="list"\]::-webkit-scrollbar-track/)
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-pane\[data-pane="list"\]::-webkit-scrollbar-thumb:hover/)
  })
  it('泳道列头状态色提示（2026-09-24 用户裁定：色点 + 同色计数胶囊，0 也有提示）', () => {
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-col-head::before/)
    for (const st of ['in_progress', 'integrating', 'testing', 'in_review', 'done']) {
      expect(NODE_PANEL_CSS).toContain('.dsh-pm-np-col[data-col="' + st + '"] .dsh-pm-np-col-head::before')
      expect(NODE_PANEL_CSS).toContain('.dsh-pm-np-col[data-col="' + st + '"] .dsh-pm-np-col-count')
    }
  })
  it('泳道卡片苹果风：无边框 + 9px 圆角 + 轻阴影 + 列内占满宽度', () => {
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-card\s*\{[^}]*border:\s*none/)
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-card\s*\{[^}]*border-radius:\s*9px/)
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-card\s*\{[^}]*box-shadow:\s*0 1px 3px/)
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-card\s*\{[^}]*width:\s*100%/)
  })
  it('泳道卡片平铺不重叠 + 标题两行 clamp（2026-09-24 实测修复：grid 压行致溢出重叠，改 flex 竖排）', () => {
    // 列体必须是 flex 竖排（grid auto 行会把卡片压到 min-height、标题溢出到下一卡）
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-col-body\s*\{[^}]*display:\s*flex;\s*flex-direction:\s*column/)
    expect(NODE_PANEL_CSS).not.toMatch(/\.dsh-pm-np-col-body\s*\{[^}]*display:\s*grid/)
    // 标题两行 clamp（全文换行难看，用户裁定）
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-card-title\s*\{[^}]*-webkit-line-clamp:\s*2/)
  })
  it('泳道卡片带对应状态颜色（淡底，无左边条；用户裁定 2026-09-23）', () => {
    for (const st of ['todo', 'in_progress', 'integrating', 'testing', 'in_review', 'done']) {
      expect(NODE_PANEL_CSS).toContain('.dsh-pm-np-card[data-status="' + st + '"]')
      // 2026-09-24 用户裁定：DAG 节点与泳道卡片共用同一套六状态色
      expect(NODE_PANEL_CSS).toContain('.dsh-pm-np-dag-node[data-status="' + st + '"]')
    }
    // 无左边条
    expect(NODE_PANEL_CSS).not.toMatch(/\.dsh-pm-np-card\[data-status\]\s*\{[^}]*border-left/)
  })
  it('DAG 节点与泳道卡片同构（无边框 + 9px 圆角 + 轻阴影 + 定宽 208px = 泳道卡片实渲染宽）', () => {
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-dag-node\s*\{[^}]*border:\s*none/)
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-dag-node\s*\{[^}]*border-radius:\s*9px/)
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-dag-node\s*\{[^}]*box-shadow:\s*0 1px 3px/)
    // 208px = 220px 列 - 列体 12px 内边距，与泳道卡片实渲染宽度一致（2026-09-24 用户裁定）
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-dag-node\s*\{[^}]*flex:\s*0 0 208px/)
    // 几何与泳道卡片一致：padding / min-height
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-dag-node\s*\{[^}]*padding:\s*6px 8px/)
    expect(NODE_PANEL_CSS).toMatch(/\.dsh-pm-np-dag-node\s*\{[^}]*min-height:\s*44px/)
  })
  it('DAG 节点标题两行 clamp（与泳道卡片一致，不再单行省略）', () => {
    // 不应再有针对 dag-node 的 nowrap 覆盖
    expect(NODE_PANEL_CSS).not.toMatch(/\.dsh-pm-np-dag-node \.dsh-pm-np-card-title\s*\{[^}]*white-space:\s*nowrap/)
  })
})
