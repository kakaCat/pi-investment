// @pi-investment/dashboard-bulletin · 公告板看板（DSH GUI 双半插件 host 半，RFC 013）
// host 半：只向同源暴露 bulletin JSON API（/dashboard/api/bulletin/posts，client 半 fetch 用）；
// GUI 呈现由 client 半承担（package.json dsh.client + exports["./client"] → lib/client.js）。
// /dashboard/api/bulletin/posts 的唯一所有者——execution 独占 /dashboard/api/board、
// holdings 独占 /dashboard/api/holdings（双插件互斥路由契约）。
// 数据源：Agent OS memory（tag office:board），与 board_post/board_read/board_update 工具同源（RFC 009）。
// 模块形状与 dashboard-holdings 一致（name + apply 具名导出；路由经
// (ctx as any).inject(['webServer']) 惰性注入 + webCtx.effect 包裹注册，disposer 自动注销）。
//
// phase2（2026-09-05）：公告板主体——posts 聚合/过滤/计数/分页 JSON API；phase1 的
// /dashboard/api/bulletin-probe 探针已移除。

import { Context } from '@deepseek-ai/cordis'
import { BulletinAggregationService } from './services/bulletin-aggregation.js'
import { createBulletinHandler } from './routes/bulletin-routes.js'

export const name = 'dashboard-bulletin'

interface PluginConfig {
  /** Agent OS base URL（RFC 009 board 数据源） */
  agentOsBaseURL?: string
  requestTimeoutMs?: number
}

function resolveOptions(config: PluginConfig | undefined) {
  return {
    agentOsBaseURL: (config?.agentOsBaseURL || process.env.AGENT_OS_BASE_URL || 'http://localhost:8080').replace(/\/$/, ''),
    requestTimeoutMs: config?.requestTimeoutMs ?? 4000,
  }
}

export function apply(ctx: Context, config?: PluginConfig): void {
  const aggregator = new BulletinAggregationService(resolveOptions(config))
  const logger = ctx.logger(name)
  logger.info('dashboard-bulletin host applied (phase2: posts API)')

  // 惰性注入 webServer：DSH web 启动后注入，注册即生效（模式同 dashboard-holdings）
  ;(ctx as unknown as { inject?: (services: string[], cb: (webCtx: any) => void) => void }).inject?.(
    ['webServer'],
    (webCtx: { effect?: (fn: () => void, label?: string) => void; webServer?: any }) => {
      webCtx.effect?.(() => {
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/bulletin/posts',
          handler: createBulletinHandler(aggregator),
        })
      }, name + ': api')

      logger.info('routes registered: /dashboard/api/bulletin/posts (client half renders GUI)')
    },
  )
}
