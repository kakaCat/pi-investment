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

// Task #2：认领/转交需要左侧会话列表（USER #3：公告板客户端已见左栏内容，不再从后端拉窗口清单）。
// inject 'sessions' → apply(ctx) 的 ctx.sessions 与左栏同源（同一 client 服务），其
// .list.getSnapshot() 产出 { items:{id,displayTitle,running,blank,...}[], current }。
export const inject: string[] = ['sessions', 'workspaces']

/** sessions 服务的极简投影（宽容读取，缺字段即降级；boot 提供失败也不阻断看板只读） */
export interface SessionsFacade {
  list?: {
    getSnapshot?(): {
      items?: Array<{
        id?: string
        sessionId?: string
        displayTitle?: string
        title?: string
        running?: boolean
        blank?: boolean
      }>
      current?: string
    }
  }
}
interface ApplyContext {
  sessions?: SessionsFacade
  /** workspace 控制器（归档集合 archivedSessionIds 来源） */
  workspaces?: {
    list?: { getSnapshot?: () => { archivedSessionIds?: string[] } }
  }
}

declare global {
  interface Window {
    __dshBbdClient?: { dispose(): void }
    /** 认领/转交用的会话源（与左栏同源；mount 层点击时懒读） */
    __dshBbdSessions?: SessionsFacade
    /** apply 时的 client ctx（sessions 若未注入完成，点开转交时经它惰性重取） */
    __dshBbdCtx?: { sessions?: SessionsFacade; workspaces?: unknown }
    /** workspaces 服务快照（归档集合，转交候选过滤用） */
    __dshBbdWorkspaces?: { list?: { getSnapshot?: () => { archivedSessionIds?: string[] } } }
  }
}

export function apply(ctx: ApplyContext): void {
  // 暴露给 board-mount：转交弹窗即时取会话列表（不随轮询重绘，点开时新鲜读取）
  try { (window as any).__dshBbdCtx = ctx; (window as any).__dshBbdSessions = ctx?.sessions; (window as any).__dshBbdWorkspaces = ctx?.workspaces } catch { /* noop */ }
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
