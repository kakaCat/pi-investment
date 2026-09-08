/**
 * Mount-point helpers for the holdings board.
 * Universal parts imported from page-kit; page-specific constants kept here.
 *
 * @module dashboard-holdings/client/dom
 */
import { sidebarRoot, conversationColumn, ACTIVATE_EVENT } from '@pi-investment/page-kit/client'

export const ENTRY_SELECTOR = '[data-dsh-hld-entry]'
export const BOARD_VIEW_SELECTOR = '[data-dsh-hld-view]'
export const PANEL_NAME = 'dashboard-holdings'
export const ACTIVE_ATTR = 'data-dsh-hld-active'
/** Sibling panels' activation attributes, evicted when this board opens. */
export const OTHER_ACTIVE_ATTRS = [
  'data-dsh-atb-active', 'data-dsh-taskboard-active', 'data-dsh-ssh-active',
  'data-dsh-exec-active', 'data-dsh-bbd-active', 'data-dsh-gen-active',
]
export { sidebarRoot, conversationColumn, ACTIVATE_EVENT }
