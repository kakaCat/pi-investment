/**
 * Dsh-pmboard client half — M3: 泳道看板 GUI（需求状态列 + 详情 + 待归类 + 会话跳转）。
 *
 * DSH dual-half contract: package.json declares dsh.client + exports["./client"];
 * shell serves bundle at /plugins/??dsh-pmboard/client.js.
 */
import { createBoardController, mountBoard } from './board-mount.ts'
import { ReqboardFooterAction, injectFooterStyles, OPEN_EVENT } from './footer-action.ts'
import { RequirementProgressAction } from './conversation-progress.ts'
import { injectStyles } from './styles.ts'
import { registerBizToolviews } from './toolviews/index.ts'
import { PANEL_NAME, PANEL_LABEL } from './dom.ts'

export const name = 'dsh-pmboard/client'
// sidebarRight（REQ-ff20ca t5）：官方右侧栏导航面——Cordis 要求服务先声明 inject
// 才允许访问（否则抛 "cannot get property without inject"）。该服务由 web-app 随
// 官方 UI 插件组提供，实测存在；声明后插件等待它就绪再激活。
export const inject: string[] = ['slots', 'sessions', 'workspaces', 'sidebarRight']

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
      const detail = (event as CustomEvent<{ open?: boolean; req?: string }>).detail
      if (detail?.open === true) {
        controller.openBoard()
        // 如果传入了 req 参数，打开需求详情页
        if (detail.req) {
          // 等待看板打开后，通过触发 data-action="open-req" 事件来打开详情
          setTimeout(() => {
            const reqCard = document.querySelector(`[data-req="${detail.req}"]`)
            if (reqCard) {
              // 模拟点击需求卡片，触发 open-req 事件
              reqCard.dispatchEvent(new MouseEvent('click', { bubbles: true }))
            }
          }, 200)
        }
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
      // 侧边栏底部按钮（项目看板入口）
      try {
        slots.inject('sidebar.footer.action', () =>
          slots.register(
            { name: 'sidebar.footer.action', id: PANEL_NAME, order: 110, label: PANEL_LABEL },
            ReqboardFooterAction,
          ),
        )
      } catch (e) {
        console.error('[dsh-pmboard] Failed to register sidebar.footer.action:', e)
      }

      // 会话标题栏的「需求进度」流程图：session 作用域槽位会把 sessionId 交给 inject，
      // 组件据此查该会话绑定的需求进度（无绑定需求 → 渲染 null，槽位不占位）。
      // order: 5 让它显示在模式选择器后面（模式选择器通常是 order: 10）
      //
      // FIX: 用 try-catch 包裹槽位注册，避免与 DSH 框架对话节点系统冲突导致
      // "assistant-step withdrew materialized target 'chat'" 错误影响整个插件加载
      try {
        slots.inject('conversation.session.header.utilities', () =>
          slots.register(
            {
              name: 'conversation.session.header.utilities',
              id: PANEL_NAME + ':progress',
              order: 5,
              inject: (sessionId: string) => ({ sessionId }),
            },
            RequirementProgressAction,
          ),
        )
      } catch (e) {
        console.error('[dsh-pmboard] Failed to register conversation.session.header.utilities:', e)
        // 降级：进度条注册失败不影响主功能（看板依然可用）
      }

      // 业务工具定制卡片（REQ-c48f99 FR-1）：tool.call.toolview keyed 插槽，
      // 逐卡 try/catch 在 registerBizToolviews 内部；整体失败不拖垮看板。
      try {
        const n = registerBizToolviews(slots)
        console.debug('[dsh-pmboard] biz toolviews registered: ' + n)
      } catch (e) {
        console.error('[dsh-pmboard] Failed to register biz toolviews:', e)
      }
    } else {
      console.warn('[dsh-pmboard] ctx.slots unavailable')
    }
  } catch (e) {
    console.error('[dsh-pmboard] client half failed to start:', e)
  }
}
