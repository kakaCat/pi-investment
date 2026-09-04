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
import { buildView, renderAll, type ViewRefs } from './view.ts'
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
      renderAll(refs, json.data as BoardData)
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
    document.documentElement.removeAttribute(ACTIVE_ATTR)
    container?.remove()
    container = undefined
    refs = undefined
  }
}
