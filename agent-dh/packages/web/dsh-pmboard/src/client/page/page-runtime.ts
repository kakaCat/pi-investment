/**
 * 页面运行环境（模块级）—— 存放 client ctx 中「页面导航」相关的最小服务投影。
 *
 * 为什么需要它（REQ-260928185112-e20d FR-3）：apply() 收到的 ctx 只在 apply 作用域内可见，
 * 而 session-jump 在跳转时要先 \`layout.selectPanel(null)\`（收回看板面板、回当前对话）
 * 再 \`uiWorkspace.openSession(sid)\`（切会话）。本模块把 ctx.layout 交给一个模块级持有器，
 * 供 session-jump 经它读——与既有 window.__dshPmCtx 同款惰性读，但不再新增全局量。
 *
 * 依赖纪律：dsh-pmboard 是自包含包——本模块**零 import**（不引任何 @pi-investment/* 或裸 npm 包）。
 *
 * @module dsh-pmboard/client/page/page-runtime
 */

/** DSH 官方页面导航服务（ctx.layout）的投影：null = 显示当前对话。 */
export interface PageLayoutFace {
  /** 选中的主面板 id；null 表示回到当前对话（不改变当前会话）。 */
  selectPanel(id: string | null): void
}

let currentLayout: PageLayoutFace | undefined

/**
 * apply() 时注入 ctx.layout（服务缺失/降级时传 undefined，读取方须自行判定不可用）。
 * 与 clearPageLayout 配对使用，保证 HMR 重放后不残留上一轮的服务引用。
 */
export function setPageLayout(layout: PageLayoutFace | undefined): void {
  currentLayout = layout
}

/**
 * 读取当前 layout；未注入（或已 clear）时返回 undefined。
 *
 * 调用方**必须显式处理 undefined**（如 session-jump 返回 unavailable 并提示），
 * 不得把「layout 不可用」静默当成「已经回对话」。
 */
export function getPageLayout(): PageLayoutFace | undefined {
  return currentLayout
}

/** dispose 时清空引用（HMR 重放安全）。 */
export function clearPageLayout(): void {
  currentLayout = undefined
}
