/**
 * 通用侧栏顶部入口 —— 所有 DSH GUI page 共享。
 * MutationObserver 自愈 + 5s 慢定时 + 1s active 同步。
 *
 * @module page-kit/client/sidebar-entry
 */
import { sidebarRoot } from './dom.js'

export interface EntryController {
  isActive(): boolean
  toggle(): void
}

export interface SidebarEntryOptions {
  /** CSS/数据集前缀，如 'dsh-hld' */
  prefix: string
  /** SVG 图标字符串（含 <svg>...</svg>） */
  icon: string
  /** 按钮文字 */
  label: string
  /** title / aria-label */
  title: string
  controller: EntryController
}

export function mountSidebarEntry(opts: SidebarEntryOptions): () => void {
  const { prefix, icon, label, title, controller } = opts
  const datasetKey = prefix.replace(/-([a-z])/g, (_, c) => c.toUpperCase()) + 'Entry'
  const entrySelector = '[data-' + prefix + '-entry]'
  let entry: HTMLButtonElement | undefined

  const build = (): HTMLButtonElement => {
    const el = document.createElement('button')
    el.type = 'button'
    el.className = prefix + '-entry'
    ;(el.dataset as any)[datasetKey] = ''
    el.setAttribute('aria-label', title)
    el.title = title
    el.innerHTML = icon + '<span class="' + prefix + '-entry-label">' + label + '</span>'
    el.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); controller.toggle() })
    return el
  }

  const place = (): boolean => {
    const root = sidebarRoot()
    if (root === undefined) return false
    if (root.querySelector(entrySelector) !== null) {
      const existing = root.querySelector<HTMLElement>(entrySelector)
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

  const syncActive = (): void => {
    entry?.setAttribute('data-active', controller.isActive() ? 'true' : 'false')
  }
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
