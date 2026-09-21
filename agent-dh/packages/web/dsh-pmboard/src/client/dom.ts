/**
 * Mount-point helpers for the project board (dsh-pmboard).
 * 挂载点常量与中心列查找；页面特有的 prefix 常量也在这里。
 *
 * @module dsh-pmboard/client/dom
 */

/** 跨面板互斥激活事件；detail 为激活面板名称。 */
export const ACTIVATE_EVENT = 'dsh-panel-activate'
export const CONVERSATION_COLUMN_SELECTOR = '[data-pane="conversation"], [class*="centerCol"], .dshDesktopConversationSurface'

/** 查找中心（会话）列，未挂载时返回 undefined。 */
export function conversationColumn(): HTMLElement | undefined {
  return document.querySelector<HTMLElement>(CONVERSATION_COLUMN_SELECTOR) ?? undefined
}

export const ENTRY_SELECTOR = '[data-dsh-pm-entry]'
export const BOARD_VIEW_SELECTOR = '[data-dsh-pm-view]'
export const PANEL_NAME = 'dsh-pmboard'
export const PANEL_LABEL = '项目看板'
export const ACTIVE_ATTR = 'data-dsh-pm-active'
/** Sibling panels' activation attributes, evicted when this board opens. */
export const OTHER_ACTIVE_ATTRS = [
  'data-dsh-atb-active', 'data-dsh-taskboard-active', 'data-dsh-ssh-active',
  'data-dsh-hld-active', 'data-dsh-bbd-active', 'data-dsh-gen-active', 'data-dsh-exec-active',
]
