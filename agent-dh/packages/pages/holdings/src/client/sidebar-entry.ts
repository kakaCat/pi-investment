/**
 * Top sidebar entry row for the holdings board.
 * Delegated to page-kit; page only provides icon + label + title.
 *
 * @module dashboard-holdings/client/sidebar-entry
 */
import { mountSidebarEntry as mountGeneric, type EntryController } from '@pi-investment/page-kit/client'

const ICON = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M8 2 V8 L12 11"/><path d="M8 8 L4 5"/></svg>`

export interface SidebarController extends EntryController {}

export function mountSidebarEntry(controller: SidebarController): () => void {
  return mountGeneric({
    prefix: 'dsh-hld',
    icon: ICON,
    label: '账户持仓',
    title: '账户持仓看板',
    controller,
  })
}
