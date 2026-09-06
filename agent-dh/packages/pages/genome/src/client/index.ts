/**
 * Client half of the genome dashboard: registers the sidebar「自主进化」entry
 * (top sidebar row, holdings idiom) and lazily mounts the center-column board.
 * Pure DOM; plain fetch to the same-origin host API /dashboard/api/genome.
 *
 * @module dashboard-genome/client
 */
import { mountSidebarEntry } from './sidebar-entry.ts'
import { createBoardController, mountBoard } from './board-mount.ts'
import { injectStyles } from './styles.ts'

export const name = '@pi-investment/dashboard-genome/client'

/** 顶部侧栏入口行 + 中心栏板：纯 DOM，无需 shell services。 */
export const inject: string[] = []

/** HMR 安全：重复 apply 先释放上一次的挂载（与 dashboard-execution 同款守卫）。 */
const GLOBAL_KEY = '__dshGenomeClient'

export function apply(): void {
  if ((window as unknown as Record<string, unknown>)[GLOBAL_KEY] !== undefined) {
    try {
      ;((window as unknown as Record<string, unknown>)[GLOBAL_KEY] as { dispose(): void }).dispose()
    } catch {
      // 旧实例 dispose 失败不阻断重建
    }
  }

  injectStyles()

  const controller = createBoardController()
  const disposeSidebar = mountSidebarEntry(controller)
  const disposeBoard = mountBoard(controller)

  const dispose = (): void => {
    try {
      disposeSidebar()
      disposeBoard()
    } catch {
      // 幂等收尾
    }
  }
  ;(window as unknown as Record<string, unknown>)[GLOBAL_KEY] = { dispose }

  console.log('[dashboard-genome] client applied — 侧栏「自主进化」入口就绪')
}
