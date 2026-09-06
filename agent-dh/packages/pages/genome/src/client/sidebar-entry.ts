/**
 * Sidebar entry row for the genome dashboard — a button inserted as a direct
 * child of the sidebar's logo row owner (mirrored from dashboard-execution's
 * sidebar-entry / holdings top-row idiom: pure DOM row React never manages).
 * A MutationObserver + slow timer self-heals late mounts. Clicking toggles
 * board visibility through the shared controller callback.
 *
 * @module dashboard-genome/client/sidebar-entry
 */
import { ENTRY_SELECTOR, sidebarRoot } from './dom.ts'

export interface EntryController {
  isActive(): boolean
  toggle(): void
}

const ICON = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/><circle cx="12" cy="12" r="3"/></svg>`

export function mountSidebarEntry(controller: EntryController): () => void {
  let entry: HTMLButtonElement | undefined

  const build = (): HTMLButtonElement => {
    const el = document.createElement('button')
    el.type = 'button'
    el.className = 'dsh-gen-entry'
    el.dataset.dshGenEntry = ''
    el.setAttribute('aria-label', '自主进化')
    el.title = '自主进化看板 (dashboard-genome) — 基因组/候选/一致性诊断'
    el.innerHTML = ICON + '<span class="dsh-gen-entry-label">自主进化</span>'
    el.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); controller.toggle() })
    return el
  }

  const place = (): boolean => {
    const root = sidebarRoot()
    if (root === undefined) return false
    if (root.querySelector(ENTRY_SELECTOR) !== null) {
      const existing = root.querySelector<HTMLElement>(ENTRY_SELECTOR)
      if (existing !== undefined && entry === undefined) entry = existing as HTMLButtonElement
      return true
    }
    const el = build()
    const logo = root.querySelector<HTMLElement>('[class*="logoRow"]')
    if (logo !== null && logo.nextSibling !== null) root.insertBefore(el, logo.nextSibling)
    else root.prepend(el)
    entry = el
    return true
  }

  place()
  const observer = new MutationObserver(() => {
    if (entry === undefined || !document.contains(entry)) place()
    else if (entry.parentElement === null) place()
  })
  observer.observe(document.body, { childList: true, subtree: true })
  const slowTimer = window.setInterval(() => {
    if (entry === undefined || !document.contains(entry)) place()
  }, 5000)

  return () => {
    window.clearInterval(slowTimer)
    observer.disconnect()
    entry?.remove()
    entry = undefined
  }
}
