/**
 * Sidebar entry row for the execution board — delegated to page-kit.
 *
 * @module dashboard-execution/client/sidebar-entry
 */
import { mountSidebarEntry as mountGeneric, type EntryController } from '@pi-investment/page-kit/client'

const ICON = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/></svg>`

export interface SidebarController extends EntryController {}

export function mountSidebarEntry(controller: SidebarController): () => void {
  return mountGeneric({
    prefix: 'dsh-exec',
    icon: ICON,
    label: '智能执行',
    title: '双线执行确认看板 (dashboard-execution)',
    controller,
  })
}
