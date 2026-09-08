/**
 * Mount-point helpers for the execution board.
 * Universal parts imported from page-kit; page-specific constants kept here.
 *
 * @module dashboard-execution/client/dom
 */
import { sidebarRoot, conversationColumn, ACTIVATE_EVENT } from '@pi-investment/page-kit/client'

export const ENTRY_SELECTOR = '[data-dsh-exec-entry]'
export const BOARD_VIEW_SELECTOR = '[data-dsh-exec-view]'
export const PANEL_NAME = 'dashboard-execution'
export const ACTIVE_ATTR = 'data-dsh-exec-active'
/** Sibling panels' activation attributes, evicted when this board opens. */
export const OTHER_ACTIVE_ATTRS = ['data-dsh-atb-active', 'data-dsh-taskboard-active', 'data-dsh-ssh-active', 'data-dsh-hld-active', 'data-dsh-bbd-active', 'data-dsh-gen-active']
export { sidebarRoot, conversationColumn, ACTIVATE_EVENT, CONVERSATION_COLUMN_SELECTOR }