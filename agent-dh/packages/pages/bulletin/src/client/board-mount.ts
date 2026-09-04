/**
 * 公告板控制器 + 中心栏挂载（RFC 013 §4/§7）。
 * - html[data-dsh-bbd-active] 显隐：打开时置自身 active、清掉其他看板 active（互斥），
 *   并广播 ACTIVATE_EVENT —— 持仓/执行等既有看板收到后自关；本板监听同事件，被开时自关。
 * - 30s 轮询（RFC §6）：仅数据变更整体重绘；状态 tab / kind pill / 翻页为纯视图切换——
 *   服务端按查询过滤后只局部替换 #dsh-bbd-posts + #dsh-bbd-pg（RFC D3），并同步 pill 激活态。
 * - 帖子手风琴展开集合独立维护：局部替换与轮询重绘后重新套用。
 * - 全局回调：__dshBbdRefresh / __dshBbdStatusTab / __dshBbdKind / __dshBbdPage。
 *
 * @module dashboard-bulletin/client/board-mount
 */
import { ACTIVE_ATTR, ACTIVATE_EVENT, BOARD_VIEW_SELECTOR, conversationColumn, OTHER_ACTIVE_ATTRS, PANEL_NAME } from './dom.js'
import { buildBoardHtml, buildPaginationHtml, buildPostsHtml } from './view.js'
import type { BulletinData, KindKey, StatusKey } from './types.js'

const PAGE_SIZE = 20

export interface BoardController {
  openBoard(): void
  closeBoard(): void
  toggleBoard(): void
  getSnapshot(): { boardOpen: boolean }
  refresh(): void
  statusTab(key: StatusKey): void
  kindTab(key: KindKey): void
  pageTo(page: number): void
  /** 帖子手风琴：展开/收起某帖全文与变更记录 */
  toggleExpanded(id: string): void
}

export function createBoardController(): BoardController {
  let boardOpen = false
  let status: StatusKey = 'active'
  let kind: KindKey = 'all'
  let page = 1
  const expanded = new Set<string>()
  let pollTimer: number | undefined

  const buildUrl = (): string => {
    const p = new URLSearchParams()
    p.set('status', status)
    if (kind !== 'all') p.set('kind', kind)
    p.set('page', String(page))
    p.set('page_size', String(PAGE_SIZE))
    return '/dashboard/api/bulletin/posts?' + p.toString()
  }

  const open = (): void => {
    if (boardOpen) return
    boardOpen = true
    console.log('[dashboard-bulletin] opening board')
    // 先清其他看板 active，再置自身（防两板同时显隐冲突）
    for (const attr of OTHER_ACTIVE_ATTRS) document.documentElement.removeAttribute(attr)
    document.documentElement.setAttribute(ACTIVE_ATTR, '')
    window.dispatchEvent(new CustomEvent(ACTIVATE_EVENT, { detail: PANEL_NAME }))
    startPolling()
    fetchAndRender()
  }

  const close = (): void => {
    if (!boardOpen) return
    boardOpen = false
    document.documentElement.removeAttribute(ACTIVE_ATTR)
    stopPolling()
  }

  const toggle = (): void => { if (boardOpen) close(); else open() }

  const refresh = (): void => { fetchAndRender() }

  /** 状态 tab / kind pill / 翻页：服务端过滤后局部替换卡根（不动 header/过滤条） */
  const applyPartial = (next: Partial<{ status: StatusKey; kind: KindKey; page: number }>): void => {
    if (next.status !== undefined && next.status !== status) { status = next.status; page = 1 }
    if (next.kind !== undefined && next.kind !== kind) { kind = next.kind; page = 1 }
    if (next.page !== undefined && Number(next.page) > 0 && Number(next.page) !== page) page = Math.trunc(Number(next.page))
    fetchPartial()
  }

  const fetchPartial = async (): Promise<void> => {
    try {
      const res = await fetch(buildUrl())
      const json: any = await res.json()
      if (!json?.success) throw new Error(json?.error || 'Unknown error')
      const data: BulletinData = json.data
      const postsHost = document.getElementById('dsh-bbd-posts')
      if (postsHost === null) { renderBoard(data); return } // 兜底：找不到卡根才整板重绘
      const frag = document.createElement('template')
      frag.innerHTML = buildPostsHtml(data.posts, expanded)
      const node = frag.content.firstElementChild as HTMLElement | null
      if (node === null) { renderBoard(data); return }
      postsHost.replaceWith(node)
      // 分页条同步替换
      const pg = document.getElementById('dsh-bbd-pg')
      const pgFrag = document.createElement('template')
      pgFrag.innerHTML = buildPaginationHtml(data)
      const pgNode = pgFrag.content.firstElementChild as HTMLElement | null
      if (pg !== null && pgNode !== null) pg.replaceWith(pgNode)
      else if (pgNode !== null) { pgFrag.content.lastChild && document.querySelector('.dsh-bbd-board .dsh-bbd-wrap')?.appendChild(pgFrag.content.lastChild) }
      // pill 激活态同步（attr 不重绘）
      document.querySelectorAll<HTMLElement>('[data-bbd-status]').forEach((el) => {
        el.classList.toggle('act', el.dataset.bbdStatus === status)
      })
      document.querySelectorAll<HTMLElement>('[data-bbd-kind]').forEach((el) => {
        el.classList.toggle('act', el.dataset.bbdKind === kind)
      })
    } catch (error) {
      console.error('[dashboard-bulletin] partial fetch failed:', error)
      renderError(String(error))
    }
  }

  const fetchAndRender = async (): Promise<void> => {
    try {
      const res = await fetch(buildUrl())
      const json: any = await res.json()
      if (!json?.success) throw new Error(json?.error || 'Unknown error')
      renderBoard(json.data as BulletinData)
    } catch (error) {
      console.error('[dashboard-bulletin] fetch failed:', error)
      renderError(String(error))
    }
  }

  const renderBoard = (data: BulletinData): void => {
    const view = document.querySelector(BOARD_VIEW_SELECTOR)
    if (!view) return
    view.innerHTML = buildBoardHtml(data, { status, kind, page }, expanded)
    syncExpanded()
  }

  const syncExpanded = (): void => {
    for (const id of expanded) {
      const card = document.querySelector<HTMLElement>('[data-bbd-id="' + CSS.escape(id) + '"]')
      if (card !== null) card.classList.add('exp')
    }
  }

  const renderError = (message: string): void => {
    const view = document.querySelector(BOARD_VIEW_SELECTOR)
    if (!view) return
    view.innerHTML =
      '<div class="dsh-bbd-board"><div class="dsh-bbd-wrap">' +
        '<div class="dsh-bbd-head"><h1 class="dsh-bbd-title">公告板</h1></div>' +
        '<div class="dsh-bbd-banner show">数据加载失败: ' + esc(message) + '</div>' +
      '</div></div>'
  }

  /** 卡片手风琴：点击帖子卡切换展开（内容/log 显示） */
  const toggleExpanded = (id: string): void => {
    if (expanded.has(id)) expanded.delete(id)
    else expanded.add(id)
    const card = document.querySelector<HTMLElement>('[data-bbd-id="' + CSS.escape(id) + '"]')
    if (card !== null) card.classList.toggle('exp', expanded.has(id))
  }

  const startPolling = (): void => {
    stopPolling()
    pollTimer = window.setInterval(() => { if (boardOpen) fetchAndRender() }, 30000)
  }
  const stopPolling = (): void => {
    if (pollTimer !== undefined) { clearInterval(pollTimer); pollTimer = undefined }
  }

  return {
    openBoard: open,
    closeBoard: close,
    toggleBoard: toggle,
    getSnapshot: () => ({ boardOpen }),
    refresh,
    statusTab: (k) => applyPartial({ status: k }),
    kindTab: (k) => applyPartial({ kind: k }),
    pageTo: (n) => applyPartial({ page: n }),
    toggleExpanded,
  }
}

const esc = (s: unknown): string =>
  String(s ?? '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m] ?? m))

/**
 * 中心栏挂载：把看板容器挂进 conversation 列（数据-dsh-bbd-view 尾随子节点）。
 * 列可能晚于 client apply() 出现（boot 时序）→ MutationObserver 兜底补挂。
 * 返回 disposer：注销事件监听/全局回调/定时器并移除容器。
 */
export function mountBoard(controller: BoardController): () => void {
  let container: HTMLDivElement | undefined

  const ensure = (): void => {
    if (container !== undefined) return
    const column = conversationColumn()
    if (column === undefined) return
    container = document.createElement('div')
    container.setAttribute('data-dsh-bbd-view', '')
    container.className = 'dsh-bbd-view'
    column.appendChild(container)
    console.log('[dashboard-bulletin] board container mounted')
  }
  const waitObserver = new MutationObserver(() => { ensure() })
  waitObserver.observe(document.body, { childList: true, subtree: true })
  ensure()

  // 全局回调（view 交互出口；同 holdings __dshHld* 惯例）
  ;(window as any).__dshBbdRefresh = () => controller.refresh()
  ;(window as any).__dshBbdStatusTab = (k: unknown) => controller.statusTab(String(k) as StatusKey)
  ;(window as any).__dshBbdKind = (k: unknown) => controller.kindTab(String(k) as KindKey)
  ;(window as any).__dshBbdPage = (p: unknown) => controller.pageTo(Number(p))

  // 其他看板激活 → 本板自关（互斥；ACTIVATE_EVENT 协议）
  const onOtherActivate = (event: Event): void => {
    const detail = (event as CustomEvent).detail
    if (detail !== PANEL_NAME && controller.getSnapshot().boardOpen) controller.closeBoard()
  }
  window.addEventListener(ACTIVATE_EVENT, onOtherActivate)

  // 点看板外任意区域关板（会话行是 div[role=treeitem]，不能用 button/a 判定）
  const onClickOutside = (event: MouseEvent): void => {
    if (!controller.getSnapshot().boardOpen) return
    const target = event.target as HTMLElement | null
    if (target === null) return
    if (target.closest('[data-dsh-bbd-view]') !== null) return
    if (target.closest('[data-dsh-bbd-entry]') !== null) return
    controller.closeBoard()
  }
  document.addEventListener('click', onClickOutside, true)

  // 看板内交互（捕获委托）：卡手风琴 + 状态/kind pill + 翻页 + 刷新
  const onBoardClick = (event: MouseEvent): void => {
    const target = event.target as HTMLElement | null
    if (target === null) return
    const card = target.closest<HTMLElement>('[data-dsh-bbd-id]')
    if (card !== null && card.dataset.dshBbdId) {
      controller.toggleExpanded(card.dataset.dshBbdId)
      return
    }
    const statusBtn = target.closest<HTMLElement>('[data-bbd-status]')
    if (statusBtn !== null && statusBtn.dataset.bbdStatus) {
      ;(window as any).__dshBbdStatusTab(statusBtn.dataset.bbdStatus)
      return
    }
    const kindBtn = target.closest<HTMLElement>('[data-bbd-kind]')
    if (kindBtn !== null && kindBtn.dataset.bbdKind) {
      ;(window as any).__dshBbdKind(kindBtn.dataset.bbdKind)
      return
    }
    const pgBtn = target.closest<HTMLElement>('[data-bbd-page]')
    if (pgBtn !== null && pgBtn.dataset.bbdPage) {
      ;(window as any).__dshBbdPage(pgBtn.dataset.bbdPage)
      return
    }
    if (target.closest('#dsh-bbd-refresh') !== null) {
      ;(window as any).__dshBbdRefresh()
    }
  }
  document.addEventListener('click', onBoardClick, true)

  return () => {
    window.removeEventListener(ACTIVATE_EVENT, onOtherActivate)
    document.removeEventListener('click', onClickOutside, true)
    document.removeEventListener('click', onBoardClick, true)
    waitObserver.disconnect()
    if (container !== undefined) container.remove()
    delete (window as any).__dshBbdRefresh
    delete (window as any).__dshBbdStatusTab
    delete (window as any).__dshBbdKind
    delete (window as any).__dshBbdPage
    console.log('[dashboard-bulletin] board unmounted')
  }
}