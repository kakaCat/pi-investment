// @pi-investment/dashboard-genome · 自主进化看板（DSH GUI 双半插件 host 半）
// host 半：向同源暴露 /dashboard/api/genome JSON API（client 半 fetch 用）；
// GUI 呈现由 client 半承担（package.json dsh.client + exports["./client"] → lib/client.js，
// 浏览器加载后挂侧栏「自主进化」入口 + 中心栏视图）。
// 数据源：~/.dsh-agent-dh/genome/ 本地文件（genome.json + candidates.json），host 进程内 fs
// 直读——浏览器不直连本地文件。零工具、零 dsh-tools/core-tool 依赖（模式同 dashboard-execution）。
// 模块形状：name + apply 具名导出；路由经 (ctx as any).inject(['webServer']) 惰性注入 +
// webCtx.effect 包裹注册（disposer 自动注销）。

import { Context } from '@deepseek-ai/cordis'
import * as os from 'node:os'
import * as path from 'node:path'
import { GenomeAggregationService } from './services/genome-aggregation.js'
import { createGenomeHandler } from './routes/genome-routes.js'

export const name = 'dashboard-genome'

interface PluginConfig {
  /** genome 数据目录（默认 ~/.dsh-agent-dh/genome，与 genome 插件 cordis 配置 genomeDir 一致） */
  genomeDir?: string
}

function resolveOptions(config: PluginConfig | undefined) {
  return {
    genomeDir: config?.genomeDir || path.join(os.homedir(), '.dsh-agent-dh', 'genome'),
  }
}

export function apply(ctx: Context, config?: PluginConfig): void {
  const aggregator = new GenomeAggregationService(resolveOptions(config))
  const logger = ctx.logger(name)
  logger.info('dashboard-genome host applied (Autonomy 可观测 /dashboard/api/genome)')

  // 惰性注入 webServer：DSH web 启动后注入，注册即生效（模式同 dashboard-execution）
  ;(ctx as unknown as { inject?: (services: string[], cb: (webCtx: any) => void) => void }).inject?.(
    ['webServer'],
    (webCtx: { effect?: (fn: () => void, label?: string) => void; webServer?: any }) => {
      webCtx.effect?.(() => {
        webCtx.webServer.register({
          kind: 'exact',
          path: '/dashboard/api/genome',
          handler: createGenomeHandler(aggregator),
        })
      }, name + ': api')
      logger.info('routes registered: /dashboard/api/genome (client half renders GUI)')
    },
  )
}
