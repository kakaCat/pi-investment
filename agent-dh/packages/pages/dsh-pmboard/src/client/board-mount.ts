/**
 * Minimal board mount for reqboard (step 1: placeholder view).
 */
import {
  ACTIVE_ATTR, CONVERSATION_COLUMN_SELECTOR, PANEL_NAME, ACTIVATE_EVENT,
} from './dom.ts'

export interface BoardController {
  getSnapshot(): { boardOpen: boolean }
  openBoard(): void
  closeBoard(): void
  toggleBoard(): void
}

export function createBoardController(): BoardController {
  const snap = { boardOpen: false }
  const sync = (): void => {
    if (snap.boardOpen) {
      document.documentElement.setAttribute(ACTIVE_ATTR, '')
      document.dispatchEvent(new CustomEvent(ACTIVATE_EVENT, { detail: PANEL_NAME }))
    } else {
      document.documentElement.removeAttribute(ACTIVE_ATTR)
    }
  }
  return {
    getSnapshot: () => snap,
    openBoard: () => { snap.boardOpen = true; sync() },
    closeBoard: () => { snap.boardOpen = false; sync() },
    toggleBoard: () => { snap.boardOpen = !snap.boardOpen; sync() },
  }
}

export function mountBoard(controller: BoardController): () => void {
  let container: HTMLDivElement | undefined

  const ensure = (): void => {
    if (container !== undefined) return
    const column = document.querySelector<HTMLElement>(CONVERSATION_COLUMN_SELECTOR)
    if (column === null) return
    container = document.createElement('div')
    container.dataset.dshReqboardView = ''
    container.className = 'dsh-reqboard-view'
    container.innerHTML = `
      <div class="dsh-reqboard-placeholder">
        <h2>项目看板</h2>
        <p>RFC 014 · 需求流水线插件</p>
        <p style="font-size:12px;color:#999">M3 开发中：泳道视图 / DAG / 待归类区 / 会话跳转</p>
      </div>
    `
    column.appendChild(container)
  }

  const observer = new MutationObserver(() => ensure())
  observer.observe(document.body, { childList: true, subtree: true })

  // Close when clicking outside
  const onClickOutside = (event: MouseEvent): void => {
    if (!controller.getSnapshot().boardOpen) return
    const target = event.target as HTMLElement | null
    if (!target) return
    if (target.closest('[data-dsh-reqboard-view]')) return
    if (target.closest('.dsh-reqboard-foot')) return
    controller.closeBoard()
  }
  document.addEventListener('click', onClickOutside, true)

  // Close when other panel activates
  const onOtherActivate = (event: Event): void => {
    const detail = (event as CustomEvent).detail
    if (detail !== PANEL_NAME && controller.getSnapshot().boardOpen) {
      controller.closeBoard()
    }
  }
  document.addEventListener(ACTIVATE_EVENT, onOtherActivate)

  ensure()

  return () => {
    document.removeEventListener('click', onClickOutside, true)
    document.removeEventListener(ACTIVATE_EVENT, onOtherActivate)
    observer.disconnect()
    document.documentElement.removeAttribute(ACTIVE_ATTR)
    container?.remove()
    container = undefined
  }
}
