/**
 * Mount-point helpers for the genome board.
 * Universal parts imported from page-kit; page-specific constants kept here.
 *
 * @module dashboard-genome/client/dom
 */
import { sidebarRoot, conversationColumn, ACTIVATE_EVENT } from '@pi-investment/page-kit/client'

export const ENTRY_SELECTOR = '[data-dsh-gen-entry]'
export const BOARD_VIEW_SELECTOR = '[data-dsh-gen-view]'
export const PANEL_NAME = 'dashboard-genome'
export const ACTIVE_ATTR = 'data-dsh-gen-active'
/** Sibling panels' activation attributes, evicted when this board opens. */
export const OTHER_ACTIVE_ATTRS = [''data-dsh-atb-active'', ''data-dsh-taskboard-active'', ''data-dsh-ssh-active'', ''data-dsh-hld-active'', ''data-dsh-exec-active'', ''data-dsh-bbd-active'']
export { sidebarRoot, conversationColumn, ACTIVATE_EVENT }
