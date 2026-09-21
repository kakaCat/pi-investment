/**
 * Sidebar entry row for the bulletin board — delegated to page-kit.
 *
 * @module dashboard-bulletin/client/sidebar-entry
 */
import { mountSidebarEntry as mountGeneric, type EntryController } from '@pi-investment/page-kit/client'

const ICON = `<svg width='16' height='16' viewBox='0 0 16 16' fill='none' stroke='currentColor' stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><rect x='3' y='2.5' width='10' height='11' rx='1.5'/><path d='M6 6.5h4M6 9h4'/></svg>`

export interface SidebarController extends EntryController {}

export function mountSidebarEntry(controller: SidebarController): () => void {
  return mountGeneric({
    prefix: 'dsh-bbd',
    icon: ICON,
    label: '公告板',
    title: '公告板',
    controller,
  })
}
