/**
 * Top sidebar entry row for the holdings board: a button inserted as a direct
 * child of the sidebar's logo row owner so it survives shell re-renders
 * (pure DOM row React never manages, mirrored from dsh-taskboard /
 * dashboard-execution sidebar-entry). Sits ABOVE the conversation list
 * (i.e. above 新会话). A MutationObserver + slow timer self-heals late mounts.
 * Clicking toggles board visibility through the shared controller callback.
 *
 * 2026-09-05: 入口由底部官方座位 sidebar.footer.action 迁移到顶部行
 * （用户要求菜单放“新会话”上面）；styles.ts 里 .dsh-hld-entry 样式原样复用。
 *
 * @module dashboard-holdings/client/sidebar-entry
 */
import { ENTRY_SELECTOR, sidebarRoot } from './dom.js'

export interface EntryController {
  isActive(): boolean
  toggle(): void
}

const ICON = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M8 2 V8 L12 11"/><path d="M8 8 L4 5"/></svg>`

export function mountSidebarEntry(controller: EntryController): () => void {
  let entry: HTMLButtonElement | undefined

  const build = (): HTMLButtonElement => {
    const el = document.createElement('button')
    el.type = 'button'
    el.className = 'dsh-hld-entry'
    el.dataset.dshHldEntry = ''
    el.setAttribute('aria-label', '账户持仓')
    el.title = '账户持仓看板'
    el.innerHTML = ICON + '<span class="dsh-hld-entry-label">账户持仓</span>'
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
    // insert after the logo row if present, else prepend → above 新会话/会话列表
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
