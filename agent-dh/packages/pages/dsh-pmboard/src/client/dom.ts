/** DOM selectors and constants for reqboard client. */

/** Center column selector (conversation area). */
export const CONVERSATION_COLUMN_SELECTOR = '[data-dsh-center-column], .dsh-center-column, main[role="main"]'

/** Data attribute set on <html> when board is active. */
export const ACTIVE_ATTR = 'data-dsh-reqboard-active'

/** Board container selector. */
export const BOARD_VIEW_SELECTOR = '[data-dsh-reqboard-view]'

/** Footer entry selector. */
export const ENTRY_SELECTOR = '.dsh-reqboard-foot'

/** Panel identity. */
export const PANEL_NAME = 'dsh-pmboard'
export const PANEL_LABEL = '项目看板'

/** Activation event (cross-plugin). */
export const ACTIVATE_EVENT = 'dsh:panel-activate'
