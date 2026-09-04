/**
 * Sidebar entry row for the execution board: a button inserted as a direct
 * child of the sidebar's logo row owner so it survives shell re-renders
 * (pure DOM row React never manages, mirrored from dsh-taskboard). A
 * MutationObserver + slow timer self-heals late mounts. Clicking toggles
 * board visibility through the shared controller callback.
 *
 * @module dashboard-execution/client/sidebar-entry
 */
import { ENTRY_SELECTOR, sidebarRoot } from './dom.ts'

export interface EntryController {
  isActive(): boolean
  toggle(): void
}

const ICON = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/></svg>`

export function mountSidebarEntry(controller: EntryController): () => void {
  let entry: HTMLButtonElement | undefined

  const build = (): HTMLButtonElement => {
    const el = document.createElement('button')
    el.type = 'button'
    el.className = 'dsh-exec-entry'
    el.dataset.dshExecEntry = ''
    el.setAttribute('aria-label', '智能执行')
    el.title = '双线执行确认看板 (dashboard-execution)'
    el.innerHTML = ICON + '<span class="dsh-exec-entry-label">智能执行</span>'
    el.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); controller.toggle() })
    return el
  }

  const place = (): boolean => {
    const root = sidebarRoot()
    if (root === undefined) return false
    if (root.querySelector(ENTRY_SELECTOR) !== null) {
      // already mounted somewhere in root; make sure it is this root
      const existing = root.querySelector<HTMLElement>(ENTRY_SELECTOR)
      if (existing !== undefined && entry === undefined) entry = existing as HTMLButtonElement
      return true
    }
    const el = build()
    // insert after the logo row if present, else prepend
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

  const syncActive = (): void => { entry?.setAttribute('data-active', controller.isActive() ? 'true' : 'false') }
  const tick = window.setInterval(syncActive, 1000)
  syncActive()

  return () => {
    observer.disconnect()
    window.clearInterval(slowTimer)
    window.clearInterval(tick)
    entry?.remove()
    entry = undefined
  }
}
