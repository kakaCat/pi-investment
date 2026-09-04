/**
 * @pi-investment/dashboard-bulletin · client 半（浏览器端，RFC 013）。
 * phase2（2026-09-05，用户开工）：公告板主体——中心栏看板全量渲染：
 * 顶部入口行（logoRow 下、新会话上方，与「智能执行」「账户持仓」并列）点击开合，
 * 中心栏挂载 data-dsh-bbd-view 容器，html[data-dsh-bbd-active] 显隐 + ACTIVATE_EVENT
 * 互斥；数据来自同源 /dashboard/api/bulletin/posts（host 半聚合 board_* 工具同源数据，
 * RFC 009 memory tag office:board）。phase1 占位 controller（点按只亮按钮）已替换为真实看板。
 *
 * 模块形状：name = 包名/client、inject 空数组、apply()（与 holdings/execution client 一致）。
 * @module dashboard-bulletin/client
 */
import { createBoardController, mountBoard } from './board-mount.js'
import { mountSidebarEntry } from './sidebar-entry.js'
import { injectStyles } from './styles.js'

export const name = '@pi-investment/dashboard-bulletin/client'

export const inject: string[] = []

declare global {
  interface Window {
    __dshBbdClient?: { dispose(): void }
  }
}

export function apply(): void {
  try {
    injectStyles()

    // HMR / 壳重载先清理上一份挂载，防重复挂载（同 holdings __dshHldClient 惯例）
    ;(window as any).__dshBbdClient?.dispose?.()

    // 看板主体：真实 controller + 中心栏挂载
    const controller = createBoardController()
    const disposeBoard = mountBoard(controller)

    // 顶部侧栏入口行：isActive → 开板状态；toggle → 开合
    const disposeEntry = mountSidebarEntry({
      isActive: () => controller.getSnapshot().boardOpen,
      toggle: () => controller.toggleBoard(),
    })

    ;(window as any).__dshBbdClient = {
      dispose: () => {
        try { disposeBoard() } catch { /* noop */ }
        try { disposeEntry() } catch { /* noop */ }
        try { controller.closeBoard() } catch { /* noop */ }
      },
    }
    console.info('[dashboard-bulletin] phase2 board client ready')
  } catch (e) {
    console.error('[dashboard-bulletin] client half failed to start:', e)
  }
}
