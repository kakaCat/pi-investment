/**
 * Board view mounting: container appended inside the center column (trailing
 * child React never manages), visibility toggled via a data attribute on
 * <html> + cross-plugin activation events — the dsh-taskboard contract.
 *
 * @module dashboard-execution/client/board-mount
 */
import type { ApiResponse, BoardData } from './types.ts'
import {
  BOARD_VIEW_SELECTOR, PANEL_NAME, ACTIVE_ATTR, OTHER_ACTIVE_ATTRS,
  ACTIVATE_EVENT, CONVERSATION_COLUMN_SELECTOR,
} from './dom.ts'
import { buildView, renderAll, renderTasks, setTaskSel, setDomSel, setTaskPage, type ViewRefs } from './view.ts'
import { ENTRY_SELECTOR } from './dom.ts'

const BOARD_API = '/dashboard/api/board'
const POLL_MS = 30000   // 全量刷新
let fetching = false

/** 控制面：sidebar-entry 只消费 isActive/toggle；board 内部用其余方法 */
export interface BoardController {
  isActive(): boolean
  toggle(): void
  getSnapshot(): { boardOpen: boolean }
  openBoard(): void
  closeBoard(): void
  toggleBoard(): void
}

export function createBoardController(): BoardController {
  const snap = { boardOpen: false }
  const open = (): void => { snap.boardOpen = true; sync() }
  const close = (): void => { snap.boardOpen = false; sync() }
  const sync = (): void => {
    if (snap.boardOpen) {
      for (const attr of OTHER_ACTIVE_ATTRS) document.documentElement.removeAttribute(attr)
      document.documentElement.setAttribute(ACTIVE_ATTR, '')
      document.dispatchEvent(new CustomEvent(ACTIVATE_EVENT, { detail: PANEL_NAME }))
    } else {
      document.documentElement.removeAttribute(ACTIVE_ATTR)
    }
  }
  const controller: BoardController = {
    isActive: () => snap.boardOpen,
    toggle: () => { if (snap.boardOpen) close(); else open() },
    getSnapshot: () => snap,
    openBoard: open,
    closeBoard: close,
    toggleBoard: () => { if (snap.boardOpen) close(); else open() },
  }
  return controller
}

/** Mount the board into the center column and start polling. Returns disposer. */
export function mountBoard(controller: BoardController): () => void {
  let refs: ViewRefs | undefined
  let container: HTMLDivElement | undefined
  let pollTimer = 0
  let refreshBtn: HTMLButtonElement | undefined
  let lastBoard: BoardData | undefined

  const ensure = (): void => {
    if (container !== undefined) return
    const column = document.querySelector<HTMLElement>(CONVERSATION_COLUMN_SELECTOR)
    if (column === null) return
    container = document.createElement('div')
    container.dataset.dshExecView = ''
    container.className = 'dsh-exec-view'
    column.appendChild(container)
    refs = buildView()
    container.appendChild(refs.board)
    refreshBtn = container.querySelector<HTMLButtonElement>('[data-role="refresh"]') ?? undefined
    refreshBtn?.addEventListener('click', () => { void fetchBoard() })
    // 调度任务点击：分类 pill tab 切换 / 任务行选中看详情（委派监听，重绘 innerHTML 不影响容器）
    refs.tasksBox.addEventListener('click', (ev) => {
      const target = ev.target as Element
      if (lastBoard === undefined || refs === undefined) return
      // 「我来解决」：失败任务行按钮 → 窗口选择器投递（先于行选中判定，阻止误选详情）
      const solveBtn = target.closest<HTMLElement>('.dsh-exec-solve[data-solve-task]')
      if (solveBtn !== null && solveBtn.dataset.solveTask !== undefined) {
        openSolvePicker(solveBtn, { kind: 'task', name: solveBtn.dataset.solveTask })
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
    })
    // 错误事件条「我来解决」→ 窗口选择器投递（同 board 语义）
    refs.errsBox.addEventListener('click', (ev) => {
      const solveBtn = (ev.target as Element).closest<HTMLElement>('.dsh-exec-solve[data-solve-err]')
      if (solveBtn !== null && solveBtn.dataset.solveErr !== undefined) {
        openSolvePicker(solveBtn, { kind: 'error', index: Number(solveBtn.dataset.solveErr) })
      }
    })
    void fetchBoard(true)
  }
  const waitObserver = new MutationObserver(() => { ensure() })
  waitObserver.observe(document.body, { childList: true, subtree: true })

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

  // ---------- 「我来解决」：窗口选择器投递（solve，只投递不建帖） ----------
  let solvePop: HTMLDivElement | undefined
  let solveDocClean: (() => void) | undefined
  const closeSolvePop = (): void => {
    solveDocClean?.()
    solveDocClean = undefined
    if (solvePop !== undefined) { solvePop.remove(); solvePop = undefined }
  }
  const toast = (text: string, ok: boolean): void => {
    const el = document.createElement('div')
    el.className = 'dsh-exec-toast ' + (ok ? 'ok' : 'err')
    el.textContent = text
    document.body.appendChild(el)
    window.setTimeout(() => { el.classList.add('out'); window.setTimeout(() => el.remove(), 350) }, 4200)
  }
  /** 会话源懒取（与左栏同源；apply 未注入完成时经 ctx 重取），归档/子代理过滤 */
  const sessionCandidates = (): { sid: string; label: string; current: boolean }[] => {
    const w = window as any
    let fac = w.__dshExecSessions
    if (!fac?.list) { try { fac = w.__dshExecCtx?.sessions; if (fac?.list) w.__dshExecSessions = fac } catch { /* noop */ } }
    let archived: Set<string> | null = null
    try {
      const ar = w.__dshExecWorkspaces?.list?.getSnapshot?.()?.archivedSessionIds
      if (Array.isArray(ar)) archived = new Set(ar.map(String))
    } catch { /* workspaces 降级 → 无归档过滤 */ }
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
    } catch { /* sessions 降级 → 空候选 */ }
    return out
  }
  const currentSession = (): string => {
    try { return String((window as any).__dshExecSessions?.list?.getSnapshot?.()?.current ?? '') } catch { return '' }
  }
  /** 从 lastBoard 解析投递快照（task 按 name；error 按下标）；列表已刷新则 null */
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
  /** POST /dashboard/api/board/solve（host 路由：自包含消息 → 目标 agent.followup） */
  const postSolve = async (kind: 'task' | 'error', snap: Record<string, unknown>, toSession?: string): Promise<void> => {
    const from = currentSession()
    try {
      const res = await fetch('/dashboard/api/board/solve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind, task: kind === 'task' ? snap : undefined, err: kind === 'error' ? snap : undefined, from_session: from || undefined, to_session: toSession }),
      })
      const j = await res.json().catch(() => null)
      if (j === null || j.success !== true) { toast('投递失败：' + String(j?.error ?? 'HTTP ' + res.status), false); return }
      const d = j.data as { delivered?: boolean; note?: string; error?: string } | undefined
      toast(d?.delivered === true ? '✓ ' + String(d?.note ?? '已投递') : '⚠ ' + String(d?.error ?? j.error ?? '投递失败'), d?.delivered === true)
    } catch (e) {
      toast('请求异常：' + String(e instanceof Error ? e.message : e), false)
    }
  }
  /** 点「我来解决」：弹窗口选择器（默认当前窗口在首，current 标记）；无候选时直接投递主窗口 */
  const openSolvePicker = (anchor: HTMLElement, kind: 'task' | 'error', identity: { name?: string; index?: number }): void => {
    const target = snapshotFor(kind, identity)
    if (target === null) { toast('⚠ 数据已刷新，请重试', false); return }
    closeSolvePop()
    const cands = sessionCandidates()
    if (cands.length === 0) { void postSolve(target.kind, target.snap); return }
    const pop = document.createElement('div')
    pop.className = 'dsh-exec-solvepop'
    const head = document.createElement('div')
    head.className = 'dsh-exec-solvepop-head'
    head.textContent = '投递给窗口排查处置'
    pop.appendChild(head)
    const list = document.createElement('div')
    list.className = 'dsh-exec-solvepop-list'
    for (const c of cands) {
      const b = document.createElement('button')
      b.type = 'button'
      b.className = 'dsh-exec-solvepop-item' + (c.current ? ' cur' : '')
      b.textContent = (c.current ? '● ' : '○ ') + c.label
      b.addEventListener('click', () => { closeSolvePop(); void postSolve(target.kind, target.snap, c.sid) })
      list.appendChild(b)
    }
    pop.appendChild(list)
    const cancel = document.createElement('button')
    cancel.type = 'button'
    cancel.className = 'dsh-exec-solvepop-cancel'
    cancel.textContent = '取消'
    cancel.addEventListener('click', closeSolvePop)
    pop.appendChild(cancel)
    ;(container ?? document.body).appendChild(pop)
    solvePop = pop
    // 定位：锚点下方（放不下则上方），视口内
    const rect = anchor.getBoundingClientRect()
    const popH = 40 + cands.length * 30 + 32
    let top = rect.bottom + 6
    if (top + popH > window.innerHeight) top = Math.max(6, rect.top - popH - 6)
    pop.style.position = 'fixed'
    pop.style.left = Math.min(rect.left, Math.max(6, window.innerWidth - 280)) + 'px'
    pop.style.top = top + 'px'
    // 点开后的任意外部点击关闭
    const onDoc = (ev: MouseEvent): void => {
      const t = ev.target as Element | null
      if (t !== null && pop.contains(t)) return
      document.removeEventListener('click', onDoc, true)
      solveDocClean = undefined
      closeSolvePop()
    }
    document.addEventListener('click', onDoc, true)
    solveDocClean = () => document.removeEventListener('click', onDoc, true)
  }

  // 激活监听：别的面板激活时本板关闭
  const onOtherActivate = (event: Event): void => {
    const detail = (event as CustomEvent).detail
    if (detail !== PANEL_NAME && controller.getSnapshot().boardOpen) controller.closeBoard()
  }
  // 点侧栏会话行时关板（本入口自身子树豁免）
    // 关板：点击任何非本板/本入口（footer 按钮）的区域即关闭——会话行是 role=treeitem 的 div，
  // 不能按 button/a/role=button 判定，宽松匹配保证点会话行/工作区后会话内容立刻可见
  const onClickOutside = (event: MouseEvent): void => {
    if (!controller.getSnapshot().boardOpen) return
    const target = event.target as HTMLElement | null
    if (target === null) return
    if (target.closest(BOARD_VIEW_SELECTOR) !== null) return
    if (target.closest(ENTRY_SELECTOR) !== null) return
    if (target.closest('[class*="dsh-exec-foot"]') !== null) return
    controller.closeBoard()
  }
  document.addEventListener('click', onClickOutside, true)
  document.addEventListener(ACTIVATE_EVENT, onOtherActivate)
  const startPoll = (): void => {
    if (pollTimer !== 0) window.clearInterval(pollTimer)
    pollTimer = window.setInterval(() => { void fetchBoard() }, POLL_MS)
  }
  const stopPoll = (): void => { if (pollTimer !== 0) { window.clearInterval(pollTimer); pollTimer = 0 } }
  const onVisibility = (): void => {
    if (document.hidden) stopPoll()
    else { startPoll(); void fetchBoard() }
  }
  document.addEventListener('visibilitychange', onVisibility)

  const applyActive = (): void => { ensure() }
  applyActive()
  startPoll()

  return () => {
    document.removeEventListener('click', onClickOutside, true)
    document.removeEventListener(ACTIVATE_EVENT, onOtherActivate)
    document.removeEventListener('visibilitychange', onVisibility)
    waitObserver.disconnect()
    stopPoll()
    closeSolvePop()
    document.documentElement.removeAttribute(ACTIVE_ATTR)
    container?.remove()
    container = undefined
    refs = undefined
  }
}
