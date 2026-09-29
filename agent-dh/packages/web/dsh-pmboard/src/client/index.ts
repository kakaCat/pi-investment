/**
 * Dsh-pmboard client half — M3: 泳道看板 GUI（需求状态列 + 详情 + 待归类 + 会话跳转）。
 *
 * DSH dual-half contract: package.json declares dsh.client + exports["./client"];
 * shell serves bundle at /plugins/??dsh-pmboard/client.js.
 *
 * 2026-09-28（REQ-260928185112-e20d FR-1/FR-2/FR-3）：看板从「会话列 DOM 覆盖层 +
 * 侧栏底部入口按钮」迁到 DSH 原生页面机制——page/register.ts 一次注册 \`main\`（keyed）
 * 与 \`sidebar.panellist\`（id 同源），导航交给 ctx.layout.selectPanel。
 * 本文件因此不再注册入口按钮、不再监听入口自定义事件、不再自己造看板生命周期壳
 * （挂载下沉到 main 插槽宿主 page/host.ts；旧机制文件由后续卡拆除）。
 */
import { RequirementProgressAction } from './conversation-progress.ts'
import { injectStyles } from './styles.ts'
import { registerBizToolviews } from './toolviews/index.ts'
import { PANEL_NAME } from './dom.ts'
import { registerPmboardPage } from './page/register.ts'
import { clearPageLayout, setPageLayout, type PageLayoutFace } from './page/page-runtime.ts'

export const name = 'dsh-pmboard/client'
// sidebarRight（REQ-ff20ca t5）：官方右侧栏导航面——Cordis 要求服务先声明 inject
// 才允许访问（否则抛 "cannot get property without inject"）。该服务由 web-app 随
// 官方 UI 插件组提供，实测存在；声明后插件等待它就绪再激活。
// layout（REQ-260928185112-e20d FR-3）：ctx.layout.selectPanel(id|null) 是页面导航的唯一来源，
// 看板不再自己维护显示状态；缺声明会被 Cordis 服务访问守卫拒绝。
export const inject: string[] = ['slots', 'sessions', 'workspaces', 'uiWorkspace', 'sidebarRight', 'layout']

interface SlotsService {
  inject(slot: string, thunk: () => unknown): unknown
  register(options: Record<string, unknown>, occupant: unknown): unknown
}

interface ApplyContext {
  slots?: SlotsService
  sessions?: unknown
  workspaces?: unknown
  /** DSH 官方会话导航服务（uiWorkspace.openSession = 选中会话并显示对话） */
  uiWorkspace?: unknown
  /** DSH 官方页面导航服务（layout.selectPanel(id|null)：null = 回当前对话） */
  layout?: PageLayoutFace
}

declare global {
  interface Window {
    __dshReqboardClient?: { dispose(): void }
    __dshPmSessions?: unknown
    __dshPmWorkspaces?: unknown
    __dshPmUiWorkspace?: unknown
    __dshPmCtx?: ApplyContext
  }
}

export function apply(ctx: ApplyContext): void {
  try {
    injectStyles()

    // HMR guard: dispose previous apply
    window.__dshReqboardClient?.dispose()

    // 页面运行环境：layout 交模块级 page-runtime，供 session-jump 惰性读取
    // （服务可能晚于 apply 提供，故 apply 时只做「有则存、无则留空」的粗粒度投射）。
    setPageLayout(ctx.layout)

    // 供 session-jump 惰性读取（服务可能晚于 apply 提供）
    window.__dshPmCtx = ctx
    window.__dshPmSessions = ctx.sessions
    window.__dshPmWorkspaces = ctx.workspaces
    window.__dshPmUiWorkspace = ctx.uiWorkspace

    // 页面两端注册（main keyed 插槽 + sidebar.panellist 条目，同源 id）：取代原来的
    // 侧栏底部入口按钮（footer action）。注册失败不拖垮其余接线（进度条 / 业务卡片）。
    let disposePage: (() => void) | undefined
    try {
      disposePage = registerPmboardPage(ctx)
    } catch (e) {
      console.error('[dsh-pmboard] Failed to register page panel:', e)
    }

    window.__dshReqboardClient = {
      dispose: () => {
        disposePage?.()
        disposePage = undefined
        clearPageLayout()
        delete window.__dshPmCtx
        delete window.__dshPmSessions
        delete window.__dshPmWorkspaces
        delete window.__dshPmUiWorkspace
      },
    }

    const slots = ctx.slots
    if (slots) {
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
