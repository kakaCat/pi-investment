/**
 * Top sidebar entry row for the bulletin board: a button inserted as a direct
 * child of the sidebar logo row owner so it survives shell re-renders (pure
 * DOM row React never manages, mirrored from dsh-taskboard / dashboard-execution
 * / dashboard-holdings sidebar-entry). Sits ABOVE the conversation list
 * (i.e. above 新会话). MutationObserver + slow timer self-heal late mounts.
 * Clicking toggles through the shared EntryController callback.
 *
 * RFC 013 D6：公告板入口 = 顶部行（logoRow 之下、新会话上方），2026-09-05 用户
 * 要求菜单放“新会话”上面，holdings 已同步迁移；本入口与「智能执行」「账户持仓」同锚点并列。
 * phase1：controller 为占位（点按有 data-active 反馈）；phase2 换成真实看板 controller。
 *
 * @module dashboard-bulletin/client/sidebar-entry
 */
import { ENTRY_SELECTOR, sidebarRoot } from './dom.js'

export interface EntryController {
  isActive(): boolean
  toggle(): void
}

const ICON = `<svg width='16' height='16' viewBox='0 0 16 16' fill='none' stroke='currentColor' stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><rect x='3' y='2.5' width='10' height='11' rx='1.5'/><path d='M6 6.5h4M6 9h4'/></svg>`

export function mountSidebarEntry(controller: EntryController): () => void {
  let entry: HTMLButtonElement | undefined

  const build = (): HTMLButtonElement => {
    const el = document.createElement('button')
    el.type = 'button'
    el.className = 'dsh-bbd-entry'
    el.dataset.dshBbdEntry = ''
    el.setAttribute('aria-label', '公告板')
    el.title = '公告板'
    el.innerHTML = ICON + '<span class="dsh-bbd-entry-label">公告板</span>'
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
