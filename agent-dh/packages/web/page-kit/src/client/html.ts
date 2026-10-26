/**
 * HTML 安全工具 —— 所有 DSH GUI page 共享。
 *
 * @module page-kit/client/html
 */

/** 将文本中的 HTML 特殊字符转义为实体，防止 XSS。 */
export function esc(s: unknown): string {
  return String(s ?? '').replace(/[&<>"']/g, (m) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m] ?? m)
  )
}

/**
 * 轮询看板的全量重建守卫（2026-10-26，修「每 15~30s 强制刷新」问题）。
 *
 * 背景：三个看板（holdings/genome/execution）的轮询到期后无条件
 * `el.innerHTML = buildView(data)`，数据没变也重建 —— 滚动位置、展开/折叠、
 * 选中态每轮全被抹掉，用户感知为「看板被强制刷新」。
 *
 * 机制：对每次写入的 HTML 做字符串比对，相同则跳过（DOM 完全不动，交互
 * 状态原样保留）；确实变化时，先快照元素自身与滚动祖先的 scrollTop，
 * 重建后恢复 —— 用户最多看到内容更新，不再被打回顶部。
 *
 * 手动局部改 DOM（过滤 tab 点击、分页切换等不走本函数的地方）后须调用
 * {@link captureHtml} 重新登记当前 DOM，否则下一次轮询会因「模板串 ≠
 * 浏览器序列化串」的微差误判为变化而重建一次（功能正确，但白白重置滚动）。
 */
const htmlGuard = new WeakMap<HTMLElement, string>()

/** 登记元素当前 innerHTML 为「已渲染基线」（手动局部编辑 DOM 后调用）。 */
export function captureHtml(el: HTMLElement): void {
  htmlGuard.set(el, el.innerHTML)
}

interface ScrollSnap { el: Element; top: number }

/** 快照元素自身与至多 4 层可滚动祖先的 scrollTop。 */
function captureScrolls(el: HTMLElement): ScrollSnap[] {
  const snaps: ScrollSnap[] = []
  let cur: Element | null = el
  while (cur !== null && snaps.length < 5 && cur !== document.body) {
    if (cur.scrollHeight > cur.clientHeight) snaps.push({ el: cur, top: cur.scrollTop })
    cur = cur.parentElement
  }
  return snaps
}

/**
 * html 与上次写入相同 → 不动 DOM，返回 false；
 * 不同 → 快照滚动 → 写入 → 恢复滚动，返回 true。
 */
export function setHtmlIfChanged(el: HTMLElement, html: string): boolean {
  if (htmlGuard.get(el) === html) return false
  const snaps = captureScrolls(el)
  el.innerHTML = html
  for (const s of snaps) {
    if (s.el.scrollHeight >= s.top) s.el.scrollTop = s.top
  }
  htmlGuard.set(el, html)
  return true
}
