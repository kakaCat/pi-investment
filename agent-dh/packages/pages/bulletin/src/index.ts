// @pi-investment/dashboard-bulletin · 公告板（DSH GUI 双半插件 host 半，RFC 013）
// host 半：phase2 起向同源暴露 bulletin JSON API（/dashboard/api/bulletin/posts），
// 与 execution 的 /dashboard/api/board、holdings 的 /dashboard/api/holdings 互斥（路由契约）。
// GUI 呈现由 client 半承担（package.json dsh.client + exports ./client → lib/client.js，
// 浏览器加载后挂侧栏顶部入口 + 中心栏视图）。零工具、零 dsh-tools/core-tool 依赖。
// 模块形状与 dashboard-holdings / dashboard-execution 一致（name + apply 具名导出）。
//
// phase1（2026-09-05，用户指定节奏：先建包 + 顶部菜单按钮，验证 OK 再做看板正文）：
// apply 仅占位打日志；数据服务与路由在 phase2 实现（board 数据源 = Agent OS memory, RFC 009）。

import { Context } from '@deepseek-ai/cordis'

export const name = 'dashboard-bulletin'

export function apply(ctx: Context, _config?: unknown): void {
  const logger = ctx.logger(name)
  logger.info('bulletin phase1 host placeholder; board routes arrive in phase2 per RFC 013')
}
