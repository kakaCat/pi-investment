/**
 * Dashboard-holdings client half — the holdings board's GUI face.
 *
 * Dual-half contract: package.json declares dsh.client + exports["./client"];
 * the DSH web shell's client-modules host composes a boot-graph entry for this
 * package, serves the wrapped bundle at
 * /plugins/??@pi-investment/dashboard-holdings/client.js&rev=…, and the shell
 * runs this module in the browser. Exports mirror the taskboard client-entry
 * shape: name / inject / apply.
 *
 * GUI entry point = a TOP sidebar row (direct child of the logo row's owner,
 * i.e. above the conversation list / 新会话), the same pure-DOM row the
 * taskboard/execution boards use — never DOM-injected into React-managed
 * slots. The previous official seat registration (sidebar.footer.action,
 * beside Settings at the foot) was dropped 2026-09-05: the user asked the
 * board menu to live at the TOP of the sidebar instead.
 *
 * Board body follows the dsh-taskboard standard: a container is mounted as a
 * trailing child of the center (conversation) column, a stylesheet rule hides
 * the column's other children while `html[data-dsh-hld-active]` is set, and
 * visibility is toggled by the board controller (open/close on the top entry
 * click; auto-close on sidebar-row click / other-panel activation).
 * Data comes from the same-origin auth-free JSON endpoint
 * /dashboard/api/holdings the host half exposes.
 *
 * @module dashboard-holdings/client
 */
import { createBoardController, mountBoardView } from './board-mount.js'
import { mountSidebarEntry } from './sidebar-entry.js'
import { injectStyles } from './styles.js'
import { injectSolveStyles } from '@pi-investment/solve-kit/client'
import { injectToastStyles, registerRightTab, showToast, type RightTabHandle } from '@pi-investment/page-kit/client'

export const name = '@pi-investment/dashboard-holdings/client'
/**
 * Shell services: sessions/workspaces feed the solve-kit window picker
 * session candidates (2026-09-08); slots mirrors the taskboard entry idiom
 * kept by sibling pages. Board body itself stays plain DOM.
 */
export const inject: string[] = ['slots', 'sessions', 'workspaces', 'sidebarRight', 'sidebarRightTabs']

/** apply 收到的 client ctx 极简投影（宽容读取，缺字段即降级） */
type ApplyContext = {
  slots?: unknown
  sessions?: unknown
  workspaces?: unknown
  sidebarRight?: unknown
  sidebarRightTabs?: unknown
  effect?: (fn: () => unknown, label?: string) => unknown
}

/** Window-scoped apply guard so HMR re-apply tears down before re-mounting. */
declare global {
  interface Window {
    __dshHldClient?: { dispose(): void }
    __dshHldCtx?: { sessions?: unknown; workspaces?: unknown }
    __dshHldSessions?: unknown
    __dshHldWorkspaces?: { list?: { getSnapshot?: () => { archivedSessionIds?: string[] } } }
  }
}

/** Client apply hook — never throws; a throw here fails the whole boot. */
export function apply(ctx: ApplyContext): void {
  try {
    // sessions/workspaces 注入缓存：board-mount 点「我来解决」时读候选（宽容降级，注入失败不阻断看板）
    try {
      window.__dshHldCtx = ctx
      window.__dshHldSessions = ctx.sessions
      window.__dshHldWorkspaces = ctx.workspaces as never
    } catch { /* noop */ }
    injectStyles()
    // solve 弹层/按钮/toast 样式（dsh-hld 前缀，幂等注入一次）
    injectSolveStyles('dsh-hld')
    injectToastStyles('dsh-hld')

    // Guard: a prior apply() (e.g. HMR re-apply) disposes its listeners and
    // board mount first, so re-entry never double-registers or double-mounts.
    window.__dshHldClient?.dispose()

    // Board body: 注册成 DSH 原生右侧栏 tab（打开时才挂载，与会话并排）。
    const controller = createBoardController()
    const tab: RightTabHandle = registerRightTab(ctx, {
      id: '@pi-investment/dashboard-holdings',
      kind: 'dashboard-holdings',
      title: '账户持仓',
      // isActive 供轮询守卫：tab 非激活时暂停轮询，重新激活立即补数据
      mount: (host) => mountBoardView(controller, host, { isActive: () => tab.isActive() }),
    })

    // Top sidebar entry row opens/closes the right-sidebar tab.
    const disposeEntry = mountSidebarEntry({
      isActive: () => tab.isActive(),
      toggle: () => {
        if (tab.isActive()) {
          tab.close()
          return
        }
        if (!tab.open()) {
          showToast('请先打开一个会话 —— 右侧栏需要有会话才能停靠看板', false, 'dsh-hld')
        }
      },
    })

    window.__dshHldClient = {
      dispose: () => {
        disposeEntry()
        tab.dispose()
      },
    }
  } catch (e) {
    console.error('[dashboard-holdings] client half failed to start:', e)
  }
}
