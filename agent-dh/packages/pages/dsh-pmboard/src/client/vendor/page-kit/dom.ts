/**
 * 通用挂载点助手 —— 所有 DSH GUI page 共享。
 * 与页面前缀无关的全局常量/函数；页面特有的 prefix 常量留在各自 dom.ts 里。
 *
 * @module page-kit/client/dom
 */

export const SIDEBAR_SELECTOR = '[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface'
export const CONVERSATION_COLUMN_SELECTOR = '[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface'

/** 跨面板互斥激活事件；detail 为激活面板名称。 */
export const ACTIVATE_EVENT = 'dsh-panel-activate'

/** 查找侧边栏根节点（logo 行的父容器），未挂载时返回 undefined。 */
export function sidebarRoot(): HTMLElement | undefined {
  const column = document.querySelector<HTMLElement>(SIDEBAR_SELECTOR)
  if (column === null) return undefined
  const logoOwner = column.querySelector<HTMLElement>('[class*="logoRow"]')?.parentElement
  return logoOwner ?? (column.firstElementChild as HTMLElement | undefined)
}

/** 查找中心（会话）列，未挂载时返回 undefined。 */
export function conversationColumn(): HTMLElement | undefined {
  return document.querySelector<HTMLElement>(CONVERSATION_COLUMN_SELECTOR) ?? undefined
}
