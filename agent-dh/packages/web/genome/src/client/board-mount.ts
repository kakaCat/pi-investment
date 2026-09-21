/**
 * Board controller + center-column mounting for the genome dashboard.
 * Delegated to page-kit board-shell for lifecycle; page only provides
 * buildContainer / onMount / onPoll callbacks.
 *
 * @module dashboard-genome/client/board-mount
 */
import type { ApiResponse, GenomeData } from './types.ts'
import {
  PANEL_NAME, ACTIVE_ATTR, OTHER_ACTIVE_ATTRS,
  ACTIVATE_EVENT,
} from './dom.ts'
import { buildView, renderAll, type ViewRefs } from './view.ts'
import { createBoardShell } from '@pi-investment/page-kit/client'

const GENOME_API = '/dashboard/api/genome'
const POLL_MS = 30000
let fetching = false

export interface BoardController {
  isActive(): boolean
  toggle(): void
  getSnapshot(): { boardOpen: boolean }
  openBoard(): void
  closeBoard(): void
}

export function createBoardController(): BoardController {
  const ctrl: BoardController = {
    isActive: () => false,
    toggle: () => {},
    getSnapshot: () => ({ boardOpen: false }),
    openBoard: () => {},
    closeBoard: () => {},
  }
  return ctrl
}

export function mountBoard(controller: BoardController): () => void {
  let refs: ViewRefs | undefined
  let lastData: GenomeData | undefined

  const shell = createBoardShell({
    prefix: 'dsh-gen',
    panelName: PANEL_NAME,
    activeAttr: ACTIVE_ATTR,
    otherActiveAttrs: OTHER_ACTIVE_ATTRS,
    pollMs: POLL_MS,
    dispatchTarget: 'document',
    listenTarget: 'window',
    buildContainer: () => {
      const el = document.createElement('div')
      el.className = 'dsh-gen-board'
      el.dataset.dshGenView = ''
      return el
    },
    onMount: (container) => {
      refs = buildView()
      container.appendChild(refs.root)
      const onRefresh = () => { void fetchData() }
      refs.refreshBtn?.addEventListener('click', onRefresh)
      const closeBtn = document.createElement('button')
      closeBtn.type = 'button'
      closeBtn.className = 'dsh-gen-close'
      closeBtn.title = '收起看板，回到会话'
      closeBtn.textContent = '✕ 收起'
      const onClose = () => { shell.toggle() }
      closeBtn.addEventListener('click', onClose)
      if (refs.head !== undefined) refs.head.insertBefore(closeBtn, refs.refreshBtn ?? null)
      void fetchData(true)
      console.log('[dashboard-genome] board container mounted')
      return () => {
        refs.refreshBtn?.removeEventListener('click', onRefresh)
        closeBtn.removeEventListener('click', onClose)
      }
    },
    onPoll: () => { void fetchData() },
  })

  controller.isActive = shell.isActive
  controller.toggle = shell.toggle
  controller.openBoard = shell.open
  controller.closeBoard = shell.close
  controller.getSnapshot = () => ({ boardOpen: shell.isActive() })

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

  return () => {
    shell.dispose()
    document.documentElement.removeAttribute(ACTIVE_ATTR)
  }
}