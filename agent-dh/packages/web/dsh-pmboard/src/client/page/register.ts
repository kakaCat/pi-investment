/**
 * 本页两端注册（REQ-260928185112-e20d FR-1/FR-2）—— 把「项目看板」注册成 DSH 原生页面：
 * \`main\` keyed 插槽（key = PANEL_ID，承载命令式看板宿主）+ \`sidebar.panellist\` 条目（id 同源）。
 *
 * 同源纪律：id 只来自 dom.ts 的 PANEL_ID（= PANEL_NAME，即 MainPanelId），
 * 因此不可能出现「侧栏条目与主列占用者 id 漂移」——这正是把两端收进一次调用的原因。
 * 这也取代了旧的 \`sidebar.footer.action\` 入口按钮：入口位置从「侧栏底部按钮」变成「侧栏面板条目」。
 *
 * @module dsh-pmboard/client/page/register
 */
import { registerPagePanel, type SlotRegistrar } from './page-panel.ts'
import { BoardPanelHost } from './host.ts'
import { PANEL_ID, PANEL_LABEL } from '../dom.ts'

/** 侧栏条目排序：沿用原 sidebar.footer.action 的 order=110，界面次序不因迁移而变。 */
export const PMBOARD_PAGE_ORDER = 110

/** 注册所需的 client ctx 投影（只需 slots；与 index.ts 的 ApplyContext 结构兼容）。 */
export interface PmboardPageContext {
  slots?: SlotRegistrar
}

/**
 * 注册「项目看板」页面：main（key=PANEL_ID）+ sidebar.panellist（id=PANEL_ID）。
 *
 * @returns 幂等 disposer（撤销两端注册，HMR 重放安全）。
 * @throws ctx.slots 缺失时由 registerPagePanel 抛错——响亮失败，不静默降级为「页面不存在」。
 */
export function registerPmboardPage(ctx: PmboardPageContext): () => void {
  return registerPagePanel(ctx, {
    id: PANEL_ID,
    label: PANEL_LABEL,
    order: PMBOARD_PAGE_ORDER,
    Component: BoardPanelHost,
  })
}
