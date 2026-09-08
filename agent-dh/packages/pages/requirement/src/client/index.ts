/**
 * Reqboard client half — step 1: sidebar entry + placeholder board view.
 *
 * DSH dual-half contract: package.json declares dsh.client + exports["./client"];
 * shell serves bundle at /plugins/??@pi-investment/dashboard-requirement/client.js.
 */
import { createBoardController, mountBoard } from './board-mount.ts'
import { ReqboardFooterAction, injectFooterStyles, OPEN_EVENT } from './footer-action.ts'
import { injectStyles } from './styles.ts'
import { PANEL_NAME, PANEL_LABEL } from './dom.ts'

export const name = '@pi-investment/dashboard-requirement/client'
export const inject: string[] = ['slots']

interface SlotsService {
  inject(slot: string, thunk: () => unknown): unknown
  register(options: Record<string, unknown>, occupant: unknown): unknown
}

interface ApplyContext {
  slots?: SlotsService
}

declare global {
  interface Window {
    __dshReqboardClient?: { dispose(): void }
  }
}

export function apply(ctx: ApplyContext): void {
  try {
    injectFooterStyles()
    injectStyles()

    // HMR guard: dispose previous apply
    window.__dshReqboardClient?.dispose()

    const controller = createBoardController()
    const disposeBoard = mountBoard(controller)

    const onOpen = (event: Event): void => {
      const detail = (event as CustomEvent<{ open?: boolean }>).detail
      if (detail?.open === true) {
        if (controller.getSnapshot().boardOpen) controller.closeBoard()
        else controller.openBoard()
      } else {
        controller.toggleBoard()
      }
    }
    window.addEventListener(OPEN_EVENT, onOpen)

    window.__dshReqboardClient = {
      dispose: () => {
        window.removeEventListener(OPEN_EVENT, onOpen)
        disposeBoard()
        controller.closeBoard()
      },
    }

    const slots = ctx.slots
    if (slots) {
      slots.inject('sidebar.footer.action', () =>
        slots.register(
          { name: 'sidebar.footer.action', id: PANEL_NAME, order: 110, label: PANEL_LABEL },
          ReqboardFooterAction,
        ),
      )
    } else {
      console.warn('[dashboard-requirement] ctx.slots unavailable')
    }
  } catch (e) {
    console.error('[dashboard-requirement] client half failed to start:', e)
  }
}
