/**
 * @pi-investment/web-liveness · host 半（空壳）。
 *
 * 本插件的全部行为都在 client 半（`src/client/`）：订阅框架在 `/plugins/events` 上的
 * 免鉴权 SSE，用 graph.rev 与页面加载时的 `__DSH_BOOT__.rev` 比对，判定服务端是否换过进程，
 * 据此提示/刷新页面。**host 侧不需要任何路由、工具或服务** —— 之所以仍做成插件包，
 * 是因为"能在浏览器里跑代码"这件事本身只能由 `dsh.client` 声明的 client 半提供。
 *
 * @module @pi-investment/web-liveness
 */
import type { Context } from '@deepseek-ai/cordis'

export const name = 'web-liveness'

export function apply(ctx: Context): void {
  ctx.logger(name).info('web-liveness host applied (client-only: watches /plugins/events for process change)')
}
