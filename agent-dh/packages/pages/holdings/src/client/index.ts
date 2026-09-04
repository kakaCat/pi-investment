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
 * GUI entry point = the OFFICIAL sidebar seat `sidebar.footer.action` (the
 * single third-party slot in the sidebar; rendered beside Settings at the foot,
 * list/root scope). Registration goes through `ctx.slots` — the same mechanism
 * ui-cordis / ui-settings-general use — never DOM injection. `inject` declares
 * the client services apply() needs: `slots` makes `ctx.slots` available.
 *
 * Board body follows the dsh-taskboard standard: a container is mounted as a
 * trailing child of the center (conversation) column, a stylesheet rule hides
 * the column's other children while `html[data-dsh-hld-active]` is set, and
 * visibility is toggled by the board controller (open/close on the footer
 * action click; auto-close on sidebar-row click / other-panel activation).
 * Data comes from the same-origin auth-free JSON endpoint
 * /dashboard/api/holdings the host half exposes.
 *
 * @module dashboard-holdings/client
 */
import { createBoardController, mountBoard } from './board-mount.js'
import { HoldingsFooterAction, injectFooterStyles, PANEL_NAME, PANEL_LABEL, OPEN_EVENT } from './footer-action.js'
import { injectStyles } from './styles.js'

export const name = '@pi-investment/dashboard-holdings/client'
/** Service names this client module requires on ctx (official slot idiom). */
export const inject: string[] = ['slots']

/** Minimal view of the slots service this module consumes (official shape). */
interface SlotsService {
  /** Queue a registration until the target slot exists (sidebar foot seat). */
  inject(slot: string, thunk: () => unknown): unknown
  /** Register one occupant (React component) into a declared slot seat. */
  register(options: Record<string, unknown>, occupant: unknown): unknown
}
interface ApplyContext {
  slots?: SlotsService
}

/** Window-scoped apply guard so HMR re-apply tears down before re-mounting. */
declare global {
  interface Window {
    __dshHldClient?: { dispose(): void }
  }
}

/** Client apply hook — never throws; a throw here fails the whole boot. */
export function apply(ctx: ApplyContext): void {
  try {
    injectFooterStyles()
    injectStyles()

    // Guard: a prior apply() (e.g. HMR re-apply) disposes its listeners and
    // board mount first, so re-entry never double-registers or double-mounts.
    window.__dshHldClient?.dispose()

    // Board body: controller + center-column mount (taskboard contract).
    const controller = createBoardController()
    const disposeBoard = mountBoard(controller)

    // Wire the footer action click to the board controller (the seam the
    // occupant dispatches; index.ts owns the actual behavior).
    const onOpen = (event: Event): void => {
      const open = (event as CustomEvent<{ open?: boolean }>).detail?.open
      console.log('[dashboard-holdings] open-board event', { open }, 'boardOpen:', controller.getSnapshot().boardOpen)
      if (open === true) controller.openBoard()
      else controller.toggleBoard()
    }
    window.addEventListener(OPEN_EVENT, onOpen)

    window.__dshHldClient = {
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
      slots.inject('sidebar.footer.action', () =>
        slots.register(
          {
            name: 'sidebar.footer.action',
            id: PANEL_NAME,
            order: 200, // 在 execution (order: 100) 之后
            label: PANEL_LABEL,
          },
          HoldingsFooterAction,
        ),
      )
    } else {
      console.warn('[dashboard-holdings] ctx.slots unavailable (inject missing "slots")')
    }
  } catch (e) {
    console.error('[dashboard-holdings] client half failed to start:', e)
  }
}
