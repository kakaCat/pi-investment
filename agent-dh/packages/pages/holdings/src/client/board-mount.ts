/**
 * Board controller and mount logic — manages the holdings board lifecycle.
 *
 * @module dashboard-holdings/client/board-mount
 */
import { ACTIVE_ATTR, ACTIVATE_EVENT, BOARD_VIEW_SELECTOR, conversationColumn, OTHER_ACTIVE_ATTRS, PANEL_NAME } from './dom.js'
import { buildView } from './view.js'
import type { HoldingsData } from './types.js'

export interface BoardController {
  openBoard(): void
  closeBoard(): void
  toggleBoard(): void
  getSnapshot(): { boardOpen: boolean }
  refresh(): void
  switchAccount(accountName: string): void
}

export function createBoardController(): BoardController {
  let boardOpen = false
  let currentAccount = 'agent_virtual'
  let pollTimer: number | undefined

  const open = (): void => {
    if (boardOpen) return
    boardOpen = true
    console.log('[dashboard-holdings] opening board')

    // Set activation attribute
    document.documentElement.setAttribute(ACTIVE_ATTR, '')

    // Evict sibling panels
    for (const attr of OTHER_ACTIVE_ATTRS) {
      document.documentElement.removeAttribute(attr)
    }

    // Dispatch activation event
    window.dispatchEvent(new CustomEvent(ACTIVATE_EVENT, { detail: PANEL_NAME }))

    // Start polling
    startPolling()
    fetchAndRender(currentAccount)
  }

  const close = (): void => {
    if (!boardOpen) return
    boardOpen = false
    console.log('[dashboard-holdings] closing board')

    document.documentElement.removeAttribute(ACTIVE_ATTR)
    stopPolling()
  }

  const toggle = (): void => {
    if (boardOpen) close()
    else open()
  }

  const refresh = (): void => {
    console.log('[dashboard-holdings] manual refresh')
    fetchAndRender(currentAccount)
  }

  const switchAccount = (accountName: string): void => {
    console.log('[dashboard-holdings] switching account to', accountName)
    currentAccount = accountName
    fetchAndRender(accountName)
  }

  const startPolling = (): void => {
    stopPolling()
    pollTimer = window.setInterval(() => {
      if (boardOpen) fetchAndRender(currentAccount)
    }, 15000) // 15s 轮询
  }

  const stopPolling = (): void => {
    if (pollTimer !== undefined) {
      clearInterval(pollTimer)
      pollTimer = undefined
    }
  }

  const fetchAndRender = async (accountName: string): Promise<void> => {
    try {
      const url = `/dashboard/api/holdings?account=${encodeURIComponent(accountName)}`
      const res = await fetch(url)
      const json = await res.json()

      if (!json.success) {
        throw new Error(json.error || 'Unknown error')
      }

      const data: HoldingsData = json.data
      renderBoard(data)
    } catch (error) {
      console.error('[dashboard-holdings] fetch failed:', error)
      renderError(String(error))
    }
  }

  const renderBoard = (data: HoldingsData): void => {
    const view = document.querySelector(BOARD_VIEW_SELECTOR)
    if (!view) return

    view.innerHTML = buildView(data)
  }

  const renderError = (message: string): void => {
    const view = document.querySelector(BOARD_VIEW_SELECTOR)
    if (!view) return

    view.innerHTML = `
      <div class="dsh-hld-board">
        <div class="dsh-hld-wrap">
          <div class="dsh-hld-head">
            <h1 class="dsh-hld-title">持仓看板</h1>
          </div>
          <div class="dsh-hld-banner show">
            数据加载失败: ${message}
          </div>
        </div>
      </div>
    `
  }

  return {
    openBoard: open,
    closeBoard: close,
    toggleBoard: toggle,
    getSnapshot: () => ({ boardOpen }),
    refresh,
    switchAccount,
  }
}

/**
 * Mount the board view container to the conversation column.
 * Returns a disposer to remove the mount.
 */
export function mountBoard(controller: BoardController): () => void {
  const column = conversationColumn()
  if (!column) {
    console.warn('[dashboard-holdings] conversation column not found')
    return () => {}
  }

  const view = document.createElement('div')
  view.setAttribute('data-dsh-hld-view', '')
  view.className = 'dsh-hld-view'
  column.appendChild(view)

  // Wire global callbacks for view interactions
  ;(window as any).__dshHldRefresh = () => controller.refresh()
  ;(window as any).__dshHldSwitchAccount = (accountName: string) => controller.switchAccount(accountName)

  // Listen for other panels' activation to auto-close
  const onOtherActivate = (event: Event): void => {
    const detail = (event as CustomEvent).detail
    if (detail !== PANEL_NAME) {
      controller.closeBoard()
    }
  }
  window.addEventListener(ACTIVATE_EVENT, onOtherActivate)

  // Listen for sidebar row clicks to auto-close
  const onSidebarClick = (event: Event): void => {
    const target = event.target as HTMLElement
    // Check if click is on a sidebar navigation element (not our footer button)
    if (target.closest('[data-pane="sidebar"]') && !target.closest('[class*="dsh-hld-foot"]')) {
      const isNavClick = target.closest('button, a, [role="button"]')
      if (isNavClick && !target.closest('[data-dsh-hld-entry]')) {
        controller.closeBoard()
      }
    }
  }
  document.addEventListener('click', onSidebarClick)

  console.log('[dashboard-holdings] board mounted')

  return () => {
    window.removeEventListener(ACTIVATE_EVENT, onOtherActivate)
    document.removeEventListener('click', onSidebarClick)
    view.remove()
    delete (window as any).__dshHldRefresh
    delete (window as any).__dshHldSwitchAccount
    console.log('[dashboard-holdings] board unmounted')
  }
}
