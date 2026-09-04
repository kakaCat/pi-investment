/**
 * @pi-investment/dashboard-bulletin · client 半（浏览器端，RFC 013）。
 * phase1（2026-09-05，用户指定节奏）：只挂侧栏顶部「公告板」菜单按钮，
 * 点按为占位反馈（data-active 切换 + console 提示），不挂看板正文；
 * 用户 GUI 确认按钮 OK 后 phase2 才实现看板（board-mount + conversation 栏
 * 挂载 + html[data-dsh-bbd-active] 显隐 + ACTIVATE_EVENT 互斥 + host 数据路由）。
 *
 * 模块形状：name = 包名，apply(ctx) 具名导出（与 holdings/execution 一致），
 * dsh.web.client 由 DSH web shell 加载；inject 空数组（纯 DOM，无 slot 参与）。
 *
 * @module dashboard-bulletin/client
 */
import { mountSidebarEntry } from './sidebar-entry.js'
import { injectStyles } from './styles.js'

export const name = '@pi-investment/dashboard-bulletin/client'

export const inject: string[] = []

export function apply(_ctx?: unknown): void {
  // dispose 守卫：shell 重载 client 模块时先清理上一份挂载，防重复按钮。
  try {
    ;(window as any).__dshBbdClient?.dispose?.()
  } catch {
    /* 首载 window 上还没有旧实例，忽略 */
  }

  injectStyles()

  // phase1 占位 controller：点击有状态反馈（按钮高亮），phase2 换成真实看板。
  const state = { active: false }
  const controller = {
    isActive: () => state.active,
    toggle: () => {
      state.active = !state.active
      console.info('[dashboard-bulletin] 按钮已就绪（phase1）。看板正文待 phase2（RFC 013）')  
    },
  }

  const disposeEntry = mountSidebarEntry(controller)

  const client = {
    dispose() {
      try {
        disposeEntry()
      } catch {
        /* noop */
      }
    },
  }
  ;(window as any).__dshBbdClient = client
}
