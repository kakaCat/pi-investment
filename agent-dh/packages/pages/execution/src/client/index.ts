/**
 * Dashboard-execution client half — the execution board's GUI face.
 *
 * Dual-half contract: package.json declares dsh.client + exports["./client"];
 * the DSH web shell's client-modules host composes a boot-graph entry for this
 * package, serves the wrapped bundle at
 * /plugins/??@pi-investment/dashboard-execution/client.js&rev=…, and the shell
 * runs this module in the browser. Exports mirror the taskboard client-entry
 * shape: name / inject / apply.
 *
 * GUI entry point = the OFFICIAL sidebar seat `sidebar.footer.action` (the
 * single third-party slot in the sidebar; rendered beside Settings at the foot,
 * list/root scope). Registration goes through `ctx.slots` — the same mechanism
 * ui-cordis / ui-settings-general use — never DOM injection. `inject` declares
 * the client services apply() needs: `slots` makes `ctx.slots` available.
 *
 * Board body follows the dsh-taskboard standard: a container is mounted as a
 * trailing child of the center (conversation) column, a stylesheet rule hides
 * the column's other children while `html[data-dsh-exec-active]` is set, and
 * visibility is toggled by the board controller (open/close on the footer
 * action click; auto-close on sidebar-row click / other-panel activation).
 * Data comes from the same-origin auth-free JSON endpoint
 * /dashboard/api/board the host half exposes.
 *
 * @module dashboard-execution/client
 */
import { createBoardController, mountBoard } from './board-mount.ts'
import { ExecFooterAction, injectFooterStyles, PANEL_NAME, PANEL_LABEL, OPEN_EVENT } from './footer-action.ts'
import { injectStyles } from './styles.ts'

export const name = '@pi-investment/dashboard-execution/client'
/** Service names this client module requires on ctx (official slot idiom). */
export const inject: string[] = ['slots', 'sessions', 'workspaces']

/** Minimal view of the slots service this module consumes (official shape). */
interface SlotsService {
  /** Queue a registration until the target slot exists (sidebar foot seat). */
  inject(slot: string, thunk: () => unknown): unknown
  /** Register one occupant (React component) into a declared slot seat. */
  register(options: Record<string, unknown>, occupant: unknown): unknown
}
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
        origin?: string
      }>
      current?: string
    }
  }
}
interface ApplyContext {
  slots?: SlotsService
  /** 「我来解决」会话候选（与左栏同源；board-mount 点击时经 __dshExecSessions 懒读） */
  sessions?: SessionsFacade
  /** workspace 控制器（归档会话集合 archivedSessionIds 来源） */
  workspaces?: {
    list?: { getSnapshot?: () => { archivedSessionIds?: string[] } }
  }
}

/** Window-scoped apply guard so HMR re-apply tears down before re-mounting. */
declare global {
  interface Window {
    __dshExecClient?: { dispose(): void }
    /** 「我来解决」会话源（与左栏同源；board-mount 点开时懒读） */
    __dshExecSessions?: SessionsFacade
    /** apply 时的 client ctx（sessions 若未注入完成，点开时经它惰性重取） */
    __dshExecCtx?: { sessions?: SessionsFacade; workspaces?: unknown }
    /** workspaces 服务快照（归档集合，会话候选过滤用） */
    __dshExecWorkspaces?: { list?: { getSnapshot?: () => { archivedSessionIds?: string[] } } }
  }
}

/** Client apply hook — never throws; a throw here fails the whole boot. */
export function apply(ctx: ApplyContext): void {
  // 暴露给 board-mount：「我来解决」点开时即时取会话列表（不随轮询重绘，点开时新鲜读取）
  try { (window as any).__dshExecCtx = ctx; (window as any).__dshExecSessions = ctx?.sessions; (window as any).__dshExecWorkspaces = ctx?.workspaces } catch { /* noop */ }
  try {
    injectFooterStyles()
    injectStyles()

    // Guard: a prior apply() (e.g. HMR re-apply) disposes its listeners and
    // board mount first, so re-entry never double-registers or double-mounts.
    window.__dshExecClient?.dispose()

    // Execution board: controller + center-column mount (taskboard contract).
    const controller = createBoardController()
    const disposeBoard = mountBoard(controller)

    // Wire the footer action click to the board controller (the seam the
    // occupant dispatches; index.ts owns the actual behavior).
    const onOpen = (event: Event): void => {
      const open = (event as CustomEvent<{ open?: boolean }>).detail?.open
      console.log('[dashboard-execution] open-board event', { open }, 'boardOpen:', controller.getSnapshot().boardOpen)
      if (open === true) {
        // 已开时再点=关闭（openBoard 对已开状态是幂等空转）
        if (controller.getSnapshot().boardOpen) controller.closeBoard()
        else controller.openBoard()
      } else controller.toggleBoard()
    }
    window.addEventListener(OPEN_EVENT, onOpen)

    window.__dshExecClient = {
      dispose: () => {
        window.removeEventListener(OPEN_EVENT, onOpen)
        disposeBoard()
        controller.closeBoard()
      },
    }

    // Official registration idiom (see sidebar slots contract: id is required
    // for list seats; order positions the entry; occupant receives {wide}).
    const slots = ctx.slots
    if (slots) {
      // Register execution footer action
      slots.inject('sidebar.footer.action', () =>
        slots.register(
          {
            name: 'sidebar.footer.action',
            id: PANEL_NAME,
            order: 100,
            label: PANEL_LABEL,
          },
          ExecFooterAction,
        ),
      )
    } else {
      console.warn('[dashboard-execution] ctx.slots unavailable (inject missing "slots")')
    }
  } catch (e) {
    console.error('[dashboard-execution] client half failed to start:', e)
  }
}
