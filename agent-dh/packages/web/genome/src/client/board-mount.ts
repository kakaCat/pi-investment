/**
 * Board view mounting for the genome dashboard — the view now lives inside the
 * DSH right sidebar (a native sidebarRight tab), not in the center column.
 *
 * Lifecycle: page-kit's registerRightTab owns the tab; this module only mounts
 * the DOM view into the tab's host container, starts polling while mounted and
 * returns the cleanup. The old center-column board shell (html[data-dsh-gen-active]
 * hides the conversation column) is gone — see registerRightTab.
 *
 * @module dashboard-genome/client/board-mount
 */
import type { ApiResponse, GenomeData } from './types.ts'
import { buildView, renderAll, type ViewRefs } from './view.ts'

const GENOME_API = '/dashboard/api/genome'
const POLL_MS = 30000

/**
 * Mount the genome board DOM into a host container (right-sidebar tab body).
 *
 * @param container - tab body host (page-kit provides it)
 * @returns cleanup: clears polling, unbinds listeners and removes the DOM
 */
export function mountBoardView(container: HTMLElement): () => void {
  const refs: ViewRefs = buildView()
  container.appendChild(refs.root)

  let lastData: GenomeData | undefined
  let fetching = false
  let disposed = false
  let pollTimer: number | undefined

  const fetchData = async (initial = false): Promise<void> => {
    if (fetching || disposed) return
    fetching = true
    try {
      const res = await fetch(GENOME_API, { headers: { Accept: 'application/json' } })
      const json = (await res.json()) as ApiResponse<GenomeData>
      if (!json.success || json.data === undefined) throw new Error(json.error ?? '接口失败')
      if (disposed) return
      lastData = json.data
      renderAll(refs, json.data)
      refs.meta.textContent = '刷新于 ' + new Date().toLocaleTimeString() + ' · 数据 ' + (json.data.fetchedAt ? new Date(json.data.fetchedAt).toLocaleTimeString() : '')
    } catch (err) {
      if (disposed) return
      refs.meta.textContent = '⚠️ 加载失败: ' + (err instanceof Error ? err.message : String(err))
      if (!initial && lastData !== undefined) renderAll(refs, lastData)
    } finally {
      fetching = false
    }
  }

  const onRefresh = (): void => { void fetchData() }
  refs.refreshBtn?.addEventListener('click', onRefresh)

  // 首次挂载即取数（tab 打开时才挂载，等价于「打开时加载」）
  void fetchData(true)
  pollTimer = window.setInterval(() => {
    if (!document.hidden && !disposed) void fetchData()
  }, POLL_MS)

  return () => {
    disposed = true
    if (pollTimer !== undefined) { clearInterval(pollTimer); pollTimer = undefined }
    refs.refreshBtn?.removeEventListener('click', onRefresh)
    refs.root.remove()
  }
}
