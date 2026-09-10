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
import { buildView, renderAll, renderTasks, renderErrorPage, setTaskSel, setDomSel, setTaskPage, type ViewRefs, type ErrPageView } from './view.ts'
import { createSolveKit } from '@pi-investment/solve-kit/client'
import { createBoardShell } from '@pi-investment/page-kit/client'

const BOARD_API = '/dashboard/api/board'
const ERROR_LIST_API = '/dashboard/api/board/error-events'
const ERROR_ACTION_API = '/dashboard/api/board/error-action'
const ERR_PAGE_SIZE = 10
const POLL_MS = 30000
let fetching = false
let errLoading = false
const emptyErrCounts = { total: 0, open: 0, processing: 0, resolved: 0, ignored: 0 }

type EvAct = 'claim' | 'resolve' | 'ignore' | 'reopen'
async function postErrorAction(body: { id: string; action: EvAct; from_session?: string; note?: string }): Promise<{ ok: boolean; error?: string; message?: string }> {
  try {
    const res = await fetch(ERROR_ACTION_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const j = (await res.json().catch(() => ({}))) as { success?: boolean; data?: { message?: string }; error?: string }
    if (!res.ok && j.success === undefined) return { ok: false, error: 'HTTP ' + res.status }
    if (j.success === false) return { ok: false, error: j.error ?? '操作失败' }
    return { ok: true, message: j.data?.message ?? '已更新' }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

/** 复制文本到剪贴板：navigator.clipboard 优先，非安全上下文/被拒时回退 textarea + execCommand。
 *  2026-09-10（w-8f2c4cc5）：错误事件列表暴露可引用的完整事件 ID，供用户与 agent 对齐排查对象（REQ-2057bd）。 */
async function copyText(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch { /* 回退到 execCommand */ }
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.setAttribute('readonly', '')
    ta.style.position = 'fixed'
    ta.style.top = '-1000px'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch { return false }
}

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
  // 错误事件独立分页状态（单源 /dashboard/api/board/error-events）；claim/resolve/reopen 不改 last_seen → 行序稳定
  let errView: ErrPageView = { events: [], total: 0, page: 1, pageSize: ERR_PAGE_SIZE, active: '', counts: { ...emptyErrCounts } }
  const errSnapCache = new Map<string, { row: Record<string, unknown>; fetchedAt: string }>()

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
      const onRefresh = () => { void fetchBoard(); void fetchErrPage({ silent: true }) }
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
      // 错误事件区：Tabs(状态过滤) / 分页器 / 处置（claim→投递 / resolve / ignore / reopen）
      //   认领点击瞬间缓存行快照（errSnapCache）→ openPicker 后立即刷新当前页；
      //   snapshotFor 优先按 id 查缓存（claim 后行可能因状态过滤离页，索引会失效），兜底当前 errView 索引
      const onErrsClick = (ev: MouseEvent) => {
        const target = ev.target as Element
        if (refs === undefined) return
        // 事件 ID 徽标：点击复制完整 UUID（用户 2026-09-10 反馈"列表没 ID 无法描述问题"）
        const idChip = target.closest<HTMLElement>('.evid[data-evcopy]')
        if (idChip !== null) {
          const id = idChip.dataset.evcopy ?? ''
          if (id !== '') {
            // toast 第二参 ok 控制绿/红配色（solve-kit client.toast(text, ok)）
            void copyText(id).then((ok) => kit.toast(ok ? '✓ 已复制事件 ID：' + id : '⚠ 复制失败，请手动复制 ID：' + id, ok))
          }
          return
        }
        const etab = target.closest<HTMLElement>('.dsh-exec-tab[data-errst]')
        if (etab !== null) { errView = { ...errView, active: etab.dataset.errst ?? '', page: 1 }; void fetchErrPage(); return }
        const epg = target.closest<HTMLElement>('.dsh-exec-tkpg [data-errpage]')
        if (epg !== null && !(epg as HTMLButtonElement).disabled) {
          const pg = Number((epg as HTMLButtonElement).dataset.errpage)
          if (!Number.isNaN(pg) && pg >= 1) { errView = { ...errView, page: Math.trunc(pg) }; void fetchErrPage() }
          return
        }
        const solveBtn = target.closest<HTMLElement>('.dsh-exec-solve[data-solve-err]')
        if (solveBtn !== null && solveBtn.dataset.solveErr !== undefined) {
          const idx = Number(solveBtn.dataset.solveErr)
          let ev = errView.events[idx]
          if (ev?.id === undefined && solveBtn.dataset.evid) ev = errView.events.find((x) => String(x.id) === String(solveBtn.dataset.evid))
          if (ev?.id === undefined) return
          errSnapCache.set(String(ev.id), { row: { ...(ev as unknown as Record<string, unknown>), fetchedAt: lastBoard?.fetchedAt ?? '' }, fetchedAt: lastBoard?.fetchedAt ?? '' })
          if (errSnapCache.size > 60) { const k = errSnapCache.keys().next().value; if (k !== undefined) errSnapCache.delete(k) }
          void (async () => {
            const r = await postErrorAction({ id: ev.id, action: 'claim', from_session: currentSession() })
            if (!r.ok) { kit.toast('⚠ 认领失败：' + (r.error ?? '')); return }
            kit.openPicker(solveBtn, 'error', { index: idx, id: ev.id })
            void fetchErrPage({ silent: true })
          })()
          return
        }
        const actBtn = target.closest<HTMLElement>('.dsh-exec-evact[data-evid][data-evact]')
        if (actBtn !== null) {
          const id = actBtn.dataset.evid
          const act = actBtn.dataset.evact as EvAct | undefined
          if (id === undefined || act === undefined) return
          // P1（2026-09-10）：resolve/ignore 必填结构化结论，结论会展示在事件卡片上
          let note: string | undefined
          if (act === 'resolve' || act === 'ignore') {
            const hint = act === 'resolve'
              ? '处置结论（≥10字）：根因 + 动作 + 证据\n例：根因=Python3.13移除timeout参数；动作=thread_pool.py改cancel_futures；证据=pytest PASS'
              : '忽略理由（≥10字）：为何误报 / 无需处置'
            const input = window.prompt(hint)
            if (input === null) return // 用户取消
            note = input.trim()
            if ([...note].length < 10) { kit.toast('⚠ 结论太短（≥10字），未提交'); return }
          }
          void (async () => {
            const r = await postErrorAction({ id, action: act, from_session: currentSession(), note })
            kit.toast(r.ok ? '✓ ' + (r.message ?? '已更新') : '⚠ ' + (r.error ?? '操作失败'))
            if (r.ok) void fetchErrPage({ silent: true })
          })()
        }
      }
      refs.errsBox.addEventListener('click', onErrsClick)
      void fetchBoard(true)
      void fetchErrPage()
      return () => {
        refreshBtn?.removeEventListener('click', onRefresh)
        refs.tasksBox.removeEventListener('click', onTasksClick)
        refs.errsBox.removeEventListener('click', onErrsClick)
      }
    },
    onPoll: () => { void fetchBoard(); void fetchErrPage({ silent: true }) },
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

  // 错误事件分页加载：GET /dashboard/api/board/error-events?status=&page=&pageSize=
  // 成功 → 更新 errView 并重绘；失败 → 区内 banner（silent 时不弹 toast，避免 30s 轮询刷屏）
  async function fetchErrPage(opts?: { silent?: boolean }): Promise<void> {
    if (errLoading) return
    errLoading = true
    const snap = errView
    try {
      const qs = new URLSearchParams()
      if (snap.active) qs.set('status', snap.active)
      qs.set('page', String(snap.page))
      qs.set('pageSize', String(snap.pageSize))
      const res = await fetch(ERROR_LIST_API + '?' + qs.toString(), { headers: { Accept: 'application/json' } })
      if (!res.ok) throw new Error('HTTP ' + res.status)
      const json = (await res.json()) as { success?: boolean; data?: { events?: any[]; total?: number; page?: number; counts?: any }; error?: string }
      if (!json.success || json.data === undefined) throw new Error(json.error ?? 'API 返回失败')
      if (refs === undefined) return
      errView = {
        events: Array.isArray(json.data.events) ? (json.data.events as any) : [],
        total: Number(json.data.total ?? snap.total),
        page: Math.max(1, Number(json.data.page ?? snap.page)),
        pageSize: snap.pageSize,
        active: snap.active,
        counts: { ...emptyErrCounts, ...(json.data.counts ?? {}) },
        error: undefined,
      }
      renderErrorPage(refs, errView)
    } catch (e) {
      const msg = String(e && (e as Error).message ? (e as Error).message : e)
      if (!opts?.silent) kit.toast('⚠ 错误事件加载失败：' + msg)
      if (refs === undefined) return
      errView = { ...errView, error: msg }
      renderErrorPage(refs, errView)
    } finally {
      errLoading = false
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
  const snapshotFor = (kind: 'task' | 'error', identity: { name?: string; index?: number; id?: string }): { kind: 'task' | 'error'; snap: Record<string, unknown> } | null => {
    if (kind === 'task') {
      if (lastBoard === undefined) return null
      const fetchedAt = lastBoard.fetchedAt ?? ''
      const t = (lastBoard.tasks ?? []).find((x) => String(x.name) === identity.name)
      return t ? { kind: 'task', snap: { ...(t as Record<string, unknown>), fetchedAt } } : null
    }
    // 错误事件：优先认领瞬间缓存（claim 后行可能因状态过滤离页）；兜底当前 errView 行索引
    const fetchedAt = lastBoard?.fetchedAt ?? ''
    if (identity.id !== undefined) {
      const c = errSnapCache.get(String(identity.id))
      if (c) return { kind: 'error', snap: c.row }
    }
    const e = errView.events[Number(identity.index ?? -1)]
    return e ? { kind: 'error', snap: { ...(e as unknown as Record<string, unknown>), fetchedAt } } : null
  }
  const kit = createSolveKit({
    endpoint: '/dashboard/api/board/solve',
    prefix: 'dsh-exec',
    candidates: sessionCandidates,
  online: async () => {
    try {
      const res = await fetch('/dashboard/api/board/online-windows')
      const j = (await res.json()) as { data?: { online?: unknown } }
      return Array.isArray(j?.data?.online) ? (j.data.online as string[]).map(String) : []
    } catch { return [] }
  },
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