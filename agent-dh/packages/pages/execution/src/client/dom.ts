/**
 * Mount-point helpers for the execution board (pure DOM).
 * Triple-generation selectors mirror dsh-taskboard's proven approach:
 *   dev shell data-pane, official layout CSS-Module class, Desktop non-compat
 *   surfaces — each generation matches one of them. Own namespace dsh-exec-*
 * never collides with taskboard's dsh-atb-*.
 *
 * @module dashboard-execution/client/dom
 */
export const ENTRY_SELECTOR = '[data-dsh-exec-entry]'
export const BOARD_VIEW_SELECTOR = '[data-dsh-exec-view]'
export const PANEL_NAME = 'dashboard-execution'
export const ACTIVE_ATTR = 'data-dsh-exec-active'
/** Sibling panels' activation attributes, evicted when this board opens. */
export const OTHER_ACTIVE_ATTRS = ['data-dsh-atb-active', 'data-dsh-taskboard-active', 'data-dsh-ssh-active']
/** Cross-plugin activation event; detail is the activating panel name. */
export const ACTIVATE_EVENT = 'dsh-panel-activate'

export const SIDEBAR_SELECTOR = '[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface'
export const CONVERSATION_COLUMN_SELECTOR = '[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface'

/** Find the sidebar root (logo row's owner), or undefined before mount. */
export function sidebarRoot(): HTMLElement | undefined {
  const column = document.querySelector<HTMLElement>(SIDEBAR_SELECTOR)
  if (column === null) return undefined
  const logoOwner = column.querySelector<HTMLElement>('[class*="logoRow"]')?.parentElement
  return logoOwner ?? (column.firstElementChild as HTMLElement | undefined)
}
/** Find the center (conversation) column, or undefined before mount. */
export function conversationColumn(): HTMLElement | undefined {
  return document.querySelector<HTMLElement>(CONVERSATION_COLUMN_SELECTOR) ?? undefined
}
