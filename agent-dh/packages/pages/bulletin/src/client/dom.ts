/**
 * Mount-point helpers for the bulletin board (pure DOM).
 * Triple-generation selectors mirror dashboard-holdings dom.ts (taskboard-proven):
 * dev shell data-pane, official layout CSS-Module class, Desktop non-compat
 * surfaces — each generation matches one of them. Own namespace dsh-bbd-*
 * never collides with taskboard dsh-atb-*, holdings dsh-hld-*, execution dsh-exec-*.
 *
 * phase1 uses only the sidebar part; board helpers arrive with the board body
 * (phase2) and are declared here so mount code stays import-stable.
 *
 * @module dashboard-bulletin/client/dom
 */
export const ENTRY_SELECTOR = '[data-dsh-bbd-entry]'
export const BOARD_VIEW_SELECTOR = '[data-dsh-bbd-view]'
export const PANEL_NAME = 'dashboard-bulletin'
export const ACTIVE_ATTR = 'data-dsh-bbd-active'
/** Sibling panels activation attrs, evicted when this board opens. */
export const OTHER_ACTIVE_ATTRS = ['data-dsh-atb-active', 'data-dsh-taskboard-active', 'data-dsh-ssh-active', 'data-dsh-exec-active', 'data-dsh-hld-active']
/** Cross-plugin activation event; detail is the activating panel name. */
export const ACTIVATE_EVENT = 'dsh-panel-activate'

export const SIDEBAR_SELECTOR = '[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface'
export const CONVERSATION_COLUMN_SELECTOR = '[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface'

/** Find the sidebar root (logo row owner), or undefined before mount. */
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
