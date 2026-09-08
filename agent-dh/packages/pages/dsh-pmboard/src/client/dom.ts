/**
 * Mount-point helpers for the project board (dsh-pmboard).
 * Universal parts imported from page-kit; page-specific constants kept here.
 *
 * @module dsh-pmboard/client/dom
 */
import { ACTIVATE_EVENT, CONVERSATION_COLUMN_SELECTOR } from '@pi-investment/page-kit/client'

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
export { ACTIVATE_EVENT, CONVERSATION_COLUMN_SELECTOR }
