/**
 * Sidebar entry row for the genome board — delegated to page-kit.
 *
 * @module dashboard-genome/client/sidebar-entry
 */
import { mountSidebarEntry as mountGeneric, type EntryController } from '@pi-investment/page-kit/client'

const ICON = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/><circle cx="12" cy="12" r="3"/></svg>`

export interface SidebarController extends EntryController {}

export function mountSidebarEntry(controller: SidebarController): () => void {
  return mountGeneric({
    prefix: 'dsh-gen',
    icon: ICON,
    label: '自主进化',
    title: '自主进化看板 (dashboard-genome) — 基因组/候选/一致性诊断',
    controller,
  })
}
