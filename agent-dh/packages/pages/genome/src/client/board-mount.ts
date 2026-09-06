/**
 * Board controller + center-column mounting for the genome dashboard.
 *
 * Visibility is toggled via a data attribute on <html> plus cross-plugin
 * activation events — the dsh-taskboard contract (mirrors dashboard-execution).
 * Opening evicts every sibling panel's active attr; a passive listener on
 * dsh-panel-activate closes this board when ANOTHER panel activates (siblings
 * don't know about us, so we self-close instead of editing their arrays).
 *
 * @module dashboard-genome/client/board-mount
 */
import type { ApiResponse, GenomeData } from './types.ts'
import {
  BOARD_VIEW_SELECTOR, PANEL_NAME, ACTIVE_ATTR, OTHER_ACTIVE_ATTRS,
  ACTIVATE_EVENT, CONVERSATION_COLUMN_SELECTOR, conversationColumn,
} from './dom.ts'
import { buildView, renderAll, type ViewRefs } from './view.ts'

const GENOME_API = '/dashboard/api/genome'
const POLL_MS = 30000 // 全量刷新（基因组/candidates 变化低频，30s 足够）
let fetching = false

export interface BoardController {
  isActive(): boolean
  toggle(): void
  getSnapshot(): { boardOpen: boolean }
  openBoard(): void
  closeBoard(): void
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
  return {
    isActive: () => snap.boardOpen,
    toggle: () => { if (snap.boardOpen) close(); else open() },
    getSnapshot: () => snap,
    openBoard: open,
    closeBoard: close,
  }
}

/** Mount the board container + view into the center column; returns disposer. */
export function mountBoard(controller: BoardController): () => void {
  let refs: ViewRefs | undefined
  let container: HTMLDivElement | undefined
  let pollTimer: number | undefined
  let lastData: GenomeData | undefined
  let disposed = false

  // 中心列可能晚于 client apply() 出现（boot 时序）→ 启动即挂 + MutationObserver 兜底补挂
  // （dashboard-bulletin 实证范式）。容器常驻隐藏，点开只切 html[data-dsh-gen-active]。
  const ensure = (): void => {
    if (container !== undefined || disposed) return
    const column = conversationColumn()
    if (column === undefined) return
    container = document.createElement('div')
    container.className = 'dsh-gen-board'
    container.dataset.dshGenView = ''
    column.appendChild(container)
    refs = buildView()
    container.appendChild(refs.root)
    refs.refreshBtn?.addEventListener('click', () => { void fetchData() })
    // 显式「收起」按钮：看板点开后随时可一键回会话（不依赖点外部区域；点 = toggle，与入口同路径）
    const closeBtn = document.createElement('button')
    closeBtn.type = 'button'
    closeBtn.className = 'dsh-gen-close'
    closeBtn.title = '收起看板，回到会话'
    closeBtn.textContent = '✕ 收起'
    closeBtn.addEventListener('click', () => { controller.toggle() })
    if (refs.head !== undefined) refs.head.insertBefore(closeBtn, refs.refreshBtn ?? null)
    void fetchData(true)
    console.log('[dashboard-genome] board container mounted')
  }
  const waitObserver = new MutationObserver(() => { ensure() })
  waitObserver.observe(document.body, { childList: true, subtree: true })
  ensure()

  async function fetchData(initial = false): Promise<void> {
    if (fetching || refs === undefined) return
    fetching = true
    try {
      const res = await fetch(GENOME_API, { headers: { Accept: 'application/json' } })
      const json = (await res.json()) as ApiResponse<GenomeData>
      if (!json.success || json.data === undefined) throw new Error(json.error ?? '接口失败')
      lastData = json.data
      renderAll(refs, json.data)
      refs.meta.textContent = '刷新于 ' + new Date().toLocaleTimeString() + ' · 数据 ' + (json.data.fetchedAt ? new Date(json.data.fetchedAt).toLocaleTimeString() : '')
    } catch (err) {
      if (refs === undefined) return
      refs.meta.textContent = '⚠️ 加载失败: ' + (err instanceof Error ? err.message : String(err))
      if (!initial && lastData !== undefined) renderAll(refs, lastData)
    } finally {
      fetching = false
    }
  }

  const startPoll = (): void => {
    if (pollTimer !== undefined) return
    pollTimer = window.setInterval(() => { void fetchData() }, POLL_MS)
  }
  const stopPoll = (): void => {
    if (pollTimer !== undefined) { window.clearInterval(pollTimer); pollTimer = undefined }
  }

  // 打开时：确保容器已挂（幂等）+ 开始轮询；关闭时：停止轮询（保留容器数据）。
  // 增强版 open/close/toggle 重绑定到 controller——sidebar-entry 运行时动态读
  // controller.toggle()，替换后入口点击即走增强路径。
  const rawOpen = controller.openBoard
  const rawClose = controller.closeBoard
  const openAndMount = (): void => { ensure(); startPoll(); rawOpen() }
  const closeAndStop = (): void => { stopPoll(); rawClose() }
  const ctrl = controller as unknown as Record<string, unknown>
  ctrl.openBoard = openAndMount
  ctrl.closeBoard = closeAndStop
  ctrl.toggle = (): void => { if (controller.isActive()) closeAndStop(); else openAndMount() }

  // 另一面板激活 → 关闭自己（被动互斥，避免与旧面板静态数组脱节）
  const onActivate = (event: Event): void => {
    const detail = (event as CustomEvent<string>).detail
    if (detail !== undefined && detail !== PANEL_NAME && controller.isActive()) closeAndStop()
  }
  window.addEventListener(ACTIVATE_EVENT, onActivate)

  // 打开时点看板以外任意区域 → 收起回会话（bulletin 语义，宽于原 data-pane=sidebar 一代收窄：
  // 三代侧栏布局下会话列表/新会话按钮可能不在 data-pane="sidebar"，收窄会点不中 → 回不去会话）。
  // 点入口本身走 entry 的 toggle（这里排除，避免与 toggle 重复）。
  const onDocClick = (event: MouseEvent): void => {
    if (!controller.isActive()) return
    const target = event.target as HTMLElement | null
    if (target === null) return
    if (target.closest('[data-dsh-gen-entry], [data-dsh-gen-view]') !== null) return
    closeAndStop()
  }
  document.addEventListener('click', onDocClick)

  return () => {
    disposed = true
    waitObserver.disconnect()
    stopPoll()
    window.removeEventListener(ACTIVATE_EVENT, onActivate)
    document.removeEventListener('click', onDocClick)
    container?.remove()
    container = undefined
    document.documentElement.removeAttribute(ACTIVE_ATTR)
  }
}
