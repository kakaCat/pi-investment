/**
 * Board view mounting: delegated to page-kit board-shell for lifecycle.
 * Page retains solve-kit, event delegation, and fetch/render logic.
 *
 * @module dashboard-execution/client/board-mount
 */
import type { ApiResponse, BoardData } from './types.ts'
import {
  BOARD_VIEW_SELECTOR, PANEL_NAME, ACTIVE_ATTR, OTHER_ACTIVE_ATTRS,
  ACTIVATE_EVENT, ENTRY_SELECTOR,
} from './dom.ts'
import { buildView, renderAll, renderTasks, setTaskSel, setDomSel, setTaskPage, type ViewRefs } from './view.ts'
import { createSolveKit } from '@pi-investment/solve-kit/client'
import { createBoardShell } from '@pi-investment/page-kit/client'

const BOARD_API = '/dashboard/api/board'
const POLL_MS = 30000
let fetching = false

export interface BoardController {
  isActive(): boolean
  toggle(): void
  getSnapshot(): { boardOpen: boolean }
  openBoard(): void
  closeBoard(): void
  toggleBoard(): void
}

export function createBoardController(): BoardController {
  const ctrl: BoardController = {
    isActive: () => false,
    toggle: () => {},
    getSnapshot: () => ({ boardOpen: false }),
    openBoard: () => {},
    closeBoard: () => {},
    toggleBoard: () => {},
  }
  return ctrl
}

export function mountBoard(controller: BoardController): () => void {
  let refs: ViewRefs | undefined
  let lastBoard: BoardData | undefined

  const shell = createBoardShell({
    prefix: 'dsh-exec',
    panelName: PANEL_NAME,
    activeAttr: ACTIVE_ATTR,
    otherActiveAttrs: OTHER_ACTIVE_ATTRS,
    pollMs: POLL_MS,
    pauseOnHidden: true,
    dispatchTarget: 'document',
    listenTarget: 'document',
    buildContainer: () => {
      const el = document.createElement('div')
      el.dataset.dshExecView = ''
      el.className = 'dsh-exec-view'
      return el
    },
    onMount: (container) => {
      refs = buildView()
      container.appendChild(refs.board)
      const refreshBtn = container.querySelector<HTMLButtonElement>('[data-role="refresh"]')
      const onRefresh = () => { void fetchBoard() }
      refreshBtn?.addEventListener('click', onRefresh)
      // 调度任务点击委派
      const onTasksClick = (ev: MouseEvent) => {
        const target = ev.target as Element
        if (lastBoard === undefined || refs === undefined) return
        const solveBtn = target.closest<HTMLElement>('.dsh-exec-solve[data-solve-task]')
        if (solveBtn !== null && solveBtn.dataset.solveTask !== undefined) {
          kit.openPicker(solveBtn, 'task', { name: solveBtn.dataset.solveTask })
          return
        }
        const tab = target.closest<HTMLElement>('.dsh-exec-tab[data-dom]')
        if (tab !== null) { setDomSel(tab.dataset.dom ?? 'all'); renderTasks(refs, lastBoard); return }
        const pg = target.closest<HTMLElement>('.dsh-exec-tkpg [data-tkpage]')
        if (pg !== null && !(pg as HTMLButtonElement).disabled) { setTaskPage(Number(pg.dataset.tkpage)); renderTasks(refs, lastBoard); return }
        const row = target.closest<HTMLElement>('.dsh-exec-tr[data-tk]')
        const nm = row?.dataset.tk
        if (nm === undefined) return
        setTaskSel(nm)
        renderTasks(refs, lastBoard)
      }
      refs.tasksBox.addEventListener('click', onTasksClick)
      // 错误事件条「我来解决」
      const onErrsClick = (ev: MouseEvent) => {
        const solveBtn = (ev.target as Element).closest<HTMLElement>('.dsh-exec-solve[data-solve-err]')
        if (solveBtn !== null && solveBtn.dataset.solveErr !== undefined) {
          kit.openPicker(solveBtn, 'error', { index: Number(solveBtn.dataset.solveErr) })
        }
      }
      refs.errsBox.addEventListener('click', onErrsClick)
      void fetchBoard(true)
      return () => {
        refreshBtn?.removeEventListener('click', onRefresh)
        refs.tasksBox.removeEventListener('click', onTasksClick)
        refs.errsBox.removeEventListener('click', onErrsClick)
      }
    },
    onPoll: () => { void fetchBoard() },
  })

  controller.isActive = shell.isActive
  controller.toggle = shell.toggle
  controller.openBoard = shell.open
  controller.closeBoard = shell.close
  controller.toggleBoard = shell.toggle
  controller.getSnapshot = () => ({ boardOpen: shell.isActive() })

  async function fetchBoard(initial = false): Promise<void> {
    if (fetching) return
    fetching = true
    try {
      const res = await fetch(BOARD_API, { headers: { Accept: 'application/json' } })
      if (!res.ok) throw new Error('HTTP ' + res.status)
      const json = (await res.json()) as ApiResponse
      if (!json.success || json.data === undefined) throw new Error(json.error ?? 'API 返回失败')
      if (refs === undefined) return
      lastBoard = json.data as BoardData
      renderAll(refs, lastBoard)
      refs.meta.textContent = '刷新于 ' + new Date().toLocaleTimeString() + ' · 数据 ' + (json.data.fetchedAt ?? '')
      refs.banner.classList.remove('show')
    } catch (e) {
      if (refs === undefined) return
      refs.banner.innerHTML = '⚠ 无法连接看板 API：' + String(e && (e as Error).message ? (e as Error).message : e) + ' — 请检查 :13080 与插件状态'
      refs.banner.classList.add('show')
    } finally {
      fetching = false
    }
  }

  // solve-kit
  const sessionCandidates = (): { sid: string; label: string; current: boolean }[] => {
    const w = window as any
    let fac = w.__dshExecSessions
    if (!fac?.list) { try { fac = w.__dshExecCtx?.sessions; if (fac?.list) w.__dshExecSessions = fac } catch { } }
    let archived: Set<string> | null = null
    try {
      const ar = w.__dshExecWorkspaces?.list?.getSnapshot?.()?.archivedSessionIds
      if (Array.isArray(ar)) archived = new Set(ar.map(String))
    } catch { }
    const out: { sid: string; label: string; current: boolean }[] = []
    try {
      const snap = fac?.list?.getSnapshot?.()
      if (!snap) return out
      const cur = String(snap.current ?? '')
      const rows: any[] = Array.isArray(snap.items)
        ? snap.items
        : (Array.isArray(snap.ids) ? snap.ids.map((id: string) => (snap.byId as any)?.[id]).filter(Boolean) : [])
      for (const it of rows) {
        const sid = String(it?.id ?? it?.sessionId ?? '')
        if (!sid || it.blank) continue
        if (archived?.has(sid)) continue
        if (it?.origin === 'subagent') continue
        out.push({ sid, label: String(it.displayTitle ?? it.title ?? sid), current: sid === cur })
      }
    } catch { }
    return out
  }
  const currentSession = (): string => {
    try { return String((window as any).__dshExecSessions?.list?.getSnapshot?.()?.current ?? '') } catch { return '' }
  }
  const snapshotFor = (kind: 'task' | 'error', identity: { name?: string; index?: number }): { kind: 'task' | 'error'; snap: Record<string, unknown> } | null => {
    if (lastBoard === undefined) return null
    const fetchedAt = lastBoard.fetchedAt ?? ''
    if (kind === 'task') {
      const t = (lastBoard.tasks ?? []).find((x) => String(x.name) === identity.name)
      return t ? { kind: 'task', snap: { ...(t as Record<string, unknown>), fetchedAt } } : null
    }
    const e = (lastBoard.errors ?? [])[Number(identity.index)]
    return e ? { kind: 'error', snap: { ...(e as Record<string, unknown>), fetchedAt } } : null
  }
  const kit = createSolveKit({
    endpoint: '/dashboard/api/board/solve',
    prefix: 'dsh-exec',
    candidates: sessionCandidates,
    current: currentSession,
    resolveSnapshot: (kind, identity) => snapshotFor(kind, identity),
    host: () => document.querySelector<HTMLElement>(BOARD_VIEW_SELECTOR) ?? undefined,
  })

  return () => {
    shell.dispose()
    kit.close()
    document.documentElement.removeAttribute(ACTIVE_ATTR)
  }
}