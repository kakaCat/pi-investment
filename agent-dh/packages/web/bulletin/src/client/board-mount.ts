/**
 * 公告板控制器 + 中心栏挂载（RFC 013 §4/§7）。
 * 生命周期（互斥/轮询/挂载/外部点击/dispose）委托给 page-kit board-shell；
 * 页面保留业务状态（status/kind/page/expanded）、partial fetch、事件委托、转交逻辑。
 *
 * @module dashboard-bulletin/client/board-mount
 */
import { ACTIVE_ATTR, ACTIVATE_EVENT, BOARD_VIEW_SELECTOR, PANEL_NAME, OTHER_ACTIVE_ATTRS } from './dom.js'
import { buildBoardHtml, buildPaginationHtml, buildPostsHtml } from './view.js'
import { esc } from '@pi-investment/page-kit/client'
import type { BulletinData, KindKey, StatusKey } from './types.js'
import { createBoardShell, showToast } from '@pi-investment/page-kit/client'

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
  toggleExpanded(id: string): void
}

export function createBoardController(): BoardController {
  let status: StatusKey = 'active'
  let kind: KindKey = 'all'
  let page = 1
  const expanded = new Set<string>()
  let shellRef: { open(): void; close(): void; toggle(): void; isActive(): boolean; dispose(): void } | undefined

  const buildUrl = (): string => {
    const p = new URLSearchParams()
    p.set('status', status)
    if (kind !== 'all') p.set('kind', kind)
    p.set('page', String(page))
    p.set('page_size', String(PAGE_SIZE))
    return '/dashboard/api/bulletin/posts?' + p.toString()
  }

  const fetchPartial = async (): Promise<void> => {
    try {
      const res = await fetch(buildUrl())
      const json: any = await res.json()
      if (!json?.success) throw new Error(json?.error || 'Unknown error')
      const data: BulletinData = json.data
      const postsHost = document.getElementById('dsh-bbd-posts')
      if (postsHost === null) { renderBoard(data); return }
      const frag = document.createElement('template')
      frag.innerHTML = buildPostsHtml(data.posts, expanded)
      const node = frag.content.firstElementChild as HTMLElement | null
      if (node === null) { renderBoard(data); return }
      postsHost.replaceWith(node)
      const pg = document.getElementById('dsh-bbd-pg')
      const pgFrag = document.createElement('template')
      pgFrag.innerHTML = buildPaginationHtml(data)
      const pgNode = pgFrag.content.firstElementChild as HTMLElement | null
      if (pg !== null && pgNode !== null) pg.replaceWith(pgNode)
      else if (pgNode !== null) { pgFrag.content.lastChild && document.querySelector('.dsh-bbd-board .dsh-bbd-wrap')?.appendChild(pgFrag.content.lastChild) }
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

  const applyPartial = (next: Partial<{ status: StatusKey; kind: KindKey; page: number }>): void => {
    if (next.status !== undefined && next.status !== status) { status = next.status; page = 1 }
    if (next.kind !== undefined && next.kind !== kind) { kind = next.kind; page = 1 }
    if (next.page !== undefined && Number(next.page) > 0 && Number(next.page) !== page) page = Math.trunc(Number(next.page))
    fetchPartial()
  }

  return {
    openBoard: () => shellRef?.open(),
    closeBoard: () => shellRef?.close(),
    toggleBoard: () => shellRef?.toggle(),
    getSnapshot: () => ({ boardOpen: shellRef?.isActive() ?? false }),
    refresh: fetchAndRender,
    statusTab: (k) => applyPartial({ status: k }),
    kindTab: (k) => applyPartial({ kind: k }),
    pageTo: (n) => applyPartial({ page: n }),
    toggleExpanded: (id) => {
      if (expanded.has(id)) expanded.delete(id)
      else expanded.add(id)
      const card = document.querySelector<HTMLElement>('[data-bbd-id="' + CSS.escape(id) + '"]')
      if (card !== null) card.classList.toggle('exp', expanded.has(id))
    },
  }
}

export function mountBoard(controller: BoardController): () => void {
  // 全局回调（view 交互出口）
  ;(window as any).__dshBbdRefresh = () => controller.refresh()
  ;(window as any).__dshBbdStatusTab = (k: unknown) => controller.statusTab(String(k) as StatusKey)
  ;(window as any).__dshBbdKind = (k: unknown) => controller.kindTab(String(k) as KindKey)
  ;(window as any).__dshBbdPage = (p: unknown) => controller.pageTo(Number(p))

  const shell = createBoardShell({
    prefix: 'dsh-bbd',
    panelName: PANEL_NAME,
    activeAttr: ACTIVE_ATTR,
    otherActiveAttrs: OTHER_ACTIVE_ATTRS,
    pollMs: 30000,
    buildContainer: () => {
      const el = document.createElement('div')
      el.setAttribute('data-dsh-bbd-view', '')
      el.className = 'dsh-bbd-view'
      return el
    },
    onMount: () => {
      controller.refresh()
      // 看板内点击委托
      const onBoardClick = (event: MouseEvent): void => {
        const target = event.target as HTMLElement | null
        if (target === null) return
        const actBtn = target.closest<HTMLElement>('[data-bbd-solve],[data-bbd-delegate]')
        if (actBtn !== null) {
          const id = actBtn.closest<HTMLElement>('[data-bbd-id]')?.dataset.bbdId
          if (id) {
            if (actBtn.hasAttribute('data-bbd-solve')) void runAction(id, 'solve')
            else { const card = actBtn.closest<HTMLElement>('[data-bbd-id]'); if (card) togglePicker(card) }
          }
          return
        }
        if (target.closest('[data-bbd-pickclose]') !== null) { closePickers(); return }
        const pickBtn = target.closest<HTMLElement>('[data-bbd-picksession]')
        if (pickBtn !== null && pickBtn.dataset.bbdPicksession) {
          const id = pickBtn.closest<HTMLElement>('[data-bbd-id]')?.dataset.bbdId
          if (id) { closePickers(); void runAction(id, 'delegate', pickBtn.dataset.bbdPicksession) }
          return
        }
        const card = target.closest<HTMLElement>('[data-bbd-id]')
        if (card !== null && card.dataset.bbdId && target.closest('button') === null) {
          controller.toggleExpanded(card.dataset.bbdId)
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
      return () => { document.removeEventListener('click', onBoardClick, true) }
    },
    onPoll: () => controller.refresh(),
  })

  // 把 shell 接口挂到 controller（createBoardController 里的 shellRef 占位）
  const ctrl = controller as any
  ctrl.openBoard = shell.open
  ctrl.closeBoard = shell.close
  ctrl.toggleBoard = shell.toggle
  ctrl.getSnapshot = () => ({ boardOpen: shell.isActive() })

  return () => {
    shell.dispose()
    delete (window as any).__dshBbdRefresh
    delete (window as any).__dshBbdStatusTab
    delete (window as any).__dshBbdKind
    delete (window as any).__dshBbdPage
    console.log('[dashboard-bulletin] board unmounted')
  }
}

// ---------- 转交 / 认领工具函数（纯 DOM，无状态） ----------
const sessionCandidates = (): { sid: string; label: string; current: boolean }[] => {
  const w = window as any
  let fac = w.__dshBbdSessions
  if (!fac?.list) { try { fac = w.__dshBbdCtx?.sessions; if (fac?.list) w.__dshBbdSessions = fac } catch { } }
  let archived: Set<string> | null = null
  try {
    let wfac = w.__dshBbdWorkspaces
    if (!wfac?.list) { wfac = w.__dshBbdCtx?.workspaces }
    const ar = wfac?.list?.getSnapshot?.()?.archivedSessionIds
    if (Array.isArray(ar)) archived = new Set(ar.map(String))
  } catch { }
  const out: { sid: string; label: string; current: boolean }[] = []
  try {
    const snap = fac?.list?.getSnapshot?.()
    if (!snap) return out
    const cur = String(snap.current ?? '')
    const rows: any[] = Array.isArray(snap.items)
      ? snap.items
      : (Array.isArray(snap.ids) ? snap.ids.map((id: string) => snap.byId?.[id]).filter(Boolean) : [])
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

const closePickers = (): void => {
  document.querySelectorAll<HTMLElement>('[data-bbd-pick]:not([hidden])').forEach((p) => { p.hidden = true })
}

const togglePicker = (card: HTMLElement): void => {
  const pick = card.querySelector<HTMLElement>('[data-bbd-pick]')
  if (pick === null) return
  if (!pick.hidden) { pick.hidden = true; return }
  closePickers()
  const list = pick.querySelector<HTMLElement>('[data-bbd-picklist]')
  const cands = sessionCandidates()
  if (list !== null) {
    list.innerHTML = cands.length === 0
      ? '<div class="dsh-bbd-pick-empty">暂无可转窗口（会话列表为空或未就绪）——请稍候重试或点「我来解决」</div>'
      : cands.map((c) =>
          '<button type="button" class="dsh-bbd-picksession' + (c.current ? ' cur' : '') + '" data-bbd-picksession="' + esc(c.sid) + '">' +
            esc(c.label) + (c.current ? '<i>当前</i>' : '') +
          '</button>'
        ).join('')
  }
  pick.hidden = false
}

const runAction = async (postId: string, action: 'solve' | 'delegate', toSession?: string): Promise<void> => {
  let current = ''
  try { current = String((window as any).__dshBbdSessions?.list?.getSnapshot?.()?.current ?? '') } catch { }
  const btn = document.querySelector<HTMLElement>(
    '[data-bbd-id="' + CSS.escape(postId) + '"] [data-bbd-' + (action === 'solve' ? 'solve' : 'delegate') + ']')
  const prevLabel = btn?.textContent ?? ''
  if (btn !== null) { btn.disabled = true; btn.textContent = '处理中…' }
  showToast('正在' + (action === 'solve' ? '认领' : '转交') + '…', true, 'dsh-bbd')
  try {
    const res = await fetch('/dashboard/api/bulletin/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ post_id: postId, action, to_session: toSession, from_session: current || undefined }),
    })
    const j = await res.json().catch(() => null)
    if (j === null || j.success !== true) { showToast('动作失败：' + (j?.error ?? 'HTTP ' + res.status), false, 'dsh-bbd'); return }
    const delivered = j.data?.delivery?.delivered === true
    showToast((delivered ? '✓ ' : '⚠ ') + String(j.data?.note ?? '已认领，等待窗口闭环'), delivered, 'dsh-bbd')
    ;(window as any).__dshBbdRefresh?.()
  } catch (e) {
    showToast('请求异常：' + String(e instanceof Error ? e.message : e), false, 'dsh-bbd')
  } finally {
    if (btn !== null) { btn.disabled = false; btn.textContent = prevLabel }
  }
}