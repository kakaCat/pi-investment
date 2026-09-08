/**
 * Dsh-pmboard client half — M3: 泳道看板 GUI（需求状态列 + 详情 + 待归类 + 会话跳转）。
 *
 * DSH dual-half contract: package.json declares dsh.client + exports["./client"];
 * shell serves bundle at /plugins/??dsh-pmboard/client.js.
 */
import { createBoardController, mountBoard } from './board-mount.ts'
import { ReqboardFooterAction, injectFooterStyles, OPEN_EVENT } from './footer-action.ts'
import { injectStyles } from './styles.ts'
import { PANEL_NAME, PANEL_LABEL } from './dom.ts'

export const name = 'dsh-pmboard/client'
export const inject: string[] = ['slots', 'sessions', 'workspaces']

interface SlotsService {
  inject(slot: string, thunk: () => unknown): unknown
  register(options: Record<string, unknown>, occupant: unknown): unknown
}

interface ApplyContext {
  slots?: SlotsService
  sessions?: unknown
  workspaces?: unknown
}

declare global {
  interface Window {
    __dshReqboardClient?: { dispose(): void }
    __dshPmSessions?: unknown
    __dshPmWorkspaces?: unknown
    __dshPmCtx?: ApplyContext
  }
}

export function apply(ctx: ApplyContext): void {
  try {
    injectFooterStyles()
    injectStyles()

    // HMR guard: dispose previous apply
    window.__dshReqboardClient?.dispose()

    // 供 session-jump 惰性读取（服务可能晚于 apply 提供）
    window.__dshPmCtx = ctx
    window.__dshPmSessions = ctx.sessions
    window.__dshPmWorkspaces = ctx.workspaces

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
        delete window.__dshPmCtx
        delete window.__dshPmSessions
        delete window.__dshPmWorkspaces
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
      console.warn('[dsh-pmboard] ctx.slots unavailable')
    }
  } catch (e) {
    console.error('[dsh-pmboard] client half failed to start:', e)
  }
}
