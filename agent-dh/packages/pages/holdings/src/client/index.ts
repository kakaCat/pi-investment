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
import { createBoardController, mountBoard } from './board-mount.js'
import { mountSidebarEntry } from './sidebar-entry.js'
import { injectStyles } from './styles.js'

export const name = '@pi-investment/dashboard-holdings/client'
/** No shell services needed — the top sidebar row is plain DOM (taskboard idiom). */
export const inject: string[] = []

/** Window-scoped apply guard so HMR re-apply tears down before re-mounting. */
declare global {
  interface Window {
    __dshHldClient?: { dispose(): void }
  }
}

/** Client apply hook — never throws; a throw here fails the whole boot. */
export function apply(): void {
  try {
    injectStyles()

    // Guard: a prior apply() (e.g. HMR re-apply) disposes its listeners and
    // board mount first, so re-entry never double-registers or double-mounts.
    window.__dshHldClient?.dispose()

    // Board body: controller + center-column mount (taskboard contract).
    const controller = createBoardController()
    const disposeBoard = mountBoard(controller)

    // Top sidebar entry row toggles the board (see sidebar-entry.ts).
    const disposeEntry = mountSidebarEntry({
      isActive: () => controller.getSnapshot().boardOpen,
      toggle: () => controller.toggleBoard(),
    })

    window.__dshHldClient = {
      dispose: () => {
        disposeBoard()
        disposeEntry()
        controller.closeBoard()
      },
    }
  } catch (e) {
    console.error('[dashboard-holdings] client half failed to start:', e)
  }
}
