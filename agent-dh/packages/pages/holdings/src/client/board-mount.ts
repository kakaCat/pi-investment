/**
 * Board controller and mount logic — manages the holdings board lifecycle.
 * Lifecycle (mutex/poll/mount/outside-click/dispose) delegated to page-kit board-shell.
 * Page retains business state (account/watchKey/historyPage) and solve-kit integration.
 *
 * @module dashboard-holdings/client/board-mount
 */
import { ACTIVE_ATTR, ACTIVATE_EVENT, BOARD_VIEW_SELECTOR, PANEL_NAME, OTHER_ACTIVE_ATTRS } from './dom.js'
import { buildHistoryCard, buildView, buildWatchCardHtml, HISTORY_PAGE_SIZE } from './view.js'
import type { HoldingsData } from './types.js'
import {
  createSolveKit, type SolveCandidate, type SolveIdentity, type SolveKit, type SolveSnapshot,
} from '@pi-investment/solve-kit/client'
import { createBoardShell } from '@pi-investment/page-kit/client'

export interface BoardController {
  openBoard(): void
  closeBoard(): void
  toggleBoard(): void
  getSnapshot(): { boardOpen: boolean }
  refresh(): void
  switchAccount(accountName: string): void
  watchSwitch(key: string): void
  historyPageSwitch(page: number): void
  solveTask(btn?: HTMLElement): void
}

export function createBoardController(): BoardController {
  let currentAccount = 'agent_virtual'
  let watchKey = 'current'
  let historyPage = 0
  let lastData: HoldingsData | undefined
  let shellRef: { open(): void; close(): void; toggle(): void; isActive(): boolean } | undefined

  const fetchAndRender = async (accountName: string): Promise<void> => {
    try {
      const url = '/dashboard/api/holdings?account=' + encodeURIComponent(accountName)
      const res = await fetch(url)
      const json = await res.json()
      if (!json.success) throw new Error(json.error || 'Unknown error')
      renderBoard(json.data as HoldingsData)
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
    view.innerHTML = '<div class="dsh-hld-board"><div class="dsh-hld-wrap"><div class="dsh-hld-head"><h1 class="dsh-hld-title">持仓看板</h1></div><div class="dsh-hld-banner show">数据加载失败: ' + message + '</div></div></div>'
  }

  const watchSwitch = (key: string): void => {
    const k = String(key || 'current')
    if (k === watchKey) return
    watchKey = k
    if (!lastData) return
    const host = document.getElementById('dsh-hld-watch')
    if (host === null) { renderBoard(lastData); return }
    const tpl = document.createElement('template')
    tpl.innerHTML = buildWatchCardHtml(lastData, watchKey)
    const node = tpl.content.firstElementChild as HTMLElement | null
    if (node === null) { renderBoard(lastData); return }
    host.replaceWith(node)
  }

  const historyPageSwitch = (page: number): void => {
    const total = lastData?.tradeHistory?.length ?? 0
    const pages = Math.max(1, Math.ceil(total / HISTORY_PAGE_SIZE))
    const next = Math.max(0, Math.min(Math.trunc(Number(page) || 0), pages - 1))
    if (next === historyPage) return
    historyPage = next
    if (!lastData) return
    const host = document.getElementById('dsh-hld-hx')
    if (host === null) { renderBoard(lastData); return }
    const tpl = document.createElement('template')
    tpl.innerHTML = buildHistoryCard(lastData, historyPage)
    const node = tpl.content.firstElementChild as HTMLElement | null
    if (node === null) { renderBoard(lastData); return }
    host.replaceWith(node)
  }

  // solve-kit
  const hldCurrentSession = (): string => {
    const w = window as any
    try { return String((w.__dshHldSessions ?? w.__dshHldCtx?.sessions)?.list?.getSnapshot?.().current ?? '') } catch { return '' }
  }
  const hldCandidates = (): SolveCandidate[] => {
    const w = window as any
    const out: SolveCandidate[] = []
    try {
      const svc = w.__dshHldSessions ?? w.__dshHldCtx?.sessions
      const list = svc?.list?.getSnapshot?.()
      const items: any[] = Array.isArray(list?.items) ? list.items : (list?.ids ?? []).map((id: string) => ({ id, title: id }))
      const archived = new Set<string>(
        w.__dshHldWorkspaces?.list?.getSnapshot?.().archivedSessionIds ??
        w.__dshHldCtx?.workspaces?.list?.getSnapshot?.().archivedSessionIds ?? [])
      const cur = hldCurrentSession()
      for (const it of items) {
        const id = String(it?.id ?? '')
        if (!id || archived.has(id)) continue
        const blank = Boolean(it?.blank)
        const origin = String(it?.origin ?? '')
        if (blank || origin.startsWith('subagent')) continue
        const label = String(it?.title ?? it?.displayTitle ?? '').slice(0, 42)
        out.push({ sid: id, label: label || id, current: id === cur })
      }
    } catch { }
    return out
  }
  const hldSnapshotFor = (kind: 'task' | 'error', identity: SolveIdentity): SolveSnapshot | null => {
    if (kind !== 'task') return null
    const auto = lastData?.automation
    if (!auto || auto.engine === true) return null
    const t = (auto.tasks ?? []).find((x) => String(x.name) === String(identity.name ?? ''))
    if (!t) return null
    const fetchedAt = String(lastData?.summary?.lastUpdated ?? '')
    return { kind: 'task', snap: {
      name: t.name,
      src: String(t.command || 'Agent OS 调度任务'),
      scheduleExpr: t.scheduleExpr,
      nextRunAt: t.nextRunAt,
      lastRun: { status: t.lastStatus, triggeredAt: t.lastAt, finishedAt: t.lastAt, err: t.lastError },
      todayTriggered: t.todayTriggered,
      todaySuccess: t.todaySuccess,
      fetchedAt,
      error: t.lastError,
    } as Record<string, unknown> }
  }
  const solveKit: SolveKit = createSolveKit({
    endpoint: '/dashboard/api/holdings/solve',
    prefix: 'dsh-hld',
    candidates: hldCandidates,
    current: hldCurrentSession,
    resolveSnapshot: hldSnapshotFor,
  })

  return {
    openBoard: () => shellRef?.open(),
    closeBoard: () => shellRef?.close(),
    toggleBoard: () => shellRef?.toggle(),
    getSnapshot: () => ({ boardOpen: shellRef?.isActive() ?? false }),
    refresh: () => { console.log('[dashboard-holdings] manual refresh'); fetchAndRender(currentAccount) },
    switchAccount: (accountName) => {
      console.log('[dashboard-holdings] switching account to', accountName)
      currentAccount = accountName
      watchKey = 'current'
      historyPage = 0
      fetchAndRender(accountName)
    },
    watchSwitch,
    historyPageSwitch,
    solveTask: (btn) => {
      if (!btn) return
      const name = String(btn.dataset?.solveTask ?? '')
      if (!name) return
      solveKit.openPicker(btn, 'task', { name })
    },
  }
}

export function mountBoard(controller: BoardController): () => void {
  ;(window as any).__dshHldRefresh = () => controller.refresh()
  ;(window as any).__dshHldSwitchAccount = (accountName: string) => controller.switchAccount(accountName)
  ;(window as any).__dshHldWatchTab = (key: string) => controller.watchSwitch(String(key))
  ;(window as any).__dshHldHistoryPage = (page: unknown) => controller.historyPageSwitch(Number(page))
  ;(window as any).__dshHldSolveTask = (btn?: HTMLElement) => controller.solveTask(btn)

  const shell = createBoardShell({
    prefix: 'dsh-hld',
    panelName: PANEL_NAME,
    activeAttr: ACTIVE_ATTR,
    otherActiveAttrs: OTHER_ACTIVE_ATTRS,
    pollMs: 15000,
    buildContainer: () => {
      const el = document.createElement('div')
      el.setAttribute('data-dsh-hld-view', '')
      el.className = 'dsh-hld-view'
      return el
    },
    onMount: () => {
      controller.refresh()
      return undefined
    },
    onPoll: () => controller.refresh(),
  })

  const ctrl = controller as any
  ctrl.openBoard = shell.open
  ctrl.closeBoard = shell.close
  ctrl.toggleBoard = shell.toggle
  ctrl.getSnapshot = () => ({ boardOpen: shell.isActive() })

  return () => {
    shell.dispose()
    delete (window as any).__dshHldRefresh
    delete (window as any).__dshHldSwitchAccount
    delete (window as any).__dshHldWatchTab
    delete (window as any).__dshHldHistoryPage
    delete (window as any).__dshHldSolveTask
    console.log('[dashboard-holdings] board unmounted')
  }
}
