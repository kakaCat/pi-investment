/**
 * 看板生命周期壳 —— 所有 DSH GUI page 共享。
 * 职责：容器挂载（MutationObserver 兜底）、面板状态、互斥协议、轮询、外部点击关闭、dispose。
 * 页面只需提供 buildContainer / onMount / onPoll 等回调。
 *
 * @module page-kit/client/board-shell
 */
import { conversationColumn, ACTIVATE_EVENT } from './dom.js'

export interface BoardShellDeps {
  /** CSS/数据集前缀，如 'dsh-gen' */
  prefix: string
  /** 面板名称（ACTIVATE_EVENT detail） */
  panelName: string
  /** html[data-xxx-active] 属性名 */
  activeAttr: string
  /** 兄弟面板的 active 属性列表（打开时清除） */
  otherActiveAttrs: string[]
  /** 轮询间隔（毫秒），默认 30000 */
  pollMs?: number
  /** 是否在当前页不可见时暂停轮询（visibilitychange） */
  pauseOnHidden?: boolean
  /** ACTIVATE_EVENT 分发目标，默认 'window' */
  dispatchTarget?: 'window' | 'document'
  /** ACTIVATE_EVENT 监听目标，默认 'window' */
  listenTarget?: 'window' | 'document'
  /** 创建容器元素（由页面设置 className / dataset） */
  buildContainer(): HTMLElement
  /**
   * 容器已挂载到中心列后调用；页面在此构建视图、绑定事件。
   * 返回可选的清理函数（dispose 时调用）。
   */
  onMount(container: HTMLElement): (() => void) | void
  /** 轮询回调；仅在面板打开时调用 */
  onPoll(): void
  /** 面板打开时调用（每次打开都调） */
  onOpen?(): void
  /** 面板关闭时调用 */
  onClose?(): void
}

export interface BoardShell {
  open(): void
  close(): void
  toggle(): void
  isActive(): boolean
  dispose(): void
}

export function createBoardShell(deps: BoardShellDeps): BoardShell {
  const {
    panelName,
    activeAttr,
    otherActiveAttrs,
    pollMs = 30000,
    pauseOnHidden = false,
    dispatchTarget = 'window',
    listenTarget = 'window',
    buildContainer,
    onMount,
    onPoll,
    onOpen,
    onClose,
  } = deps

  let boardOpen = false
  let container: HTMLElement | undefined
  let pollTimer: number | undefined
  let mountCleanup: (() => void) | undefined
  let disposed = false

  // ---- 容器挂载（MutationObserver 兜底） ----
  const ensureMounted = (): void => {
    if (container !== undefined || disposed) return
    const column = conversationColumn()
    if (column === undefined) return
    const el = buildContainer()
    column.appendChild(el)
    container = el
    mountCleanup = onMount(el) ?? undefined
  }
  const waitObserver = new MutationObserver(() => { ensureMounted() })
  waitObserver.observe(document.body, { childList: true, subtree: true })
  ensureMounted()

  // ---- 互斥与状态 ----
  const open = (): void => {
    if (boardOpen || disposed) return
    boardOpen = true
    ensureMounted()
    for (const attr of otherActiveAttrs) document.documentElement.removeAttribute(attr)
    document.documentElement.setAttribute(activeAttr, '')
    const target = dispatchTarget === 'document' ? document : window
    target.dispatchEvent(new CustomEvent(ACTIVATE_EVENT, { detail: panelName }))
    startPolling()
    onOpen?.()
  }

  const close = (): void => {
    if (!boardOpen || disposed) return
    boardOpen = false
    document.documentElement.removeAttribute(activeAttr)
    stopPolling()
    onClose?.()
  }

  const toggle = (): void => { boardOpen ? close() : open() }
  const isActive = (): boolean => boardOpen

  // ---- 轮询 ----
  const tick = (): void => { if (boardOpen) onPoll() }
  const startPolling = (): void => {
    stopPolling()
    pollTimer = window.setInterval(tick, pollMs)
  }
  const stopPolling = (): void => {
    if (pollTimer !== undefined) { clearInterval(pollTimer); pollTimer = undefined }
  }

  // ---- visibilitychange（可选） ----
  const onVisibility = (): void => {
    if (document.hidden) stopPolling()
    else if (boardOpen) startPolling()
  }
  if (pauseOnHidden) document.addEventListener('visibilitychange', onVisibility)

  // ---- 外部点击关闭 ----
  const onDocClick = (ev: MouseEvent): void => {
    if (!boardOpen) return
    const t = ev.target as Element | null
    if (t === null) return
    // 点在看板容器内 → 不关
    if (container !== undefined && (container === t || container.contains(t))) return
    // 点在侧栏入口上 → 不关（避免 toggle 冲突）
    const entrySel = '[data-' + deps.prefix + '-entry]'
    if (t.closest(entrySel) !== null) return
    close()
  }
  document.addEventListener('click', onDocClick, true)

  // ---- 其他面板激活 → 自关 ----
  const onOtherActivate = (ev: Event): void => {
    const detail = (ev as CustomEvent).detail
    if (detail !== undefined && detail !== panelName && boardOpen) close()
  }
  const listenTargetEl = listenTarget === 'document' ? document : window
  listenTargetEl.addEventListener(ACTIVATE_EVENT, onOtherActivate)

  // ---- dispose ----
  const dispose = (): void => {
    if (disposed) return
    disposed = true
    stopPolling()
    if (pauseOnHidden) document.removeEventListener('visibilitychange', onVisibility)
    document.removeEventListener('click', onDocClick, true)
    listenTargetEl.removeEventListener(ACTIVATE_EVENT, onOtherActivate)
    waitObserver.disconnect()
    mountCleanup?.()
    container?.remove()
    container = undefined
  }

  return { open, close, toggle, isActive, dispose }
}
