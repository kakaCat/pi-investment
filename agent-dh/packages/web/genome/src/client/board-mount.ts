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
 * @param opts.isActive - 右栏 tab 激活态探测；非激活时暂停轮询，重新激活立即补数据
 * @returns cleanup: clears polling, unbinds listeners and removes the DOM
 */
export function mountBoardView(container: HTMLElement, opts?: { isActive?: () => boolean }): () => void {
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
      // 2026-10-26：数据没变时 renderAll 内部跳过 DOM 重建（滚动/筛选状态不被抹掉）；
      // 仅当实际重建发生才更新 meta，避免「刷新于」时钟掩盖守卫效果
      if (renderAll(refs, json.data)) {
        refs.meta.textContent = '刷新于 ' + new Date().toLocaleTimeString() + ' · 数据 ' + (json.data.fetchedAt ? new Date(json.data.fetchedAt).toLocaleTimeString() : '')
      }
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
  // 2026-10-26：tab 非激活时停轮询（keepMounted 下后台不再白取数/重建）；
  // 重新激活后的第一个 tick 自然恢复取数，避免回来看见最长 30s 的旧数据。
  pollTimer = window.setInterval(() => {
    if (disposed || document.hidden) return
    if (opts?.isActive && !opts.isActive()) return
    void fetchData()
  }, POLL_MS)

  return () => {
    disposed = true
    if (pollTimer !== undefined) { clearInterval(pollTimer); pollTimer = undefined }
    refs.refreshBtn?.removeEventListener('click', onRefresh)
    refs.root.remove()
  }
}
