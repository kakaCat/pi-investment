/**
 * Client half of the genome dashboard: registers the sidebar「自主进化」entry
 * (top sidebar row, holdings idiom) and opens the board as a native DSH
 * right-sidebar tab instead of replacing the conversation column.
 * Pure DOM board body; plain fetch to the same-origin host API /dashboard/api/genome.
 *
 * @module dashboard-genome/client
 */
import { mountSidebarEntry } from './sidebar-entry.ts'
import { mountBoardView } from './board-mount.ts'
import { injectStyles } from './styles.ts'
import { injectToastStyles, registerRightTab, showToast, type RightTabHandle } from '@pi-investment/page-kit/client'

export const name = '@pi-investment/dashboard-genome/client'

/** 顶部侧栏入口行 + 右栏 tab：需要官方右栏服务与 slot 注册表。 */
export const inject: string[] = ['sidebarRight', 'sidebarRightTabs', 'slots']

/** HMR 安全：重复 apply 先释放上一次的挂载（与 dashboard-execution 同款守卫）。 */
const GLOBAL_KEY = '__dshGenomeClient'

/** 右栏 tab 身份：id 全局唯一（包名），kind 是 openTab 的类型 discriminator。 */
const TAB_ID = '@pi-investment/dashboard-genome'
const TAB_KIND = 'dashboard-genome'

interface ApplyContext {
  sidebarRight?: unknown
  sidebarRightTabs?: unknown
  slots?: unknown
  effect?: (fn: () => unknown, label?: string) => unknown
}

export function apply(ctx: ApplyContext): void {
  if ((window as unknown as Record<string, unknown>)[GLOBAL_KEY] !== undefined) {
    try {
      ;((window as unknown as Record<string, unknown>)[GLOBAL_KEY] as { dispose(): void }).dispose()
    } catch {
      // 旧实例 dispose 失败不阻断重建
    }
  }

  try {
    injectStyles()
    injectToastStyles('dsh-gen')

    const tab: RightTabHandle = registerRightTab(ctx, {
      id: TAB_ID,
      kind: TAB_KIND,
      title: '自主进化',
      mount: (host) => mountBoardView(host),
    })

    // 入口点击语义：已激活 → 关闭该 tab；否则打开/聚焦。右栏打不开（无会话）时给可见提示。
    const controller = {
      isActive: (): boolean => tab.isActive(),
      toggle: (): void => {
        if (tab.isActive()) {
          tab.close()
          return
        }
        if (!tab.open()) {
          showToast('请先打开一个会话 —— 右侧栏需要有会话才能停靠看板', false, 'dsh-gen')
        }
      },
    }
    const disposeSidebar = mountSidebarEntry(controller)

    const dispose = (): void => {
      try {
        disposeSidebar()
        tab.dispose()
      } catch {
        // 幂等收尾
      }
    }
    ;(window as unknown as Record<string, unknown>)[GLOBAL_KEY] = { dispose }

    console.log('[dashboard-genome] client applied — 侧栏「自主进化」入口就绪（右侧栏 tab）')
  } catch (e) {
    console.error('[dashboard-genome] client half failed to start:', e)
  }
}
