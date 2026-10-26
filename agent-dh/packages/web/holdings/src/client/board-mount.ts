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
import { pickParts, fetchPlanFor } from '../services/parts.js'
import {
  createSolveKit, type SolveCandidate, type SolveIdentity, type SolveKit, type SolveSnapshot,
} from '@pi-investment/solve-kit/client'

export interface BoardController {
  openBoard(): void
  closeBoard(): void
  toggleBoard(): void
  getSnapshot(): { boardOpen: boolean }
  refresh(): void
  /** 打开看板时的刷新：冷块不在手 → full，否则 hot */
  refreshOnOpen(): void
  switchAccount(accountName: string): void
  watchSwitch(key: string): void
  historyPageSwitch(page: number): void
  solveTask(btn?: HTMLElement): void
}

/** 右栏 tab 正文宿主：页面单实例，挂载时赋值、卸载时清空。 */
let boardHost: HTMLElement | undefined

export function createBoardController(): BoardController {
  let currentAccount = 'agent_brain'
  let watchKey = 'current'
  let historyPage = 0
  let lastData: HoldingsData | undefined
  let shellRef: { open(): void; close(): void; toggle(): void; isActive(): boolean } | undefined
  let renderRetryTimer: number | undefined

  // 2026-09-13（w-adb088f2）：整包 82 KB 里 94.8% 是盯盘规则（54 条），却每 15 秒重传一次，
  // 页面因此"卡住"。现改为分块拉取：轮询只带 parts=hot（约 2.6 KB），每第 4 次轮询补一次全量
  // （约 60s）以刷新盯盘规则与成交明细。
  //
  // 2026-09-13 二次修正（同窗口，同一处）：分块必须和"什么时候取数"一起看——
  // ① 旧代码在 **mount** 时调 refresh()，而 refresh 第 1 次恰好判成 full（pollTick % 4 === 1）
  //    → 整天没点开看板也白拉一次 77 KB；原注释"第 1 次（打开看板）必为全量"并不成立
  //    （refresh 是在 mount 调用的，不是 open）。
  // ② 打开看板反而不取数（没接 onOpen）→ 看到的是挂载那一刻的旧数据。
  // 现在：open 按"冷块是否在手"决定 full/hot；轮询沿用每 4 次补一次 full。
  //
  // 2026-09-13 三次修正（w-ae7eb4c0，REQ-6cbbf7）：上一版把"没看也拉全量"改成"挂载预热 hot"，
  // 但**挂载本身就不是用户在看**（容器启动即挂载，靠 html[data-dsh-hld-active] 显隐），
  // 未点击就发请求 = 仍然是"打开前加载"；且 parts=hot 只缩小响应体，host 仍扇出 4 个上游，
  // 这 2.6 KB 换不来任何服务端节省。故**挂载不再取数**：取数时机统一由 fetchPlanFor 决定
  // （mount → null），首次打开时 lastData=undefined → 判成 full，一次把整包拿齐（看板不会空）。
  let pollTick = 0
  // 请求序号：只有最后一次发出的请求允许落地（防止旧响应覆盖新响应）
  let fetchSeq = 0
  const fetchAndRender = async (accountName: string, mode: 'full' | 'hot' = 'full'): Promise<void> => {
    const mySeq = ++fetchSeq
    const forAccount = accountName
    try {
      const url = '/dashboard/api/holdings?account=' + encodeURIComponent(accountName)
        + (mode === 'hot' ? '&parts=hot' : '')
      const res = await fetch(url)
      const json = await res.json()
      if (!json.success) throw new Error(json.error || 'Unknown error')
      const incoming = json.data as HoldingsData
      // 2026-09-13（w-adb088f2）两处修复：
      // ① 竞态：轮询（15s，hot 约 2.5 KB 很快）与切换账户（full 约 77 KB 较慢）并发时，
      //    先发出的**旧账户**响应可能后落地，把新账户数据覆盖回去（"切了又弹回去"）。
      //    分块把轮询变快后这个窗口被放大。故按请求序号 + 目标账户双重校验，过期响应一律丢弃。
      // ② 账户一致性：HOT_PARTS 曾漏掉 currentAccount，hot 响应不带它，合并后保留了上一个
      //    账户的值 —— 而下拉框的 selected 正是由 currentAccount 渲染的，于是出现
      //    「下拉框显示 A、数据是 B」。现在无论服务端是否回显，都以本次请求的账户为准。
      if (mySeq !== fetchSeq) {
        console.log('[dashboard-holdings] 丢弃过期响应（有更新的请求在后）: ' + forAccount)
        return
      }
      if (forAccount !== currentAccount) {
        console.log('[dashboard-holdings] 丢弃跨账户响应: ' + forAccount + '（当前 ' + currentAccount + '）')
        return
      }
      const merged: HoldingsData = lastData !== undefined
        ? ({ ...lastData, ...(pickParts(incoming as any, incoming.parts) as object), currentAccount: forAccount, parts: incoming.parts } as HoldingsData)
        : ({ ...incoming, currentAccount: forAccount, parts: incoming.parts } as HoldingsData)
      renderBoard(merged)
    } catch (error) {
      console.error('[dashboard-holdings] fetch failed:', error)
      renderError(String(error))
    }
  }

  const renderBoard = (data: HoldingsData): void => {
    lastData = data
    const view = boardHost
    if (!view) {
      // 2026-09-13（w-adb088f2）：这里原来是**静默 return**——容器没挂上时，数据已经取回来了
      // 却无处渲染：控制台干净、页面空白，故障被伪装成"没有数据"（用户实测：无账户下拉、
      // 控制台无报错）。与本次会话反复修复的"静默失败把它伪装成在工作"是同一类缺陷。
      // 现改为：显式报错 + 400ms 后重试一次（容器可能比数据晚一帧挂载）。
      console.error('[dashboard-holdings] 渲染失败：右栏看板容器尚未挂载 ' + BOARD_VIEW_SELECTOR
        + '（容器由页面挂载层在右侧栏 tab 里创建；找不到时数据会全部丢失）')
      if (renderRetryTimer === undefined) {
        renderRetryTimer = window.setTimeout(() => {
          renderRetryTimer = undefined
          const again = boardHost
          if (again) {
            console.log('[dashboard-holdings] 重试成功：容器已就绪，补渲染')
            again.innerHTML = buildView(data, watchKey, historyPage)
          } else {
            console.error('[dashboard-holdings] 重试仍失败：容器始终未出现 —— 看板将无法显示任何数据')
          }
        }, 400)
      }
      return
    }
    view.innerHTML = buildView(data, watchKey, historyPage)
    console.log('[dashboard-holdings] 已渲染：账户=' + (data.currentAccount ?? '?')
      + '，账户数=' + (data.accounts?.length ?? 0)
      + '，持仓行=' + (data.positions?.length ?? 0))
  }

  const renderError = (message: string): void => {
    const view = boardHost
    if (!view) return
    view.innerHTML = '<div class="dsh-hld-board"><div class="dsh-hld-wrap"><div class="dsh-hld-head"><h1 class="dsh-hld-title">持仓看板</h1></div><div class="dsh-hld-banner show">数据加载失败: ' + message + '</div></div></div>'
  }

  const watchSwitch = (key: string): void => {
    const k = String(key || 'current')
    if (k === watchKey) return
    watchKey = k
    if (!lastData) return
    const host = boardHost?.querySelector<HTMLElement>('#dsh-hld-watch') ?? null
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
    const host = boardHost?.querySelector<HTMLElement>('#dsh-hld-hx') ?? null
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
    // holdings「我来解决」直投 investor 主窗口，不弹选择器（2026-09-08 用户需求）
    return []
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
    refresh: () => {
      pollTick += 1
      const mode = fetchPlanFor('poll', pollTick, lastData)
      if (mode === null) return
      console.log('[dashboard-holdings] refresh (' + mode + ')')
      fetchAndRender(currentAccount, mode)
    },
    // 打开看板：冷块（盯盘规则/成交明细）不在手 → full 补齐；已在手 → 只拉 hot。
    // 首次打开 lastData=undefined → hasColdParts=false → full，一次把整包拿齐。
    refreshOnOpen: () => {
      pollTick = 0
      const mode = fetchPlanFor('open', 1, lastData)
      if (mode === null) return
      console.log('[dashboard-holdings] open refresh (' + mode + ')')
      fetchAndRender(currentAccount, mode)
    },
    switchAccount: (accountName) => {
      console.log('[dashboard-holdings] switching account to', accountName)
      currentAccount = accountName
      watchKey = 'current'
      historyPage = 0
      pollTick = 0
      // 冷块按账户过滤（盯盘规则带 account 字段），换账户必须整包重取
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

/**
 * Mount the holdings board into a host container (right-sidebar tab body).
 *
 * 打开时才挂载（tab 卸载即清理），首次挂载取一次全量数据，挂载期间 15s 轮询
 * （页面不可见时暂停）。内联 onclick 依赖的 window 全局函数在这里绑定/解绑。
 */
export function mountBoardView(controller: BoardController, container: HTMLElement): () => void {
  const host = document.createElement('div')
  host.setAttribute('data-dsh-hld-view', '')
  host.className = 'dsh-hld-view'
  container.appendChild(host)
  boardHost = host

  ;(window as any).__dshHldRefresh = () => controller.refresh()
  ;(window as any).__dshHldSwitchAccount = (accountName: string) => controller.switchAccount(accountName)
  ;(window as any).__dshHldWatchTab = (key: string) => controller.watchSwitch(String(key))
  ;(window as any).__dshHldHistoryPage = (page: unknown) => controller.historyPageSwitch(Number(page))
  ;(window as any).__dshHldSolveTask = (btn?: HTMLElement) => controller.solveTask(btn)

  // 打开看板时取数：冷块（盯盘规则/成交明细）不在手 → full 补齐；已在手 → 只拉 hot。
  controller.refreshOnOpen()

  const pollTimer = window.setInterval(() => {
    if (!document.hidden) controller.refresh()
  }, 15000)

  console.log('[dashboard-holdings] board mounted in right sidebar tab')

  return () => {
    window.clearInterval(pollTimer)
    delete (window as any).__dshHldRefresh
    delete (window as any).__dshHldSwitchAccount
    delete (window as any).__dshHldWatchTab
    delete (window as any).__dshHldHistoryPage
    delete (window as any).__dshHldSolveTask
    if (boardHost === host) boardHost = undefined
    host.remove()
    console.log('[dashboard-holdings] board unmounted')
  }
}
