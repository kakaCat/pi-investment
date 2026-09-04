/**
 * Board controller and mount logic — manages the holdings board lifecycle.
 *
 * @module dashboard-holdings/client/board-mount
 */
import { ACTIVE_ATTR, ACTIVATE_EVENT, BOARD_VIEW_SELECTOR, conversationColumn, OTHER_ACTIVE_ATTRS, PANEL_NAME } from './dom.js'
import { buildView, HISTORY_PAGE_SIZE } from './view.js'
import type { HoldingsData } from './types.js'

export interface BoardController {
  openBoard(): void
  closeBoard(): void
  toggleBoard(): void
  getSnapshot(): { boardOpen: boolean }
  refresh(): void
  switchAccount(accountName: string): void
  watchSwitch(key: string): void
  historyPageSwitch(page: number): void
}

export function createBoardController(): BoardController {
  let boardOpen = false
  let currentAccount = 'agent_virtual'
  let watchKey = 'current' // 盯盘中心当前 tab（'current'=默认本账户）
  let historyPage = 0 // 「历史交易」分页卡当前页（0-based；轮询重渲染保留）
  let lastData: HoldingsData | undefined
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
    watchKey = 'current' // 切换账户后盯盘中心默认回到新账户的「本账户」tab
    historyPage = 0 // 切换账户后历史交易回到第 1 页
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
    lastData = data
    const view = document.querySelector(BOARD_VIEW_SELECTOR)
    if (!view) return

    view.innerHTML = buildView(data, watchKey, historyPage)
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

  // 盯盘中心 tab 切换：仅用当前数据重渲染（不重新拉取）；15s 轮询仍按所选 tab 展示
  const watchSwitch = (key: string): void => {
    const k = String(key || 'current')
    if (k === watchKey) return
    watchKey = k
    if (lastData) renderBoard(lastData)
  }

  // 历史交易翻页：页号越界自动收敛（数据随轮询增减后防止空页）；只重渲染不重新拉取
  const historyPageSwitch = (page: number): void => {
    const total = (lastData?.tradeHistory?.length ?? 0)
    const pages = Math.max(1, Math.ceil(total / HISTORY_PAGE_SIZE))
    const next = Math.max(0, Math.min(Math.trunc(Number(page) || 0), pages - 1))
    if (next === historyPage) return
    historyPage = next
    if (lastData) renderBoard(lastData)
  }

  return {
    openBoard: open,
    closeBoard: close,
    toggleBoard: toggle,
    getSnapshot: () => ({ boardOpen }),
    refresh,
    switchAccount,
    watchSwitch,
    historyPageSwitch,
  }
}

/**
 * Mount the board view container to the conversation column.
 * Returns a disposer to remove the mount.
 */
export function mountBoard(controller: BoardController): () => void {
  let container: HTMLDivElement | undefined

  // 中心列可能晚于 client apply() 挂载（boot 时序）：观察 body，列出现后补建视图容器。
  // 此前无重试导致列未就绪时挂载永久失败（'conversation column not found'）→ 点击只置 active
  // 属性、无任何可见内容。
  const ensure = (): void => {
    if (container !== undefined) return
    const column = conversationColumn()
    if (column === undefined) return
    container = document.createElement('div')
    container.setAttribute('data-dsh-hld-view', '')
    container.className = 'dsh-hld-view'
    column.appendChild(container)
    console.log('[dashboard-holdings] board container mounted')
  }
  const waitObserver = new MutationObserver(() => { ensure() })
  waitObserver.observe(document.body, { childList: true, subtree: true })
  ensure()

  // Wire global callbacks for view interactions
  ;(window as any).__dshHldRefresh = () => controller.refresh()
  ;(window as any).__dshHldSwitchAccount = (accountName: string) => controller.switchAccount(accountName)
  ;(window as any).__dshHldWatchTab = (key: string) => controller.watchSwitch(String(key))
  ;(window as any).__dshHldHistoryPage = (page: unknown) => controller.historyPageSwitch(Number(page))

  // Listen for other panels' activation to auto-close
  const onOtherActivate = (event: Event): void => {
    const detail = (event as CustomEvent).detail
    if (detail !== PANEL_NAME && controller.getSnapshot().boardOpen) controller.closeBoard()
  }
  window.addEventListener(ACTIVATE_EVENT, onOtherActivate)

  // 关板：点击任何非本板/本入口（footer 按钮）的区域即关闭。会话行是 role=treeitem 的 div，
  // 不能按 button/a/role=button 判定（旧逻辑从不触发 → active 属性卡死 → 点会话不显示）。
  const onClickOutside = (event: MouseEvent): void => {
    if (!controller.getSnapshot().boardOpen) return
    const target = event.target as HTMLElement | null
    if (target === null) return
    if (target.closest('[data-dsh-hld-view]') !== null) return
    if (target.closest('[class*="dsh-hld-foot"]') !== null) return
    if (target.closest('[data-dsh-hld-entry]') !== null) return
    controller.closeBoard()
  }
  document.addEventListener('click', onClickOutside, true)

  return () => {
    window.removeEventListener(ACTIVATE_EVENT, onOtherActivate)
    document.removeEventListener('click', onClickOutside, true)
    waitObserver.disconnect()
    if (container !== undefined) container.remove()
    delete (window as any).__dshHldRefresh
    delete (window as any).__dshHldSwitchAccount
    delete (window as any).__dshHldWatchTab
    delete (window as any).__dshHldHistoryPage
    console.log('[dashboard-holdings] board unmounted')
  }
}

